"""Payroll (M20): runs, payslips, staff pay set-up, leave, advances, holidays, rules and "My pay"."""

import datetime
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.files import clean_document, content_type_for
from apps.organization.models import Program
from apps.payroll import services as pay
from apps.payroll.models import (
    Advance,
    Leave,
    PayAdjustment,
    PayComponent,
    PayProfile,
    PayrollRun,
    PayrollSettings,
    Payslip,
    PublicHoliday,
)
from apps.rbac.services import has_perm
from apps.reports import documents
from apps.sales.models import SaleLine
from apps.staff.models import StaffDocument, StaffProfile

from ..access import L, can, desk, lang
from .finance import download, export_doc
from .ops import _date
from .sales import _money

PAYROLL = ["payroll.view", "payroll.prepare", "payroll.approve"]
KIND_AR = {
    "salary": "راتب شهري",
    "allowance": "بدل شهري",
    "hourly": "أجر بالساعة (الحصص المُدرَّسة)",
    "per_class": "أجر لكل حصة",
    "commission": "عمولة على المبيعات",
}
LEAVE_AR = {"annual": "إجازة سنوية", "sick": "إجازة مرضية", "unpaid": "إجازة بدون راتب"}
DOC_AR = {
    "civil_id": "البطاقة المدنية",
    "residency": "الإقامة",
    "work_permit": "إذن العمل",
    "passport": "جواز السفر",
    "certificate": "شهادة تدريب",
    "first_aid": "شهادة إسعافات أولية",
    "contract": "عقد العمل",
    "other": "أخرى",
}


def _month(value, default=None):
    d = _date(value + "-01" if value and len(value) == 7 else value, default)
    return d.replace(day=1) if d else None


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
@desk(any_of=PAYROLL)
def payroll_home(request):
    if request.method == "POST":
        month = _month(request.POST.get("month"), timezone.localdate())
        run = pay.build_run(month, request.user)
        messages.success(
            request,
            L(
                "Payroll built from classes taught, sales, leave and adjustments.",
                "تم إعداد الرواتب من الحصص والمبيعات والإجازات والتعديلات.",
            ),
        )
        return redirect("desk:payroll_run", pk=run.pk)
    runs = PayrollRun.objects.select_related("submitted_by", "approved_by")[:24]
    return render(
        request,
        "desk/payroll/home.html",
        {
            "runs": [(r, pay.run_totals(r)) for r in runs],
            "settings": PayrollSettings.get(),
            "this_month": timezone.localdate().replace(day=1),
            "can_prepare": can(request, "payroll.prepare"),
        },
    )


@desk(any_of=PAYROLL)
def payroll_run(request, pk):
    run = get_object_or_404(
        PayrollRun.objects.select_related("submitted_by", "approved_by", "paid_by", "created_by"), pk=pk
    )
    fmt = request.GET.get("format")
    if fmt == "bank":
        rows = pay.bank_rows(run)
        record_event(action="bank_file_downloaded", instance=run)
        from apps.reports.export import render as render_doc

        if request.GET.get("as") == "csv":
            import csv
            import io

            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["Beneficiary name", "IBAN", "Bank", "Amount", "Currency", "Reference"])
            for r in rows:
                w.writerow([r["name"], r["iban"], r["bank"], f"{r['amount']:.3f}", r["currency"], r["reference"]])
            return download(buf.getvalue().encode("utf-8-sig"), "text/csv", f"{run.reference}-bank.csv")
        content, ctype, ext = render_doc(documents.bank_file_doc(run, rows), "xlsx", "en")
        return download(content, ctype, f"{run.reference}-bank.{ext}")
    if fmt:
        return export_doc(
            request,
            documents.payroll_summary_doc(run, pay.run_totals(run), pay.summary(run), lang()),
            f"{run.reference}-summary",
        )
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "rebuild":
            pay.build_run(run.month, request.user)
            messages.success(request, L("Rebuilt from the latest data.", "أُعيد الإعداد من أحدث البيانات."))
        elif action == "submit":
            pay.submit_run(run, request.user)
            messages.success(request, L("Submitted to the Accountant for approval.", "أُرسل إلى المحاسب للاعتماد."))
        elif action == "return":
            pay.return_run(run, request.user, request.POST.get("note", ""))
            messages.success(request, L("Returned to the OM.", "أُعيد إلى مدير العمليات."))
        elif action == "approve":
            pay.approve_run(run, request.user)
            messages.success(
                request, L("Approved. Payslips are released to staff.", "تم الاعتماد وإرسال القسائم للموظفين.")
            )
        elif action == "paid":
            pay.mark_paid(run, request.user)
            messages.success(request, L("Marked as paid.", "تم تسجيل الدفع."))
        return redirect("desk:payroll_run", pk=pk)
    return render(
        request,
        "desk/payroll/run.html",
        {
            "run": run,
            "slips": run.payslips.select_related("branch").order_by("full_name"),
            "totals": pay.run_totals(run),
            "summary": pay.summary(run),
            "settings": PayrollSettings.get(),
            "blocking": [w for w in run.warnings if w["code"] in pay.BLOCKING],
            "can_prepare": can(request, "payroll.prepare"),
            "can_approve": can(request, "payroll.approve"),
        },
    )


def _slip_for(request, pk):
    slip = get_object_or_404(Payslip.objects.select_related("run", "staff__user", "branch"), pk=pk)
    if has_perm(request.user, "payroll.view"):
        return slip
    if slip.staff.user_id == request.user.pk and slip.run.is_locked:
        return slip
    raise Http404


@desk(any_of=PAYROLL + ["payroll.self"])
def payslip(request, pk):
    slip = _slip_for(request, pk)
    if request.GET.get("format"):
        return export_doc(request, documents.payslip_doc(slip, lang()), f"payslip-{slip.run.month:%Y%m}-{slip.pk}")
    lines = list(slip.lines.all())
    return render(
        request,
        "desk/payroll/payslip.html",
        {
            "slip": slip,
            "earnings": [x for x in lines if x.kind == "earning"],
            "deductions": [x for x in lines if x.kind == "deduction"],
            "employer": [x for x in lines if x.kind == "employer"],
        },
    )


# ---------------------------------------------------------------------------
# Staff pay set-up
# ---------------------------------------------------------------------------
@desk(any_of=PAYROLL + ["staff.manage"])
def staff_list(request):
    qs = StaffProfile.objects.select_related("user", "primary_branch", "pay").prefetch_related("documents")
    if request.GET.get("expiring"):
        horizon = timezone.localdate() + datetime.timedelta(days=30)
        qs = qs.filter(documents__expires_on__lte=horizon).distinct()
    if not request.GET.get("all"):
        qs = qs.filter(user__is_active=True)
    return render(request, "desk/payroll/staff_list.html", {"staff": qs, "today": timezone.localdate()})


@desk(any_of=PAYROLL + ["staff.manage"])
def staff_pay(request, pk):
    staff = get_object_or_404(StaffProfile.objects.select_related("user", "primary_branch"), pk=pk)
    sees_pay = has_perm(request.user, "payroll.view") or has_perm(request.user, "payroll.prepare")
    editable = pay.can_edit_pay(request.user, staff)
    profile = PayProfile.objects.filter(staff=staff).prefetch_related("components__program").first()
    if request.method == "POST":
        action = request.POST.get("action")
        p = request.POST
        if action == "profile":
            pay.save_pay_profile(
                staff,
                request.user,
                iban=p.get("iban", "").replace(" ", "").upper()[:34],
                bank_name=p.get("bank_name", "")[:80],
                account_name=p.get("account_name", "")[:150],
                is_kuwaiti=p.get("is_kuwaiti") == "1",
            )
            messages.success(request, L("Bank and PIFSS details saved.", "تم حفظ بيانات البنك والتأمينات."))
        elif action == "component":
            profile = profile or pay.save_pay_profile(staff, request.user)
            pay.save_component(
                profile,
                request.user,
                kind=p.get("kind"),
                name=p.get("name", "")[:80],
                name_ar=p.get("name_ar", "")[:80],
                amount=_money(p.get("amount")) if p.get("amount") else None,
                percent=Decimal(p.get("percent")) if p.get("percent") else None,
                program=Program.objects.filter(pk=p.get("program") or 0).first(),
                session_kinds=p.getlist("session_kinds"),
                sale_categories=p.getlist("sale_categories"),
                valid_from=_date(p.get("valid_from"), timezone.localdate()),
            )
            messages.success(request, L("Pay item added.", "تمت إضافة بند الأجر."))
        elif action == "end_component":
            comp = get_object_or_404(PayComponent, pk=p.get("component"), profile__staff=staff)
            pay.end_component(comp, request.user, _date(p.get("last_day"), timezone.localdate()))
        elif action == "adjustment":
            pay.add_adjustment(
                staff,
                request.user,
                month=_month(p.get("month"), timezone.localdate()),
                kind=p.get("kind"),
                quantity=Decimal(p.get("quantity")) if p.get("quantity") else None,
                amount=_money(p.get("amount")) if p.get("amount") else None,
                note=p.get("note", "")[:255],
            )
            messages.success(request, L("Adjustment added.", "تمت إضافة التعديل."))
        elif action == "remove_adjustment":
            pay.remove_adjustment(get_object_or_404(PayAdjustment, pk=p.get("adjustment"), staff=staff), request.user)
        elif action == "document":
            if not has_perm(request.user, "staff.manage"):
                raise PermissionDenied
            doc = StaffDocument(
                staff=staff,
                kind=p.get("kind", "other"),
                title=p.get("title", "")[:120],
                number=p.get("number", "")[:60],
                expires_on=_date(p.get("expires_on")),
                created_by=request.user,
                updated_by=request.user,
            )
            if request.FILES.get("file"):
                doc.file.save("document", clean_document(request.FILES["file"]), save=False)
            doc.full_clean()
            doc.save()
            messages.success(request, L("Document saved.", "تم حفظ المستند."))
        elif action == "leaving":
            if not has_perm(request.user, "staff.manage"):
                raise PermissionDenied
            staff.end_date = _date(p.get("end_date"))
            staff.end_reason = p.get("end_reason", "")
            staff.updated_by = request.user
            staff.save(update_fields=["end_date", "end_reason", "updated_by", "updated_at"])
        return redirect("desk:staff_pay", pk=pk)
    today = timezone.localdate()
    ctx = {
        "staff": staff,
        "profile": profile,
        "sees_pay": sees_pay,
        "editable": editable,
        "documents": staff.documents.all(),
        "can_docs": has_perm(request.user, "staff.manage"),
        "doc_kinds": [(v, DOC_AR[v] if lang() == "ar" else label) for v, label in StaffDocument.Kind.choices],
    }
    if sees_pay:
        settings = PayrollSettings.get()
        ctx.update(
            components=profile.components.all() if profile else [],
            kinds=[(v, KIND_AR[v] if lang() == "ar" else label) for v, label in PayComponent.Kind.choices],
            programs=Program.objects.filter(is_active=True).select_related("branch"),
            categories=SaleLine.Category.choices,
            adj_kinds=PayAdjustment.Kind.choices,
            adjustments=PayAdjustment.objects.filter(
                staff=staff, month__gte=today.replace(day=1) - datetime.timedelta(days=62)
            ),
            month=today.replace(day=1),
            balance=pay.annual_leave_balance(staff, today, settings),
            eos=pay.end_of_service(profile, staff.end_date or today, staff.end_reason or "termination", settings)
            if profile
            else None,
            eos_resign=pay.end_of_service(profile, staff.end_date or today, "resignation", settings)
            if profile
            else None,
            leaves=staff.leaves.all()[:10],
            advances=staff.advances.all()[:10],
            payslips=staff.payslips.select_related("run")[:12],
            can_adjust=can(request, "payroll.prepare") and staff.user_id != request.user.pk,
        )
    return render(request, "desk/payroll/staff.html", ctx)


@desk(any_of=PAYROLL + ["staff.manage", "payroll.self"])
def staff_document_file(request, pk):
    doc = get_object_or_404(StaffDocument.objects.select_related("staff"), pk=pk)
    mine = doc.staff.user_id == request.user.pk
    if not doc.file or not (mine or has_perm(request.user, "staff.manage") or has_perm(request.user, "payroll.view")):
        raise Http404
    return FileResponse(doc.file.open("rb"), content_type=content_type_for(doc.file.name))


# ---------------------------------------------------------------------------
# Leave, advances, holidays, rules
# ---------------------------------------------------------------------------
@desk("leave.approve")
def leave(request):
    if request.method == "POST":
        item = get_object_or_404(Leave, pk=request.POST.get("leave"))
        pay.decide_leave(item, request.user, request.POST.get("decision") == "approve", request.POST.get("note", ""))
        return redirect("desk:leave")
    pending = Leave.objects.filter(status="pending").select_related("staff__user")
    return render(
        request,
        "desk/payroll/leave.html",
        {
            "pending": [(x, pay.affected_classes(x), pay.annual_leave_balance(x.staff)) for x in pending],
            "recent": Leave.objects.exclude(status="pending").select_related("staff__user", "decided_by")[:30],
            "labels": LEAVE_AR if lang() == "ar" else dict(Leave.Kind.choices),
            "can_payroll": any(can(request, p) for p in PAYROLL),
        },
    )


@desk("payroll.prepare")
def advances(request):
    if request.method == "POST":
        adv = get_object_or_404(Advance, pk=request.POST.get("advance"))
        pay.decide_advance(adv, request.user, request.POST.get("decision") == "approve")
        return redirect("desk:advances")
    return render(
        request,
        "desk/payroll/advances.html",
        {"advances": Advance.objects.select_related("staff__user", "decided_by")[:60]},
    )


@desk(any_of=["payroll.prepare", "payroll.approve"])
def holidays(request):
    if request.method == "POST":
        if request.POST.get("remove"):
            PublicHoliday.objects.filter(pk=request.POST["remove"]).delete()
        else:
            day = _date(request.POST.get("date"))
            if day:
                PublicHoliday.objects.update_or_create(
                    date=day,
                    defaults={
                        "name": request.POST.get("name", "")[:100],
                        "name_ar": request.POST.get("name_ar", "")[:100],
                    },
                )
        return redirect("desk:holidays")
    return render(
        request,
        "desk/payroll/holidays.html",
        {"holidays": PublicHoliday.objects.filter(date__year__gte=timezone.localdate().year - 1)},
    )


SETTING_FIELDS = [
    ("working_days_per_month", "Working days per month (daily rate = monthly ÷ this)", "أيام العمل في الشهر"),
    ("hours_per_day", "Hours per day (hourly rate = daily ÷ this)", "ساعات العمل في اليوم"),
    ("overtime_normal", "Overtime multiplier — normal day", "معامل العمل الإضافي — يوم عادي"),
    ("overtime_rest_day", "Overtime multiplier — rest day", "معامل العمل الإضافي — يوم راحة"),
    ("overtime_holiday", "Overtime multiplier — public holiday", "معامل العمل الإضافي — عطلة رسمية"),
    (
        "eos_days_first_five_years",
        "End-of-service days per year, first 5 years",
        "أيام مكافأة نهاية الخدمة لكل سنة — أول 5 سنوات",
    ),
    (
        "eos_days_after_five_years",
        "End-of-service days per year after 5 years",
        "أيام مكافأة نهاية الخدمة لكل سنة بعد 5 سنوات",
    ),
    ("eos_cap_months", "End-of-service cap (months of pay)", "الحد الأقصى للمكافأة (أشهر)"),
    ("resign_share_under_3", "On resignation: share under 3 years", "عند الاستقالة: النسبة لأقل من 3 سنوات"),
    ("resign_share_3_to_5", "On resignation: share 3–5 years", "عند الاستقالة: من 3 إلى 5 سنوات"),
    ("resign_share_5_to_10", "On resignation: share 5–10 years", "عند الاستقالة: من 5 إلى 10 سنوات"),
    ("resign_share_10_plus", "On resignation: share 10+ years", "عند الاستقالة: أكثر من 10 سنوات"),
    ("pifss_employee_percent", "PIFSS employee %", "نسبة التأمينات على الموظف"),
    ("pifss_employer_percent", "PIFSS employer %", "نسبة التأمينات على صاحب العمل"),
    ("pifss_salary_cap", "PIFSS monthly pay cap (KD)", "الحد الأعلى للراتب الخاضع للتأمينات"),
    ("annual_leave_days", "Annual leave days per year", "أيام الإجازة السنوية"),
    ("sick_full_pay_days", "Sick leave days on full pay", "أيام الإجازة المرضية بأجر كامل"),
    ("sick_three_quarter_days", "Sick leave days on ¾ pay", "أيام بثلاثة أرباع الأجر"),
    ("sick_half_pay_days", "Sick leave days on ½ pay", "أيام بنصف الأجر"),
    ("sick_quarter_pay_days", "Sick leave days on ¼ pay", "أيام بربع الأجر"),
    ("cutoff_day", "Cut-off day for classes and sales", "يوم الإقفال للحصص والمبيعات"),
]


@desk(any_of=PAYROLL)
def payroll_settings(request):
    settings = PayrollSettings.get()
    if request.method == "POST":
        values = {}
        for name, *_ in SETTING_FIELDS:
            raw = request.POST.get(name, "").strip()
            field = PayrollSettings._meta.get_field(name)
            values[name] = int(raw) if field.get_internal_type() == "PositiveSmallIntegerField" else Decimal(raw)
        pay.confirm_settings(request.user, request.POST.get("note", ""), **values)
        messages.success(request, L("Payroll rules confirmed.", "تم اعتماد قواعد الرواتب."))
        return redirect("desk:payroll_settings")
    fields = [(name, L(en, ar), getattr(settings, name)) for name, en, ar in SETTING_FIELDS]
    return render(
        request,
        "desk/payroll/settings.html",
        {"settings": settings, "fields": fields, "can_confirm": can(request, "payroll.approve")},
    )


# ---------------------------------------------------------------------------
# My pay (every member of staff)
# ---------------------------------------------------------------------------
@desk("payroll.self")
def my_pay(request):
    staff = StaffProfile.objects.filter(user=request.user).first()
    if staff is None:
        return render(request, "desk/payroll/my_pay.html", {"staff": None})
    if request.method == "POST":
        p = request.POST
        if p.get("action") == "leave":
            pay.request_leave(
                staff,
                request.user,
                kind=p.get("kind", "annual"),
                start=_date(p.get("start")),
                end=_date(p.get("end")),
                reason=p.get("reason", "")[:255],
            )
            messages.success(request, L("Leave requested.", "تم طلب الإجازة."))
        elif p.get("action") == "advance":
            pay.request_advance(
                staff,
                request.user,
                amount=_money(p.get("amount")),
                instalments=int(p.get("instalments") or 1),
                reason=p.get("reason", "")[:255],
                first_month=_month(p.get("first_month"), timezone.localdate()),
            )
            messages.success(
                request, L("Advance requested. The OM will decide.", "تم طلب السلفة وسيقرر مدير العمليات.")
            )
        elif p.get("action") == "cancel_leave":
            item = get_object_or_404(Leave, pk=p.get("leave"), staff=staff, status="pending")
            item.status, item.updated_by = Leave.Status.CANCELLED, request.user
            item.save(update_fields=["status", "updated_by", "updated_at"])
        return redirect("desk:my_pay")
    today = timezone.localdate()
    return render(
        request,
        "desk/payroll/my_pay.html",
        {
            "staff": staff,
            "payslips": Payslip.objects.filter(staff=staff, run__status__in=["approved", "paid"]).select_related("run"),
            "balance": pay.annual_leave_balance(staff, today),
            "leaves": staff.leaves.all()[:12],
            "advances": staff.advances.all()[:6],
            "documents": staff.documents.all(),
            "today": today,
            "next_month": (today.replace(day=28) + datetime.timedelta(days=4)).replace(day=1),
            "leave_kinds": [(v, LEAVE_AR[v] if lang() == "ar" else label) for v, label in Leave.Kind.choices],
            "freelance": staff.employment_type == "freelance",
        },
    )
