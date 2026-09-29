"""
Report figures (scope M10). Everything is calculated from live data; weekly reports are frozen
when prepared (see models). Numbers follow Elite's current forms so the team recognises them:
FRM-06 Weekly Sales, FRM-07 Weekly Branch and the Active Members Report (EA-DOC-003).
"""

import datetime
from collections import OrderedDict, defaultdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.classes.models import Attendance, Booking, ClassChange, ClassSession
from apps.core.validators import day_range
from apps.members.services import contact_mobile, display_name
from apps.organization.models import Branch, PricingOption
from apps.rbac.services import has_perm, notify_perm
from apps.sales.models import CashUp, Membership, Payment, Sale, SaleLine

from .models import ActiveMembersSnapshot, WeeklyReport, week_start

ZERO = Decimal("0.000")
TRIAL_CONVERSION_DAYS = 14
LOST_AFTER_DAYS = 14  # business rule 4


def jsonable(value):
    """Decimals and dates to strings so a frozen copy can be stored and shown exactly."""
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    if isinstance(value, Decimal):
        return f"{value:.3f}"
    if isinstance(value, datetime.datetime):
        return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value


def _range(start, end):
    s0, _ = day_range(start)
    _, e1 = day_range(end)
    return s0, e1


def branches_for(user, perm_branch="reports.branch", perm_all="reports.all"):
    """Branches a user may report on; `combined` is True when they may see both together."""
    branches = [b for b in Branch.objects.filter(is_active=True).order_by("-code") if has_perm(user, perm_branch, b.pk)]
    combined = has_perm(user, perm_all)
    if combined:
        branches = list(Branch.objects.filter(is_active=True).order_by("-code"))
    return branches, combined


# ---------------------------------------------------------------------------
# Active members (business rule 1, decision P2-14)
# ---------------------------------------------------------------------------
def active_memberships(on, branch=None):
    qs = (
        Membership.objects.filter(
            pricing_option__kind=PricingOption.Kind.MEMBERSHIP,
            status=Membership.Status.ACTIVE,
            start_date__lte=on,
            end_date__gte=on,
        )
        .exclude(sale_line__line_total__lte=0)  # given free: not a paying member
        .select_related("member", "pricing_option", "branch", "sale_line")
        .prefetch_related("pricing_option__programs")
    )
    if branch is not None:
        qs = qs.filter(branch=branch)
    return qs


def program_labels(membership, lang="en"):
    option = membership.pricing_option
    if option.all_access or not option.programs.all():
        name = membership.branch.name_ar if lang == "ar" else membership.branch.name
        return [f"{name} ({'جميع البرامج' if lang == 'ar' else 'All-Access'})"]
    return [(p.name_ar or p.name) if lang == "ar" else p.name for p in option.programs.all()]


def active_members(on=None, branch=None, lang="en") -> dict:
    """Unique members, per program (a member in two programs counts once in each) and the roster."""
    on = on or timezone.localdate()
    memberships = list(active_memberships(on, branch).order_by("member__last_name", "member__first_name"))
    member_ids = {m.member_id for m in memberships}
    visits = {
        row["member_id"]: row
        for row in Attendance.objects.filter(member_id__in=member_ids, session__date__lte=on)
        .values("member_id")
        .annotate(n=Count("id"), last=Max("checked_in_at"))
    }
    last_class = {}
    for a in (
        Attendance.objects.filter(member_id__in=member_ids, session__date__lte=on)
        .select_related("session")
        .order_by("member_id", "-checked_in_at")
    ):
        last_class.setdefault(
            a.member_id, a.session.title_ar if lang == "ar" and a.session.title_ar else a.session.title_en
        )

    by_program = OrderedDict()
    roster, seen = [], set()
    for m in memberships:
        for label in program_labels(m, lang):
            row = by_program.setdefault(label, {"total": set(), "branches": defaultdict(set)})
            row["total"].add(m.member_id)
            row["branches"][m.branch.code].add(m.member_id)
        v = visits.get(m.member_id)
        roster.append(
            {
                "member_id": m.member_id,
                "name": display_name(m.member, lang),
                "branch": m.branch.name_ar if lang == "ar" else m.branch.name,
                "branch_code": m.branch.code,
                "option": m.pricing_option.name_ar
                if lang == "ar" and m.pricing_option.name_ar
                else m.pricing_option.name,
                "programs": ", ".join(program_labels(m, lang)),
                "class_attended": last_class.get(m.member_id, ""),
                "last_visit": timezone.localtime(v["last"]).date() if v and v["last"] else None,
                "visits": v["n"] if v else 0,
                "expires": m.end_date,
                "paid": m.sale_line.line_total if m.sale_line_id else None,
                "phone": contact_mobile(m.member),
                "verified": bool(v),
                "first_listing": m.member_id not in seen,
            }
        )
        seen.add(m.member_id)
    codes = sorted({m.branch.code for m in memberships}, reverse=True)
    programs = [
        {"label": label, "total": len(row["total"]), "branches": {c: len(row["branches"].get(c, ())) for c in codes}}
        for label, row in by_program.items()
    ]
    return {
        "on": on,
        "total": len(member_ids),
        "by_branch": {c: len({m.member_id for m in memberships if m.branch.code == c}) for c in codes},
        "codes": codes,
        "programs": programs,
        "program_sum": sum(p["total"] for p in programs),
        "roster": roster,
        "verified": sum(1 for r in roster if r["verified"] and r["first_listing"]),
        "member_ids": sorted(member_ids),
    }


def snapshot_active_members(day=None) -> int:
    """Friday night: keep the count per branch for the week-over-week change."""
    day = day or timezone.localdate()
    n = 0
    for branch in Branch.objects.filter(is_active=True):
        data = active_members(day, branch)
        ActiveMembersSnapshot.objects.update_or_create(
            date=day,
            branch=branch,
            defaults={
                "total": data["total"],
                "by_program": {p["label"]: p["total"] for p in data["programs"]},
                "member_ids": data["member_ids"],
            },
        )
        n += 1
    return n


def active_change(branch, on) -> dict:
    """This week's count against last Friday's snapshot (or last week's live figure when none)."""
    last_friday = on - datetime.timedelta(days=(on.weekday() - 4) % 7 or 7)
    now = active_members(on, branch)["total"] if branch else active_members(on)["total"]
    snaps = ActiveMembersSnapshot.objects.filter(date=last_friday)
    if branch is not None:
        snaps = snaps.filter(branch=branch)
    if snaps.exists():
        if branch is not None:
            before = snaps.first().total
        else:
            before = len(set().union(*[set(s.member_ids) for s in snaps]))
    else:
        before = active_members(last_friday, branch)["total"]
    return {"now": now, "before": before, "change": now - before, "since": last_friday}


# ---------------------------------------------------------------------------
# FRM-06 Weekly Sales Report
# ---------------------------------------------------------------------------
METHODS = [("knet", "KNET", "كي نت"), ("card", "Visa / MC", "فيزا / ماستركارد"), ("cash", "Cash", "نقداً")]


def weekly_sales(branch, start, lang="en") -> dict:
    from apps.finance.models import Expense

    end = start + datetime.timedelta(days=6)
    s0, e1 = _range(start, end)
    sales = (
        Sale.objects.filter(branch=branch, created_at__gte=s0, created_at__lt=e1)
        .select_related("member")
        .prefetch_related("lines__pricing_option__programs", "payments")
        .order_by("created_at")
    )
    rows = []
    for sale in sales:
        methods = sorted({p.get_method_display() for p in sale.payments.all()})
        for line in sale.lines.all():
            rows.append(
                {
                    "date": timezone.localtime(sale.created_at).date(),
                    "receipt": sale.reference,
                    "sale_id": sale.pk,
                    "member": display_name(sale.member, "en") if sale.member_id else sale.customer_name,
                    "member_ar": display_name(sale.member, "ar") if sale.member_id else sale.customer_name,
                    "program": _line_program(line, "en"),
                    "program_ar": _line_program(line, "ar"),
                    "category": line.category,
                    "method": " + ".join(methods),
                    "amount": line.line_total,
                    "refund": sale.kind == Sale.Kind.REFUND,
                }
            )
    payments = Payment.objects.filter(sale__branch=branch, received_at__gte=s0, received_at__lt=e1)
    cash_ups = list(CashUp.objects.filter(branch=branch, date__range=(start, end)))
    open_days = [
        start + datetime.timedelta(days=i)
        for i in range(7)
        if (start + datetime.timedelta(days=i)).weekday() in _python_open_days(branch)
        and start + datetime.timedelta(days=i) <= timezone.localdate()
    ]
    closed = [c for c in cash_ups if c.status != CashUp.Status.DRAFT]
    missing = [d for d in open_days if d not in {c.date for c in closed}]
    by_method = []
    for code, en, ar in METHODS:
        mine = payments.filter(method=code)
        total = mine.aggregate(t=Sum("amount"))["t"] or ZERO
        if code == "cash":
            counted = sum(((c.counted_cash or ZERO) + c.cash_paid_out for c in closed), ZERO)
        elif code == "knet":
            counted = sum((c.terminal_knet or ZERO for c in closed), ZERO)
        else:
            counted = sum((c.terminal_card or ZERO for c in closed), ZERO)
        system_closed = sum(
            (
                (c.expected_cash + c.cash_paid_out)
                if code == "cash"
                else (c.expected_knet if code == "knet" else c.expected_card)
                for c in closed
            ),
            ZERO,
        )
        by_method.append(
            {
                "code": code,
                "label": ar if lang == "ar" else en,
                "count": mine.values("sale_id").distinct().count(),
                "total": total,
                "settled": counted,
                "difference": counted - system_closed,
                "matches": not missing and counted == system_closed,
            }
        )
    expenses = [
        {
            "date": e.date,
            "description": e.description,
            "paid_to": e.paid_to,
            "amount": e.amount,
            "receipt": e.has_receipt,
            "status": e.status,
            "paid_from": e.paid_from,
            "id": e.pk,
        }
        for e in Expense.objects.filter(branch=branch, date__range=(start, end))
        .exclude(status=Expense.Status.REJECTED)
        .order_by("date", "id")
    ]
    total_sales = sum((r["amount"] for r in rows), ZERO)
    total_expenses = sum((e["amount"] for e in expenses), ZERO)
    return {
        "branch": branch.code,
        "start": start,
        "end": end,
        "rows": rows,
        "by_method": by_method,
        "missing_cash_ups": missing,
        "total_sales": total_sales,
        "expenses": expenses,
        "total_expenses": total_expenses,
        "net": total_sales - total_expenses,
    }


def _line_program(line, lang):
    option = line.pricing_option
    if option is None:
        return line.description_ar if lang == "ar" and line.description_ar else line.description
    progs = list(option.programs.all())
    if progs:
        return ", ".join(((p.name_ar or p.name) if lang == "ar" else p.name) for p in progs)
    return option.name_ar if lang == "ar" and option.name_ar else option.name


def _python_open_days(branch):
    """Branch.open_days uses Kuwait numbering 0=Saturday … 6=Friday; convert to Python weekdays."""
    return {(d + 5) % 7 for d in (branch.open_days or range(7))}


# ---------------------------------------------------------------------------
# FRM-07 Weekly Branch Report
# ---------------------------------------------------------------------------
def _week_measures(branch, start, end=None) -> dict:
    """FRM-07 measures for a week (or any period when `end` is given, e.g. a month or a quarter)."""
    from apps.operations.models import Complaint, Incident

    end = end or start + datetime.timedelta(days=6)
    s0, e1 = _range(start, end)
    lines = SaleLine.objects.filter(
        sale__branch=branch, sale__kind=Sale.Kind.SALE, sale__created_at__gte=s0, sale__created_at__lt=e1
    )
    trials = Booking.objects.filter(session__branch=branch, session__date__range=(start, end), is_trial=True).exclude(
        status=Booking.Status.CANCELLED
    )
    attended = [b for b in trials.select_related("member", "session") if b.status == Booking.Status.ATTENDED]
    converted = sum(1 for b in attended if _trial_converted(b))
    lost = [
        m
        for m in Membership.objects.filter(
            branch=branch,
            pricing_option__kind=PricingOption.Kind.MEMBERSHIP,
            end_date__range=(
                start - datetime.timedelta(days=LOST_AFTER_DAYS + 1),
                end - datetime.timedelta(days=LOST_AFTER_DAYS + 1),
            ),
        ).select_related("member")
        if not Membership.objects.filter(
            member_id=m.member_id, pricing_option__kind=PricingOption.Kind.MEMBERSHIP, end_date__gt=m.end_date
        )
        .exclude(status=Membership.Status.REFUNDED)
        .exists()
    ]
    return {
        "active": len(active_memberships(end, branch).values_list("member_id", flat=True).distinct()),
        "new": lines.filter(category=SaleLine.Category.NEW).values("sale__member_id").distinct().count(),
        "trials_booked": trials.count(),
        "trials_attended": len(attended),
        "trials_converted": converted,
        "renewals": lines.filter(category=SaleLine.Category.RENEW).count(),
        "lost": len({m.member_id for m in lost}),
        "incidents": Incident.objects.filter(branch=branch, occurred_at__gte=s0, occurred_at__lt=e1).count(),
        "complaints_received": Complaint.objects.filter(branch=branch, received_at__gte=s0, received_at__lt=e1).count(),
        "complaints_closed": Complaint.objects.filter(branch=branch, closed_at__gte=s0, closed_at__lt=e1).count(),
        "class_changes": ClassChange.objects.filter(
            session__branch=branch, created_at__gte=s0, created_at__lt=e1
        ).count(),
    }


def _trial_converted(booking) -> bool:
    """The trial person bought a first membership within 14 days of the trial."""
    until = booking.session.date + datetime.timedelta(days=TRIAL_CONVERSION_DAYS)
    s0, e1 = _range(booking.session.date, until)
    new = SaleLine.objects.filter(
        category=SaleLine.Category.NEW, sale__kind=Sale.Kind.SALE, sale__created_at__gte=s0, sale__created_at__lt=e1
    )
    if booking.member_id:
        return new.filter(sale__member_id=booking.member_id).exists()
    if booking.guest_mobile:
        return new.filter(
            Q(sale__customer_mobile=booking.guest_mobile)
            | Q(sale__member__mobile=booking.guest_mobile)
            | Q(sale__member__guardian_links__guardian__mobile=booking.guest_mobile)
        ).exists()
    return False


MEASURES = [
    ("active", "Active members (week end)", "الأعضاء النشطون (نهاية الأسبوع)"),
    ("new", "New members", "أعضاء جدد"),
    ("trials", "Trials booked / attended / converted", "التجارب: محجوزة / حضرت / اشتركت"),
    ("renewals", "Renewals completed", "التجديدات المكتملة"),
    ("lost", "Members lost", "الأعضاء المفقودون"),
    ("incidents", "Incidents reported", "الحوادث المبلغ عنها"),
    ("complaints", "Complaints received / closed", "الشكاوى: مستلمة / مغلقة"),
    ("class_changes", "Class changes", "تغييرات الحصص"),
]


def weekly_branch(branch, start, lang="en") -> dict:
    from apps.operations.models import Complaint, Incident, ShiftOpening
    from apps.renewals.models import FollowUp

    end = start + datetime.timedelta(days=6)
    this, last = _week_measures(branch, start), _week_measures(branch, start - datetime.timedelta(days=7))

    def fmt(m):
        return {
            "active": str(m["active"]),
            "new": str(m["new"]),
            "trials": f"{m['trials_booked']} / {m['trials_attended']} / {m['trials_converted']}",
            "renewals": str(m["renewals"]),
            "lost": str(m["lost"]),
            "incidents": str(m["incidents"]),
            "complaints": f"{m['complaints_received']} / {m['complaints_closed']}",
            "class_changes": str(m["class_changes"]),
        }

    def change(key):
        simple = {"active", "new", "renewals", "lost", "incidents", "class_changes"}
        if key in simple:
            return this[key] - last[key]
        if key == "trials":
            return this["trials_booked"] - last["trials_booked"]
        return this["complaints_received"] - last["complaints_received"]

    t, lw = fmt(this), fmt(last)
    rows = [{"key": k, "this": t[k], "last": lw[k], "change": change(k)} for k, *_ in MEASURES]
    s0, e1 = _range(start, end)
    leaving = [
        f"{display_name(f.member, 'en')}: {f.leaving_reason or '—'}"
        for f in FollowUp.objects.filter(
            branch=branch, outcome="L", created_at__gte=s0, created_at__lt=e1
        ).select_related("member")
    ]
    hazards = [
        f"{o.date:%d/%m}: {o.hazard}"
        for o in ShiftOpening.objects.filter(branch=branch, date__range=(start, end)).exclude(hazard="")
    ]
    return {
        "branch": branch.code,
        "start": start,
        "end": end,
        "rows": rows,
        "leaving": leaving,
        "open_incidents": list(
            Incident.objects.filter(branch=branch, status="open").values_list("reference", flat=True)
        ),
        "open_complaints": list(
            Complaint.objects.filter(branch=branch, status="open").values_list("reference", flat=True)
        ),
        "hazards": hazards,
        "measures": this,
    }


# ---------------------------------------------------------------------------
# Prepare → verify (Branch Admin prepares, OM verifies)
# ---------------------------------------------------------------------------
def build(kind, branch, start, lang="en"):
    return weekly_sales(branch, start, lang) if kind == WeeklyReport.Kind.SALES else weekly_branch(branch, start, lang)


@transaction.atomic
def prepare_report(kind, branch, start, user, **text) -> WeeklyReport:
    from apps.operations.services import next_reference

    if not has_perm(user, "reports.branch", branch.pk):
        raise PermissionDenied("You cannot prepare reports for this branch.")
    start = week_start(start)
    if start + datetime.timedelta(days=6) >= timezone.localdate():
        raise ValidationError("A weekly report can be prepared once the week has ended (after Friday).")
    report = WeeklyReport.objects.select_for_update().filter(kind=kind, branch=branch, week_start=start).first()
    if report is not None and report.status != WeeklyReport.Status.RETURNED:
        raise ValidationError("This report has already been prepared.")
    data = jsonable(build(kind, branch, start, "en"))
    if report is None:
        report = WeeklyReport(
            kind=kind,
            branch=branch,
            week_start=start,
            reference=next_reference(WeeklyReport.FORM[kind], branch, start.year),
            created_by=user,
        )
    report.data = data
    report.status, report.prepared_by, report.prepared_at = WeeklyReport.Status.PREPARED, user, timezone.now()
    report.return_note, report.updated_by = "", user
    for field in ("leaving_reasons", "facility_issues", "om_decisions"):
        if field in text:
            setattr(report, field, (text[field] or "").strip())
    report.save()
    msg = f"{report.get_kind_display()} {report.reference} ({branch.code}) is ready for verification."
    transaction.on_commit(lambda: notify_perm("reports.verify", msg, branch.pk, exclude=user))
    return report


@transaction.atomic
def verify_report(report: WeeklyReport, user) -> WeeklyReport:
    report = WeeklyReport.objects.select_for_update().get(pk=report.pk)
    if not has_perm(user, "reports.verify", report.branch_id):
        raise PermissionDenied("Only the Operations Manager verifies weekly reports.")
    if report.prepared_by_id == user.pk:
        raise PermissionDenied("Someone else must verify a report you prepared.")
    if report.status != WeeklyReport.Status.PREPARED:
        raise ValidationError("Only a prepared report can be verified.")
    report.status, report.verified_by, report.verified_at, report.updated_by = (
        WeeklyReport.Status.VERIFIED,
        user,
        timezone.now(),
        user,
    )
    report.save()
    record_event(action="weekly_report_verified", instance=report, branch_id=report.branch_id)
    return report


@transaction.atomic
def return_report(report: WeeklyReport, user, note: str) -> WeeklyReport:
    report = WeeklyReport.objects.select_for_update().get(pk=report.pk)
    if not has_perm(user, "reports.verify", report.branch_id):
        raise PermissionDenied("Only the Operations Manager returns weekly reports.")
    if report.status != WeeklyReport.Status.PREPARED:
        raise ValidationError("Only a prepared report can be returned.")
    if not note.strip():
        raise ValidationError("Say what needs correcting.")
    report.status, report.return_note, report.updated_by = WeeklyReport.Status.RETURNED, note.strip()[:255], user
    report.save()
    return report


def changed_since_frozen(report: WeeklyReport) -> bool:
    """True when live figures no longer match the prepared copy (e.g. a late refund)."""
    live = jsonable(build(report.kind, report.branch, report.week_start, "en"))
    if report.kind == WeeklyReport.Kind.SALES:
        return live["total_sales"] != report.data.get("total_sales") or live["total_expenses"] != report.data.get(
            "total_expenses"
        )
    return live["measures"] != report.data.get("measures")


def remind_due_reports(now=None) -> int:
    """Saturday 12:00: tell each branch's preparers and the OM which weekly reports are missing."""
    now = now or timezone.localtime()
    last_week = week_start(now.date()) - datetime.timedelta(days=7)
    n = 0
    for branch in Branch.objects.filter(is_active=True):
        missing = [
            WeeklyReport.FORM[k]
            for k in WeeklyReport.Kind.values
            if not WeeklyReport.objects.filter(kind=k, branch=branch, week_start=last_week)
            .exclude(status="returned")
            .exists()
        ]
        if missing:
            text = f"{branch.name}: {', '.join(missing)} for the week of {last_week:%d/%m} are due today at 12:00."
            n += notify_perm("reports.branch", text, branch.pk)
    return n


# ---------------------------------------------------------------------------
# Dashboards (Mindbody reporting cadence, scope M10)
# ---------------------------------------------------------------------------
def daily_dashboard(branches, day) -> dict:
    from apps.classes.services import utilisation

    s0, e1 = day_range(day)
    rows = []
    for b in branches:
        sessions = ClassSession.objects.filter(branch=b, date=day, status="scheduled")
        visits = Attendance.objects.filter(session__branch=b, session__date=day).count()
        fill = utilisation(b, day, day)
        sales = Payment.objects.filter(sale__branch=b, received_at__gte=s0, received_at__lt=e1)
        cash_up = CashUp.objects.filter(branch=b, date=day).first()
        rows.append(
            {
                "branch": b,
                "classes": sessions.count(),
                "visits": visits,
                "no_shows": Booking.objects.filter(session__branch=b, session__date=day, status="no_show").count(),
                "fill": _avg_fill(fill),
                "sales_total": sales.aggregate(t=Sum("amount"))["t"] or ZERO,
                "sales_count": sales.values("sale_id").distinct().count(),
                "by_method": {m: sales.filter(method=m).aggregate(t=Sum("amount"))["t"] or ZERO for m, *_ in METHODS},
                "cash_up": cash_up.get_status_display() if cash_up else "",
                "cash_up_status": cash_up.status if cash_up else "missing",
            }
        )
    return {
        "day": day,
        "rows": rows,
        "totals": _sum_rows(rows, ("classes", "visits", "no_shows", "sales_total", "sales_count")),
    }


def _avg_fill(util) -> int:
    rows = util if isinstance(util, list) else list(util)
    fills = [r["fill"] for r in rows if isinstance(r, dict) and r.get("fill") is not None]
    if not fills:
        return 0
    return round(sum(fills) / len(fills))


def _sum_rows(rows, keys):
    return {k: sum((r[k] for r in rows), ZERO if isinstance(rows[0][k], Decimal) else 0) if rows else 0 for k in keys}


def weekly_dashboard(branches, start) -> dict:
    from apps.website.models import TrialRequest

    end = start + datetime.timedelta(days=6)
    s0, e1 = _range(start, end)
    rows = []
    for b in branches:
        visits = Attendance.objects.filter(session__branch=b, session__date__range=(start, end))
        visitors = set(visits.values_list("member_id", flat=True))
        earlier = set(
            Attendance.objects.filter(member_id__in=visitors, session__date__lt=start)
            .values_list("member_id", flat=True)
            .distinct()
        )
        new_visitors = len(visitors - earlier)
        mix = (
            SaleLine.objects.filter(sale__branch=b, sale__created_at__gte=s0, sale__created_at__lt=e1)
            .values("category")
            .annotate(total=Sum("line_total"))
        )
        leads = TrialRequest.objects.filter(branch=b, created_at__gte=s0, created_at__lt=e1)
        rows.append(
            {
                "branch": b,
                "visits": visits.count(),
                "new_visitors": new_visitors,
                "returning_visitors": len(visitors & earlier),
                "cancellations": Booking.objects.filter(
                    session__branch=b, session__date__range=(start, end), status="cancelled"
                ).count(),
                "late_cancellations": Booking.objects.filter(
                    session__branch=b, session__date__range=(start, end), late_cancellation=True
                ).count(),
                "no_shows": Booking.objects.filter(
                    session__branch=b, session__date__range=(start, end), status="no_show"
                ).count(),
                "mix": {r["category"]: r["total"] or ZERO for r in mix},
                "leads": {s: leads.filter(status=s).count() for s in TrialRequest.Status.values},
            }
        )
    return {"start": start, "end": end, "rows": rows}


def _month_bounds(month):
    import calendar

    return month, month.replace(day=calendar.monthrange(month.year, month.month)[1])


def monthly_dashboard(branches, month) -> dict:
    from apps.payroll.services import previous_month, session_hours

    m0, m1 = _month_bounds(month)
    p0, p1 = _month_bounds(previous_month(month))
    rows = []
    instructors = defaultdict(lambda: Decimal(0))
    for b in branches:

        def sales(a, z, b=b):
            s0, e1 = _range(a, z)
            return (
                SaleLine.objects.filter(sale__branch=b, sale__created_at__gte=s0, sale__created_at__lt=e1).aggregate(
                    t=Sum("line_total")
                )["t"]
                or ZERO
            )

        this_sales, last_sales = sales(m0, m1), sales(p0, p1)
        start_active = active_memberships(m0, b).values_list("member_id", flat=True).distinct()
        end_active = active_memberships(m1, b).values_list("member_id", flat=True).distinct()
        start_set, end_set = set(start_active), set(end_active)
        for s in ClassSession.objects.filter(
            branch=b, date__range=(m0, min(m1, timezone.localdate())), status="scheduled"
        ).prefetch_related("instructors"):
            for u in s.instructors.all():
                instructors[u.full_name] += session_hours(s)
        rows.append(
            {
                "branch": b,
                "sales": this_sales,
                "last_sales": last_sales,
                "growth": (round((this_sales - last_sales) / last_sales * 100, 1) if last_sales else None),
                "active_start": len(start_set),
                "active_end": len(end_set),
                "joined": len(end_set - start_set),
                "left": len(start_set - end_set),
                "churn": round(len(start_set - end_set) / len(start_set) * 100, 1) if start_set else None,
                "visits": Attendance.objects.filter(session__branch=b, session__date__range=(m0, m1)).count(),
            }
        )
    return {
        "month": month,
        "rows": rows,
        "instructors": sorted(((k, v.quantize(Decimal("0.1"))) for k, v in instructors.items()), key=lambda r: -r[1]),
    }


def training_dashboard(branches, start, end) -> dict:
    per_class = (
        Attendance.objects.filter(session__branch__in=branches, session__date__range=(start, end))
        .values("session__title_en", "session__branch__code")
        .annotate(n=Count("id"), sessions=Count("session", distinct=True))
        .order_by("-n")
    )
    per_instructor = (
        Attendance.objects.filter(session__branch__in=branches, session__date__range=(start, end))
        .values("session__instructors__full_name")
        .annotate(n=Count("id"), sessions=Count("session", distinct=True))
        .order_by("-n")
    )
    return {
        "per_class": list(per_class),
        "per_instructor": [r for r in per_instructor if r["session__instructors__full_name"]],
    }


def marketing_dashboard(branches, start, end) -> dict:
    from apps.website.models import TrialRequest

    s0, e1 = _range(start, end)
    leads = TrialRequest.objects.filter(branch__in=branches, created_at__gte=s0, created_at__lt=e1)
    by_source = leads.values("source").annotate(n=Count("id")).order_by("-n")
    trials = Booking.objects.filter(
        session__branch__in=branches, session__date__range=(start, end), is_trial=True
    ).select_related("session")
    attended = [b for b in trials if b.status == "attended"]
    converted = sum(1 for b in attended if _trial_converted(b))
    return {
        "leads": leads.count(),
        "by_source": list(by_source),
        "by_status": {s: leads.filter(status=s).count() for s in TrialRequest.Status.values},
        "trials": trials.exclude(status="cancelled").count(),
        "attended": len(attended),
        "converted": converted,
        "conversion": round(converted / len(attended) * 100) if attended else None,
    }
