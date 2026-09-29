"""Reports (M10): weekly FRM-06 / FRM-07, Active Members, dashboards, emailed reports."""

import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.organization.models import Branch
from apps.payroll.services import previous_month
from apps.rbac.services import has_perm
from apps.reports import documents
from apps.reports import services as rep
from apps.reports.models import ReportSubscription, WeeklyReport, week_start
from apps.reports.tasks import allowed

from ..access import L, can, desk, lang
from .finance import export_doc
from .ops import _date

REPORT_PERMS = ["reports.branch", "reports.all", "reports.verify"]


def _may_see(user, branch):
    return any(has_perm(user, p, branch.pk) for p in REPORT_PERMS)


# ---------------------------------------------------------------------------
# Weekly reports
# ---------------------------------------------------------------------------
@desk(any_of=REPORT_PERMS)
def weekly_reports(request):
    today = timezone.localdate()
    this_week = week_start(today)
    branches = [b for b in Branch.objects.filter(is_active=True).order_by("-code") if _may_see(request.user, b)]
    weeks = [this_week - datetime.timedelta(days=7 * i) for i in range(1, 9)]
    existing = {
        (r.kind, r.branch_id, r.week_start): r
        for r in WeeklyReport.objects.filter(branch__in=branches, week_start__in=weeks).select_related(
            "prepared_by", "verified_by"
        )
    }
    table = []
    for w in weeks:
        for b in branches:
            for kind in (WeeklyReport.Kind.SALES, WeeklyReport.Kind.BRANCH):
                r = existing.get((kind, b.pk, w))
                due = timezone.make_aware(datetime.datetime.combine(w + datetime.timedelta(days=7), datetime.time(12)))
                table.append(
                    {"week": w, "branch": b, "kind": kind, "report": r, "late": r is None and timezone.now() > due}
                )
    return render(request, "desk/reports/weekly_list.html", {"table": table})


def _report_context(request, kind, code, start):
    if kind not in WeeklyReport.Kind.values:
        raise Http404
    branch = get_object_or_404(Branch, code=code)
    if not _may_see(request.user, branch):
        raise PermissionDenied
    start = week_start(_date(start) or timezone.localdate())
    report = (
        WeeklyReport.objects.filter(kind=kind, branch=branch, week_start=start)
        .select_related("prepared_by", "verified_by")
        .first()
    )
    frozen = report is not None and report.status != WeeklyReport.Status.RETURNED
    data = report.data if frozen else rep.jsonable(rep.build(kind, branch, start, "en"))
    return branch, start, report, frozen, data


@desk(any_of=REPORT_PERMS)
def weekly_report(request, kind, code, start):
    branch, start, report, frozen, data = _report_context(request, kind, code, start)
    if request.GET.get("format"):
        maker = documents.weekly_sales_doc if kind == "sales" else documents.weekly_branch_doc
        return export_doc(
            request, maker(data, branch, report, lang()), f"{(report.reference if report else kind)}-{start:%Y%m%d}"
        )
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "prepare":
            rep.prepare_report(
                kind,
                branch,
                start,
                request.user,
                leaving_reasons=request.POST.get("leaving_reasons", ""),
                facility_issues=request.POST.get("facility_issues", ""),
                om_decisions=request.POST.get("om_decisions", ""),
            )
            messages.success(
                request,
                L("Prepared and sent to the OM for verification.", "تم الإعداد والإرسال لمدير العمليات للتحقق."),
            )
        elif action == "verify":
            rep.verify_report(report, request.user)
            messages.success(request, L("Verified.", "تم التحقق."))
        elif action == "return":
            rep.return_report(report, request.user, request.POST.get("note", ""))
            messages.success(request, L("Returned to the branch for correction.", "أُعيد إلى الفرع للتصحيح."))
        return redirect("desk:weekly_report", kind=kind, code=code, start=start.isoformat())
    from apps.reports.services import MEASURES

    labels = {k: (ar if lang() == "ar" else en) for k, en, ar in MEASURES}
    rows = data.get("rows", [])
    if kind == "branch":
        rows = [{**r, "label": labels[r["key"]]} for r in rows]
    return render(
        request,
        "desk/reports/weekly.html",
        {
            "kind": kind,
            "branch": branch,
            "start": start,
            "end": start + datetime.timedelta(days=6),
            "report": report,
            "frozen": frozen,
            "data": data,
            "rows": rows,
            "changed": frozen and rep.changed_since_frozen(report),
            "can_prepare": has_perm(request.user, "reports.branch", branch.pk)
            and start + datetime.timedelta(days=6) < timezone.localdate(),
            "can_verify": has_perm(request.user, "reports.verify", branch.pk),
            "prev": start - datetime.timedelta(days=7),
            "next": start + datetime.timedelta(days=7)
            if start + datetime.timedelta(days=7) <= week_start(timezone.localdate())
            else None,
        },
    )


# ---------------------------------------------------------------------------
# Active members
# ---------------------------------------------------------------------------
def _branch_scope(request):
    branches, combined = rep.branches_for(request.user)
    if not branches:
        raise PermissionDenied
    wanted = request.GET.get("branch") or ("all" if combined else request.branch.code)
    if wanted == "all" and combined:
        return branches, None, combined, "all"
    chosen = [b for b in branches if b.code == wanted] or [
        request.branch if request.branch in branches else branches[0]
    ]
    return chosen, chosen[0], combined, chosen[0].code


@desk(any_of=["reports.branch", "reports.all"])
def active_members(request):
    branches, branch, combined, wanted = _branch_scope(request)
    on = _date(request.GET.get("on"), timezone.localdate())
    data = rep.active_members(on, branch, lang())
    change = rep.active_change(branch, on)
    scope = (branch.name_ar if lang() == "ar" else branch.name) if branch else L("Both branches", "الفرعان")
    if request.GET.get("format"):
        return export_doc(
            request, documents.active_members_doc(data, scope, change, lang()), f"elite-active-members-{on:%Y%m%d}"
        )
    return render(
        request,
        "desk/reports/active.html",
        {
            "data": data,
            "change": change,
            "on": on,
            "branches": rep.branches_for(request.user)[0],
            "wanted": wanted,
            "combined": combined,
            "scope": scope,
        },
    )


# ---------------------------------------------------------------------------
# Dashboards
# ---------------------------------------------------------------------------
@desk(any_of=["reports.branch", "reports.all"])
def dashboards(request):
    branches, branch, combined, wanted = _branch_scope(request)
    tab = request.GET.get("tab", "daily")
    today = timezone.localdate()
    ctx = {"tab": tab, "branches": rep.branches_for(request.user)[0], "wanted": wanted, "combined": combined}
    if tab == "weekly":
        start = week_start(_date(request.GET.get("week"), today))
        ctx.update(data=rep.weekly_dashboard(branches, start), start=start, prev=start - datetime.timedelta(days=7))
    elif tab == "monthly":
        raw = request.GET.get("month", "")
        month = (_date(raw + "-01" if len(raw) == 7 else raw, today) or today).replace(day=1)
        data = rep.monthly_dashboard(branches, month)
        if request.GET.get("format"):
            return export_doc(request, documents.monthly_doc(data, lang()), f"elite-monthly-{month:%Y%m}")
        ctx.update(data=data, month=month, prev=previous_month(month))
    elif tab == "training":
        end = _date(request.GET.get("end"), today)
        start = end - datetime.timedelta(days=27)
        ctx.update(data=rep.training_dashboard(branches, start, end), start=start, end=end)
    elif tab == "marketing":
        end = _date(request.GET.get("end"), today)
        start = end - datetime.timedelta(days=27)
        ctx.update(data=rep.marketing_dashboard(branches, start, end), start=start, end=end)
    else:
        tab = ctx["tab"] = "daily"
        day = _date(request.GET.get("day"), today)
        data = rep.daily_dashboard(branches, day)
        if request.GET.get("format"):
            return export_doc(request, documents.daily_doc(data, lang()), f"elite-daily-{day:%Y%m%d}")
        ctx.update(data=data, day=day, prev=day - datetime.timedelta(days=1))
    return render(request, "desk/reports/dashboards.html", ctx)


# ---------------------------------------------------------------------------
# Emailed reports
# ---------------------------------------------------------------------------
@desk(any_of=["reports.branch", "reports.all"])
def subscriptions(request):
    if request.method == "POST":
        branch = Branch.objects.filter(pk=request.POST.get("branch") or 0).first()
        sub = ReportSubscription(
            user=request.user,
            report=request.POST.get("report", "daily"),
            branch=branch,
            format=request.POST.get("format", "pdf"),
            language=lang(),
            created_by=request.user,
        )
        if sub.report not in ReportSubscription.Report.values:
            raise Http404
        if sub.report in ("weekly_sales", "weekly_branch") and branch is None:
            messages.error(
                request, L("Weekly forms are per branch: choose a branch.", "النماذج الأسبوعية لكل فرع: اختر الفرع.")
            )
        elif not allowed(sub):
            raise PermissionDenied
        else:
            sub.save()
            messages.success(
                request,
                L(
                    f"Scheduled. It will be emailed to {request.user.email}.",
                    f"تمت الجدولة وسيُرسل إلى {request.user.email}.",
                ),
            )
        return redirect("desk:subscriptions")
    return render(
        request,
        "desk/reports/subscriptions.html",
        {
            "subs": ReportSubscription.objects.filter(user=request.user).select_related("branch"),
            "reports": ReportSubscription.Report.choices,
            "branches": rep.branches_for(request.user)[0],
            "combined": can(request, "reports.all"),
        },
    )


@require_POST
@desk(any_of=["reports.branch", "reports.all"])
def subscription_stop(request, pk):
    get_object_or_404(ReportSubscription, pk=pk, user=request.user).delete()
    return redirect("desk:subscriptions")
