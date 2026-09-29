"""
Payroll rules (scope M20, business rule 20, decisions P2-1 to P2-11).

The monthly run is built by the system from what actually happened: classes taught (M4), the
person's own sales (M5), approved leave, advances and the OM's adjustments. The OM checks and
submits it; the Accountant approves it (never their own submission); only then are payslips
and the bank file released. Approved runs are frozen.
"""

import calendar
import datetime
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.messaging import send_message
from apps.core.validators import day_range
from apps.rbac.services import has_perm, notify_perm
from apps.staff.models import StaffDocument, StaffProfile

from .models import (
    ZERO,
    Advance,
    Leave,
    PayAdjustment,
    PayComponent,
    PayProfile,
    PayrollRun,
    PayrollSettings,
    Payslip,
    PayslipLine,
    PublicHoliday,
)

D = Decimal
FRIDAY = 4  # Python weekday; Elite's weekly rest day


def kd(value) -> Decimal:
    return D(value).quantize(D("0.001"), rounding=ROUND_HALF_UP)


def _need(user, perm, message):
    if not has_perm(user, perm):
        raise PermissionDenied(message)


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------
def holidays_between(start, end) -> set:
    return set(PublicHoliday.objects.filter(date__range=(start, end)).values_list("date", flat=True))


def working_days(start, end, holidays=None) -> int:
    """Days between start and end inclusive, not counting Fridays or public holidays."""
    if end < start:
        return 0
    holidays = holidays_between(start, end) if holidays is None else holidays
    n, day = 0, start
    while day <= end:
        if day.weekday() != FRIDAY and day not in holidays:
            n += 1
        day += datetime.timedelta(days=1)
    return n


def month_end(month) -> datetime.date:
    return month.replace(day=calendar.monthrange(month.year, month.month)[1])


def previous_month(month) -> datetime.date:
    return (month.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)


def pay_day(month) -> datetime.date:
    """Last working day of the month for the bank: not Friday or Saturday, not a public holiday."""
    day = month_end(month)
    holidays = holidays_between(month, day)
    while day.weekday() in (FRIDAY, 5) or day in holidays:
        day -= datetime.timedelta(days=1)
    return day


def period_for(month, settings=None) -> tuple[datetime.date, datetime.date]:
    """Classes and sales count from the day after last month's cut-off to this month's cut-off."""
    settings = settings or PayrollSettings.get()
    end = month.replace(day=settings.cutoff_day)
    start = previous_month(month).replace(day=settings.cutoff_day) + datetime.timedelta(days=1)
    return start, end


def overlap(a_start, a_end, b_start, b_end):
    start, end = max(a_start, b_start), min(a_end, b_end)
    return (start, end) if start <= end else None


# ---------------------------------------------------------------------------
# Rates, service and end-of-service
# ---------------------------------------------------------------------------
def monthly_wage(profile: PayProfile, on) -> Decimal:
    """Salary plus fixed allowances in force on a day (the base for daily rate and end-of-service)."""
    return sum(
        (c.amount or ZERO for c in profile.components.all() if c.kind in PayComponent.MONTHLY and c.active_in(on, on)),
        ZERO,
    )


def monthly_salary(profile: PayProfile, on) -> Decimal:
    return sum(
        (
            c.amount or ZERO
            for c in profile.components.all()
            if c.kind == PayComponent.Kind.SALARY and c.active_in(on, on)
        ),
        ZERO,
    )


def daily_rate(monthly, settings) -> Decimal:
    return D(monthly) / D(settings.working_days_per_month)


def hourly_base(profile, on, settings) -> Decimal:
    """Hourly rate for overtime: from the salary, or the person's hourly rate when they have no salary."""
    salary = monthly_salary(profile, on)
    if salary:
        return daily_rate(salary, settings) / D(settings.hours_per_day)
    hourly = [c.amount for c in profile.components.all() if c.kind == PayComponent.Kind.HOURLY and c.amount]
    return hourly[0] if hourly else ZERO


def years_of_service(start, end) -> Decimal:
    if start is None or end < start:
        return D(0)
    return D((end - start).days + 1) / D("365")


def end_of_service(profile: PayProfile, last_day, reason, settings=None) -> dict:
    """
    Kuwait Private Sector Labour Law (settings confirmed by the Accountant): 15 days' pay per year
    for the first five years, a month per year after, capped; on resignation a share by years served.
    """
    settings = settings or PayrollSettings.get()
    staff = profile.staff
    if profile.is_freelance or staff.start_date is None:
        return {"amount": ZERO, "years": D(0), "share": D(0), "wage": ZERO}
    wage = monthly_wage(profile, last_day)
    daily = daily_rate(wage, settings)
    years = years_of_service(staff.start_date, last_day)
    first = min(years, D(5))
    after = max(years - D(5), D(0))
    days = first * settings.eos_days_first_five_years + after * settings.eos_days_after_five_years
    amount = min(daily * days, wage * settings.eos_cap_months)
    share = D(1)
    if reason == "resignation":
        if years < 3:
            share = settings.resign_share_under_3
        elif years < 5:
            share = settings.resign_share_3_to_5
        elif years < 10:
            share = settings.resign_share_5_to_10
        else:
            share = settings.resign_share_10_plus
    return {"amount": kd(amount * share), "years": years.quantize(D("0.01")), "share": share, "wage": wage}


def eos_monthly_accrual(profile: PayProfile, month, settings) -> Decimal:
    """Provision built up this month (shown to Elite, not deducted from the person)."""
    staff = profile.staff
    if profile.is_freelance or staff.start_date is None:
        return ZERO
    end = month_end(month)
    wage = monthly_wage(profile, end)
    per_year = (
        settings.eos_days_first_five_years
        if years_of_service(staff.start_date, end) < 5
        else settings.eos_days_after_five_years
    )
    return kd(daily_rate(wage, settings) * D(per_year) / D(12))


# ---------------------------------------------------------------------------
# Leave balances
# ---------------------------------------------------------------------------
def annual_leave_balance(staff: StaffProfile, on=None, settings=None) -> Decimal:
    """Days earned since starting (entitlement ÷ 12 per month of service) less annual leave taken."""
    on = on or timezone.localdate()
    settings = settings or PayrollSettings.get()
    if staff.start_date is None or staff.employment_type == "freelance":
        return D(0)
    months = D(max((on - staff.start_date).days, 0)) / D("30.4375")
    earned = months * D(settings.annual_leave_days) / D(12)
    taken = (
        Leave.objects.filter(
            staff=staff, kind=Leave.Kind.ANNUAL, status=Leave.Status.APPROVED, start__lte=on
        ).aggregate(t=Sum("days"))["t"]
        or 0
    )
    return (earned - D(taken)).quantize(D("0.1"))


def sick_days_before(staff, day) -> int:
    """Sick working days already taken this calendar year before `day` (for the pay tiers)."""
    total = 0
    for leave in Leave.objects.filter(
        staff=staff,
        kind=Leave.Kind.SICK,
        status=Leave.Status.APPROVED,
        start__lt=day,
        end__gte=day.replace(month=1, day=1),
    ):
        span = overlap(leave.start, leave.end, day.replace(month=1, day=1), day - datetime.timedelta(days=1))
        if span:
            total += working_days(*span)
    return total


def sick_pay_share(day_number: int, settings) -> Decimal:
    """Share of pay for the n-th sick day of the year (1-based)."""
    tiers = [
        (settings.sick_full_pay_days, D(1)),
        (settings.sick_three_quarter_days, D("0.75")),
        (settings.sick_half_pay_days, D("0.5")),
        (settings.sick_quarter_pay_days, D("0.25")),
    ]
    limit = 0
    for days, share in tiers:
        limit += days
        if day_number <= limit:
            return share
    return D(0)


# ---------------------------------------------------------------------------
# What was taught and sold
# ---------------------------------------------------------------------------
def taught_sessions(user, start, end, program=None, kinds=None):
    from apps.classes.models import ClassSession

    qs = ClassSession.objects.filter(
        instructors=user,
        date__range=(start, min(end, timezone.localdate())),
        status=ClassSession.Status.SCHEDULED,
    )
    if program is not None:
        qs = qs.filter(program=program)
    if kinds:
        qs = qs.filter(kind__in=kinds)
    return qs.order_by("date", "start")


def session_hours(session) -> Decimal:
    start = datetime.datetime.combine(session.date, session.start)
    end = datetime.datetime.combine(session.date, session.end)
    return D((end - start).seconds) / D(3600)


def commission_base(user, start, end, categories=None) -> tuple[Decimal, Decimal]:
    """(own sales, refunds of own sales) in the period, by line category (decision P2-6)."""
    from apps.sales.models import Sale, SaleLine

    s0, _ = day_range(start)
    _, e1 = day_range(end)
    lines = SaleLine.objects.filter(sale__created_at__gte=s0, sale__created_at__lt=e1)
    if categories:
        lines = lines.filter(category__in=categories)
    sold = lines.filter(sale__kind=Sale.Kind.SALE, sale__created_by=user).aggregate(t=Sum("line_total"))["t"] or ZERO
    refunded = (
        lines.filter(sale__kind=Sale.Kind.REFUND, sale__refund_of__created_by=user).aggregate(t=Sum("line_total"))["t"]
        or ZERO
    )
    return sold, -refunded


# ---------------------------------------------------------------------------
# Building a payslip
# ---------------------------------------------------------------------------
@dataclass
class Draft:
    lines: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    def add(self, kind, code, label, label_ar, amount, quantity=None, rate=None, source=None):
        amount = kd(amount)
        if amount == 0 and code not in ("salary",):
            return
        self.lines.append(
            {
                "kind": kind,
                "code": code,
                "label": label,
                "label_ar": label_ar,
                "amount": amount,
                "quantity": None if quantity is None else D(quantity).quantize(D("0.01")),
                "rate": None if rate is None else kd(rate),
                "source": source or {},
            }
        )


def _employed_span(staff, start, end):
    s = max(start, staff.start_date) if staff.start_date else start
    e = min(end, staff.end_date) if staff.end_date else end
    return (s, e) if s <= e else None


def build_payslip(profile: PayProfile, run: PayrollRun, settings) -> Draft:
    staff, user = profile.staff, profile.staff.user
    month, m_end = run.month, month_end(run.month)
    d = Draft()
    comps = [c for c in profile.components.all() if c.active_in(run.period_start, m_end)]
    if not comps:
        d.warnings.append("no pay set up")
    employed = _employed_span(staff, month, m_end)
    days_in_month = D((m_end - month).days + 1)
    share = D((employed[1] - employed[0]).days + 1) / days_in_month if employed else D(0)

    # Monthly salary and allowances, pro rata for joiners and leavers.
    for c in comps:
        if c.kind in PayComponent.MONTHLY and c.active_in(month, m_end):
            label = c.name or c.get_kind_display()
            label_ar = c.name_ar or ("الراتب الشهري" if c.kind == PayComponent.Kind.SALARY else "بدل")
            amount = (c.amount or ZERO) * share
            d.add("earning", c.kind, label, label_ar, amount, source={"component": c.pk, "share": str(share)})

    wage = monthly_wage(profile, m_end)
    daily = daily_rate(wage, settings) if wage else ZERO

    # Classes taught: hourly and per-class rates (per program if set).
    for c in comps:
        if c.kind in (PayComponent.Kind.HOURLY, PayComponent.Kind.PER_CLASS):
            sessions = list(taught_sessions(user, run.period_start, run.period_end, c.program, c.session_kinds))
            if c.kind == PayComponent.Kind.HOURLY:
                qty = sum((session_hours(s) for s in sessions), D(0))
                label, label_ar = "Hours taught", "ساعات التدريب"
            else:
                qty = D(len(sessions))
                label, label_ar = "Classes taught", "الحصص المُدرَّسة"
            if c.program_id:
                label += f" · {c.program.name}"
                label_ar += f" · {c.program.name_ar or c.program.name}"
            d.add(
                "earning",
                c.kind,
                label,
                label_ar,
                qty * (c.amount or ZERO),
                quantity=qty,
                rate=c.amount,
                source={"component": c.pk, "sessions": [s.pk for s in sessions]},
            )

    # Commission on the person's own sales, less refunds of those sales.
    for c in comps:
        if c.kind == PayComponent.Kind.COMMISSION and c.percent:
            sold, refunded = commission_base(user, run.period_start, run.period_end, c.sale_categories)
            base = sold - refunded
            d.add(
                "earning",
                "commission",
                f"Commission {c.percent}% on own sales",
                f"عمولة {c.percent}٪ على المبيعات",
                base * c.percent / D(100),
                quantity=None,
                rate=None,
                source={"component": c.pk, "sold": str(sold), "refunded": str(refunded)},
            )

    # The OM's adjustments for the month.
    ot_rate = hourly_base(profile, m_end, settings)
    multipliers = {
        PayAdjustment.Kind.OVERTIME_NORMAL: settings.overtime_normal,
        PayAdjustment.Kind.OVERTIME_REST: settings.overtime_rest_day,
        PayAdjustment.Kind.OVERTIME_HOLIDAY: settings.overtime_holiday,
    }
    for adj in PayAdjustment.objects.filter(staff=staff, month=month):
        label, label_ar = adj.get_kind_display(), _ADJ_AR.get(adj.kind, adj.get_kind_display())
        src = {"adjustment": adj.pk, "note": adj.note}
        if adj.kind in PayAdjustment.HOURS:
            rate = ot_rate * multipliers[adj.kind]
            if not rate:
                d.warnings.append("overtime without a salary or hourly rate")
            d.add("earning", adj.kind, label, label_ar, (adj.quantity or 0) * rate, adj.quantity, rate, src)
        elif adj.kind == PayAdjustment.Kind.ABSENCE:
            d.add("deduction", adj.kind, label, label_ar, (adj.quantity or 0) * daily, adj.quantity, daily, src)
        elif adj.kind in PayAdjustment.DEDUCTIONS:
            d.add("deduction", adj.kind, label, label_ar, adj.amount or ZERO, source=src)
        else:
            d.add("earning", adj.kind, label, label_ar, adj.amount or ZERO, source=src)

    # Unpaid and sick leave in the calendar month.
    for leave in Leave.objects.filter(
        staff=staff,
        status=Leave.Status.APPROVED,
        kind__in=[Leave.Kind.UNPAID, Leave.Kind.SICK],
        start__lte=m_end,
        end__gte=month,
    ):
        span = overlap(leave.start, leave.end, month, m_end)
        if not span:
            continue
        if leave.kind == Leave.Kind.UNPAID:
            days = working_days(*span)
            d.add(
                "deduction",
                "unpaid_leave",
                "Unpaid leave",
                "إجازة بدون راتب",
                days * daily,
                days,
                daily,
                {"leave": leave.pk},
            )
        else:
            already = sick_days_before(staff, span[0])
            lost = D(0)
            day, n = span[0], already
            holidays = holidays_between(*span)
            while day <= span[1]:
                if day.weekday() != FRIDAY and day not in holidays:
                    n += 1
                    lost += D(1) - sick_pay_share(n, settings)
                day += datetime.timedelta(days=1)
            if lost:
                d.add(
                    "deduction",
                    "sick_leave",
                    "Sick leave beyond full pay",
                    "إجازة مرضية تتجاوز الأجر الكامل",
                    lost * daily,
                    lost,
                    daily,
                    {"leave": leave.pk},
                )

    # Final pay for a leaver: end-of-service and unused annual leave.
    if staff.end_date and month <= staff.end_date <= m_end and not profile.is_freelance:
        eos = end_of_service(profile, staff.end_date, staff.end_reason or "termination", settings)
        d.add(
            "earning",
            "eos",
            f"End-of-service indemnity ({eos['years']} years)",
            f"مكافأة نهاية الخدمة ({eos['years']} سنة)",
            eos["amount"],
            source={k: str(v) for k, v in eos.items()},
        )
        balance = annual_leave_balance(staff, staff.end_date, settings)
        if balance > 0:
            d.add(
                "earning",
                "leave_pay",
                "Unused annual leave",
                "رصيد الإجازة السنوية غير المستخدم",
                balance * daily,
                balance,
                daily,
            )

    # Salary advances: this month's instalment.
    for adv in Advance.objects.filter(staff=staff, status=Advance.Status.APPROVED, first_month__lte=month):
        if adv.outstanding > 0:
            amount = min(adv.instalment, adv.outstanding)
            d.add("deduction", "advance", "Salary advance repayment", "سداد سلفة", amount, source={"advance": adv.pk})

    # PIFSS for Kuwaiti staff.
    if profile.pifss_applies:
        base = sum(
            (
                (c.amount or ZERO) * share
                for c in comps
                if c.kind in PayComponent.MONTHLY and c.counts_for_pifss and c.active_in(month, m_end)
            ),
            ZERO,
        )
        base = min(base, settings.pifss_salary_cap)
        d.add(
            "deduction",
            "pifss",
            f"PIFSS social security ({settings.pifss_employee_percent}%)",
            f"التأمينات الاجتماعية ({settings.pifss_employee_percent}٪)",
            base * settings.pifss_employee_percent / D(100),
            source={"base": str(base)},
        )
        d.add(
            "employer",
            "pifss_employer",
            f"PIFSS paid by Elite ({settings.pifss_employer_percent}%)",
            f"حصة إيليت في التأمينات ({settings.pifss_employer_percent}٪)",
            base * settings.pifss_employer_percent / D(100),
            source={"base": str(base)},
        )
    accrual = eos_monthly_accrual(profile, month, settings)
    if accrual and not (staff.end_date and staff.end_date < month):
        d.add("employer", "eos_accrual", "End-of-service provision this month", "مخصص نهاية الخدمة لهذا الشهر", accrual)

    if not profile.iban:
        d.warnings.append("no IBAN")
    return d


_ADJ_AR = {
    "ot_normal": "عمل إضافي — يوم عادي (ساعات)",
    "ot_rest": "عمل إضافي — يوم راحة (ساعات)",
    "ot_holiday": "عمل إضافي — عطلة رسمية (ساعات)",
    "bonus": "مكافأة",
    "extra": "حصص أو ندوات أو معسكرات إضافية",
    "addition": "إضافة أخرى",
    "absence": "غياب (أيام مخصومة)",
    "deduction": "خصم آخر",
}


def payable_profiles(month):
    m_end = month_end(month)
    return (
        PayProfile.objects.filter(
            Q(staff__start_date__isnull=True) | Q(staff__start_date__lte=m_end),
            Q(staff__end_date__isnull=True) | Q(staff__end_date__gte=month),
        )
        .select_related("staff__user", "staff__primary_branch")
        .prefetch_related("components__program")
    )


# ---------------------------------------------------------------------------
# The monthly run
# ---------------------------------------------------------------------------
@transaction.atomic
def build_run(month, user) -> PayrollRun:
    """Creates or rebuilds the draft run for a month from live data."""
    _need(user, "payroll.prepare", "Only the Operations Manager prepares payroll.")
    month = month.replace(day=1)
    settings = PayrollSettings.get()
    start, end = period_for(month, settings)
    run = PayrollRun.objects.select_for_update().filter(month=month).first()
    if run is not None and run.status != PayrollRun.Status.DRAFT:
        raise ValidationError("This run has been submitted. The Accountant must return it before it can be rebuilt.")
    if run is None:
        run = PayrollRun.objects.create(
            month=month, period_start=start, period_end=end, pay_date=pay_day(month), created_by=user, updated_by=user
        )
    run.payslips.all().delete()
    run.period_start, run.period_end, run.pay_date = start, end, pay_day(month)
    run.built_at, run.updated_by, run.return_note = timezone.now(), user, ""
    warnings = []
    if not settings.confirmed:
        warnings.append({"code": "settings", "text": "The Accountant has not confirmed the payroll rules yet."})
    last_approved = (
        PayrollRun.objects.filter(status__in=[PayrollRun.Status.APPROVED, PayrollRun.Status.PAID])
        .exclude(pk=run.pk)
        .order_by("-month")
        .first()
    )
    for profile in payable_profiles(month):
        draft = build_payslip(profile, run, settings)
        staff = profile.staff
        slip = Payslip.objects.create(
            run=run,
            staff=staff,
            branch=staff.primary_branch,
            full_name=staff.user.full_name,
            full_name_ar=staff.user.full_name_ar,
            job_title=staff.job_title,
            job_title_ar=staff.job_title_ar,
            employment_type=staff.employment_type,
            iban_last4=profile.iban_last4,
        )
        PayslipLine.objects.bulk_create([PayslipLine(payslip=slip, **line) for line in draft.lines])
        _total(slip)
        name = staff.user.full_name
        for w in draft.warnings:
            warnings.append({"code": w, "text": f"{name}: {w}.", "staff": staff.pk})
        if slip.gross == 0 and draft.lines == [] and profile.components.exists():
            warnings.append({"code": "zero", "text": f"{name}: nothing to pay this month.", "staff": staff.pk})
        if slip.net < 0:
            warnings.append({"code": "negative", "text": f"{name}: deductions are more than pay.", "staff": staff.pk})
        if last_approved is not None and last_approved.approved_at:
            changed = (
                profile.updated_at > last_approved.approved_at
                or profile.components.filter(updated_at__gt=last_approved.approved_at).exists()
            )
            if changed:
                warnings.append(
                    {
                        "code": "terms_changed",
                        "text": f"{name}: pay terms changed since the last run.",
                        "staff": staff.pk,
                    }
                )
        pending = Leave.objects.filter(
            staff=staff, status=Leave.Status.PENDING, start__lte=month_end(month), end__gte=month
        ).exists()
        if pending:
            warnings.append(
                {"code": "pending_leave", "text": f"{name}: leave waiting for a decision.", "staff": staff.pk}
            )
    run.warnings = warnings
    run.save()
    record_event(action="payroll_built", instance=run, changes={"people": run.payslips.count()})
    return run


def _total(slip: Payslip):
    lines = list(slip.lines.all())
    slip.gross = kd(sum((line.amount for line in lines if line.kind == "earning"), ZERO))
    slip.deductions = kd(sum((line.amount for line in lines if line.kind == "deduction"), ZERO))
    slip.net = slip.gross - slip.deductions
    slip.employer_pifss = kd(sum((line.amount for line in lines if line.code == "pifss_employer"), ZERO))
    slip.eos_accrual = kd(sum((line.amount for line in lines if line.code == "eos_accrual"), ZERO))
    slip.save()


def run_totals(run: PayrollRun) -> dict:
    agg = run.payslips.aggregate(
        gross=Sum("gross"),
        deductions=Sum("deductions"),
        net=Sum("net"),
        pifss=Sum("employer_pifss"),
        eos=Sum("eos_accrual"),
    )
    out = {k: v or ZERO for k, v in agg.items()}
    out["people"] = run.payslips.count()
    out["cost"] = out["gross"] + out["pifss"]
    return out


BLOCKING = ("negative",)


@transaction.atomic
def submit_run(run: PayrollRun, user) -> PayrollRun:
    run = PayrollRun.objects.select_for_update().get(pk=run.pk)
    _need(user, "payroll.prepare", "Only the Operations Manager submits payroll.")
    if run.status != PayrollRun.Status.DRAFT:
        raise ValidationError("Only a draft run can be submitted.")
    blocking = [w["text"] for w in run.warnings if w["code"] in BLOCKING]
    if blocking:
        raise ValidationError("Fix these before submitting: " + " ".join(blocking))
    if not run.payslips.exists():
        raise ValidationError("There is nobody on this run.")
    run.status, run.submitted_by, run.submitted_at, run.updated_by = (
        PayrollRun.Status.SUBMITTED,
        user,
        timezone.now(),
        user,
    )
    run.save()
    record_event(action="payroll_submitted", instance=run)
    text = f"Payroll {run.month:%B %Y} submitted by {user.full_name} for approval: {run_totals(run)['net']:.3f} KD net."
    transaction.on_commit(lambda: notify_perm("payroll.approve", text, exclude=user))
    return run


@transaction.atomic
def return_run(run: PayrollRun, user, note: str) -> PayrollRun:
    run = PayrollRun.objects.select_for_update().get(pk=run.pk)
    _need(user, "payroll.approve", "Only the Accountant returns payroll.")
    if run.status != PayrollRun.Status.SUBMITTED:
        raise ValidationError("Only a submitted run can be returned.")
    if not note.strip():
        raise ValidationError("Say what needs correcting.")
    run.status, run.return_note, run.updated_by = PayrollRun.Status.DRAFT, note.strip()[:255], user
    run.save()
    record_event(action="payroll_returned", instance=run, changes={"note": run.return_note})
    submitter = run.submitted_by
    if submitter and submitter.mobile:
        transaction.on_commit(
            lambda: send_message(submitter.mobile, f"Payroll {run.month:%B %Y} was returned: {run.return_note}")
        )
    return run


@transaction.atomic
def approve_run(run: PayrollRun, user) -> PayrollRun:
    run = PayrollRun.objects.select_for_update().get(pk=run.pk)
    _need(user, "payroll.approve", "Only the Accountant approves payroll.")
    if run.status != PayrollRun.Status.SUBMITTED:
        raise ValidationError("Only a submitted run can be approved.")
    if user.pk in (run.submitted_by_id, run.created_by_id):
        raise PermissionDenied("Someone else must approve a payroll run you prepared or submitted.")
    if not PayrollSettings.get().confirmed:
        raise ValidationError("Confirm the payroll rules (overtime, end-of-service, PIFSS, leave) first.")
    # Take the advance instalments now that the run is final.
    for line in PayslipLine.objects.filter(payslip__run=run, code="advance"):
        adv = Advance.objects.select_for_update().get(pk=line.source["advance"])
        adv.repaid = min(adv.amount, adv.repaid + line.amount)
        if adv.repaid >= adv.amount:
            adv.status = Advance.Status.REPAID
        adv.save(update_fields=["repaid", "status", "updated_at"])
    run.status, run.approved_by, run.approved_at, run.updated_by = (
        PayrollRun.Status.APPROVED,
        user,
        timezone.now(),
        user,
    )
    run.save()
    totals = run_totals(run)
    record_event(action="payroll_approved", instance=run, changes={k: str(v) for k, v in totals.items()})
    transaction.on_commit(lambda: _after_approval(run.pk))
    return run


def _after_approval(run_id):
    run = PayrollRun.objects.get(pk=run_id)
    for slip in run.payslips.select_related("staff__user"):
        u = slip.staff.user
        if u.mobile:
            lang = getattr(u, "preferred_language", "en")
            text = (
                f"قسيمة راتب {run.month:%m/%Y} جاهزة في المكتب. الصافي {slip.net:.3f} د.ك."
                if lang == "ar"
                else f"Your payslip for {run.month:%B %Y} is ready in the desk. Net pay {slip.net:.3f} KD."
            )
            send_message(u.mobile, text)
        Payslip.objects.filter(pk=slip.pk).update(sent_at=timezone.now())
    totals = run_totals(run)
    from apps.operations.services import _ceo_users

    for ceo in _ceo_users():
        if ceo.mobile:
            send_message(
                ceo.mobile,
                f"Payroll {run.month:%B %Y} approved: {totals['people']} people, {totals['net']:.3f} KD net, "
                f"cost to Elite {totals['cost']:.3f} KD.",
            )


@transaction.atomic
def mark_paid(run: PayrollRun, user) -> PayrollRun:
    run = PayrollRun.objects.select_for_update().get(pk=run.pk)
    _need(user, "payroll.approve", "Only the Accountant marks payroll as paid.")
    if run.status != PayrollRun.Status.APPROVED:
        raise ValidationError("Only an approved run can be marked as paid.")
    run.status, run.paid_by, run.paid_at, run.updated_by = PayrollRun.Status.PAID, user, timezone.now(), user
    run.save()
    record_event(action="payroll_paid", instance=run)
    return run


def bank_rows(run: PayrollRun) -> list[dict]:
    """Salary transfer file (decision P2-11): standard columns until the bank is named."""
    if not run.is_locked:
        raise ValidationError("The bank file is available only after the Accountant approves the run.")
    rows = []
    for slip in run.payslips.select_related("staff__pay", "staff__user").order_by("full_name"):
        pay = slip.staff.pay
        if slip.net <= 0:
            continue
        rows.append(
            {
                "name": pay.account_name or slip.full_name,
                "iban": pay.iban,
                "bank": pay.bank_name,
                "amount": slip.net,
                "currency": "KWD",
                "reference": f"{run.reference} {slip.full_name}"[:35],
            }
        )
    return rows


def summary(run: PayrollRun) -> dict:
    """Payroll summary per branch and per function (job title)."""
    by_branch, by_function = {}, {}
    for slip in run.payslips.select_related("branch"):
        b = slip.branch.name if slip.branch_id else "Both branches"
        for bucket, key in ((by_branch, b), (by_function, slip.job_title)):
            row = bucket.setdefault(key, {"people": 0, "gross": ZERO, "net": ZERO, "cost": ZERO})
            row["people"] += 1
            row["gross"] += slip.gross
            row["net"] += slip.net
            row["cost"] += slip.cost
    return {"branch": by_branch, "function": by_function}


def payroll_cost(start, end, branch=None) -> Decimal:
    """Approved payroll cost (gross + Elite's PIFSS) for months inside a period (income statement)."""
    slips = Payslip.objects.filter(
        run__status__in=[PayrollRun.Status.APPROVED, PayrollRun.Status.PAID], run__month__range=(start, end)
    )
    if branch is not None:
        slips = slips.filter(branch=branch)
    agg = slips.aggregate(g=Sum("gross"), p=Sum("employer_pifss"))
    return (agg["g"] or ZERO) + (agg["p"] or ZERO)


# ---------------------------------------------------------------------------
# Pay set-up, adjustments, leave and advances
# ---------------------------------------------------------------------------
def can_edit_pay(user, staff: StaffProfile) -> bool:
    """The OM sets pay; nobody sets their own; the CEO can set anyone's (including the OM's)."""
    if staff.user_id == user.pk:
        return False
    return has_perm(user, "payroll.prepare") or (
        has_perm(user, "staff.manage") and has_perm(user, "payroll.view") and not has_perm(user, "payroll.approve")
    )


def _check_edit(user, staff):
    if not can_edit_pay(user, staff):
        raise PermissionDenied("You cannot change this person's pay (nobody sets their own pay).")


@transaction.atomic
def save_pay_profile(staff: StaffProfile, user, **data) -> PayProfile:
    _check_edit(user, staff)
    profile, _ = PayProfile.objects.get_or_create(staff=staff, defaults={"created_by": user})
    for k, v in data.items():
        setattr(profile, k, v)
    profile.updated_by = user
    profile.full_clean()
    profile.save()
    return profile


@transaction.atomic
def save_component(profile: PayProfile, user, component: PayComponent | None = None, **data) -> PayComponent:
    _check_edit(user, profile.staff)
    component = component or PayComponent(profile=profile, created_by=user)
    for k, v in data.items():
        setattr(component, k, v)
    kind = component.kind
    if kind == PayComponent.Kind.COMMISSION:
        if not component.percent or component.percent <= 0 or component.percent > 100:
            raise ValidationError("Enter a commission percentage between 0 and 100.")
    elif not component.amount or component.amount <= 0:
        raise ValidationError("Enter an amount above zero.")
    if kind == PayComponent.Kind.ALLOWANCE and not component.name.strip():
        raise ValidationError("Name the allowance (e.g. Transport).")
    if component.valid_to and component.valid_to < component.valid_from:
        raise ValidationError("The end date must be after the start date.")
    component.updated_by = user
    component.save()
    return component


@transaction.atomic
def end_component(component: PayComponent, user, last_day) -> PayComponent:
    _check_edit(user, component.profile.staff)
    component.valid_to, component.updated_by = last_day, user
    component.save(update_fields=["valid_to", "updated_by", "updated_at"])
    return component


def _open_month(month):
    run = PayrollRun.objects.filter(month=month).first()
    if run is not None and run.status != PayrollRun.Status.DRAFT:
        raise ValidationError(f"Payroll for {month:%B %Y} has been submitted; it can no longer be changed.")


@transaction.atomic
def add_adjustment(staff: StaffProfile, user, *, month, kind, quantity=None, amount=None, note="") -> PayAdjustment:
    _need(user, "payroll.prepare", "Only the Operations Manager adds pay adjustments.")
    if staff.user_id == user.pk:
        raise PermissionDenied("You cannot add pay adjustments for yourself.")
    month = month.replace(day=1)
    _open_month(month)
    if not note.strip():
        raise ValidationError("Write the reason (it appears on the payslip record).")
    if kind in PayAdjustment.HOURS or kind in PayAdjustment.DAYS:
        if not quantity or quantity <= 0:
            raise ValidationError("Enter the number of hours or days.")
        amount = None
    else:
        if not amount or amount <= 0:
            raise ValidationError("Enter the amount.")
        quantity = None
    return PayAdjustment.objects.create(
        staff=staff,
        month=month,
        kind=kind,
        quantity=quantity,
        amount=amount,
        note=note.strip(),
        created_by=user,
        updated_by=user,
    )


@transaction.atomic
def remove_adjustment(adjustment: PayAdjustment, user):
    _need(user, "payroll.prepare", "Only the Operations Manager changes pay adjustments.")
    _open_month(adjustment.month)
    record_event(action="pay_adjustment_removed", instance=adjustment, changes={"kind": adjustment.kind})
    adjustment.delete()


def affected_classes(leave: Leave):
    """Classes the person teaches during the leave: they need cover (M4 class changes)."""
    from apps.classes.models import ClassSession

    return ClassSession.objects.filter(
        instructors=leave.staff.user, date__range=(leave.start, leave.end), status=ClassSession.Status.SCHEDULED
    ).order_by("date", "start")


@transaction.atomic
def request_leave(staff: StaffProfile, user, *, kind, start, end, reason="") -> Leave:
    if staff.user_id != user.pk and not has_perm(user, "leave.approve"):
        raise PermissionDenied("You can request leave only for yourself.")
    if not has_perm(user, "payroll.self") and staff.user_id == user.pk:
        raise PermissionDenied("You cannot request leave.")
    if end < start:
        raise ValidationError("The leave must end on or after the day it starts.")
    if staff.employment_type == "freelance" and kind != Leave.Kind.UNPAID:
        raise ValidationError("Freelance coaches have no paid leave (decision P2-7).")
    clash = Leave.objects.filter(
        staff=staff, status__in=[Leave.Status.PENDING, Leave.Status.APPROVED], start__lte=end, end__gte=start
    ).exists()
    if clash:
        raise ValidationError("There is already leave for some of these days.")
    days = working_days(start, end)
    if days == 0:
        raise ValidationError("Those days are all Fridays or public holidays.")
    if kind == Leave.Kind.ANNUAL and D(days) > annual_leave_balance(staff, end):
        raise ValidationError(f"Only {annual_leave_balance(staff, end)} days of annual leave are available.")
    leave = Leave.objects.create(
        staff=staff, kind=kind, start=start, end=end, days=days, reason=reason.strip(), created_by=user, updated_by=user
    )
    text = f"Leave request: {staff.user.full_name}, {leave.get_kind_display()} {start:%d/%m}–{end:%d/%m} ({days} days)."
    transaction.on_commit(lambda: notify_perm("leave.approve", text, exclude=staff.user))
    return leave


@transaction.atomic
def decide_leave(leave: Leave, user, approve: bool, note="") -> Leave:
    leave = Leave.objects.select_for_update().get(pk=leave.pk)
    _need(user, "leave.approve", "Only the Operations Manager or Training Lead decides leave.")
    if leave.staff.user_id == user.pk:
        raise PermissionDenied("Someone else must decide your own leave.")
    if leave.status != Leave.Status.PENDING:
        raise ValidationError("This request has already been decided.")
    _open_month(leave.start.replace(day=1))
    if approve and leave.kind == Leave.Kind.ANNUAL and D(leave.days) > annual_leave_balance(leave.staff, leave.end):
        raise ValidationError("Not enough annual leave left.")
    leave.status = Leave.Status.APPROVED if approve else Leave.Status.REJECTED
    leave.decided_by, leave.decided_at, leave.decision_note, leave.updated_by = user, timezone.now(), note.strip(), user
    leave.save()
    u = leave.staff.user
    if u.mobile:
        verdict = "approved" if approve else "not approved"
        dates = f"{leave.start:%d/%m}–{leave.end:%d/%m}"
        text = f"Your {leave.get_kind_display().lower()} {dates} was {verdict}. {note}".strip()
        transaction.on_commit(lambda: send_message(u.mobile, text))
    return leave


@transaction.atomic
def request_advance(staff: StaffProfile, user, *, amount, instalments, reason, first_month) -> Advance:
    if staff.user_id != user.pk:
        raise PermissionDenied("You can request an advance only for yourself.")
    if not reason.strip():
        raise ValidationError("Write the reason.")
    if Advance.objects.filter(staff=staff, status__in=[Advance.Status.PENDING, Advance.Status.APPROVED]).exists():
        raise ValidationError("You already have an advance waiting or being repaid.")
    if first_month.replace(day=1) < timezone.localdate().replace(day=1):
        raise ValidationError("Repayment cannot start in a past month.")
    adv = Advance.objects.create(
        staff=staff,
        amount=amount,
        instalments=instalments,
        reason=reason.strip(),
        first_month=first_month.replace(day=1),
        created_by=user,
        updated_by=user,
    )
    text = f"Salary advance request: {staff.user.full_name}, {amount:.3f} KD over {instalments} month(s)."
    transaction.on_commit(lambda: notify_perm("payroll.prepare", text, exclude=user))
    return adv


@transaction.atomic
def decide_advance(adv: Advance, user, approve: bool) -> Advance:
    adv = Advance.objects.select_for_update().get(pk=adv.pk)
    _need(user, "payroll.prepare", "Only the Operations Manager approves salary advances (decision P2-10).")
    if adv.staff.user_id == user.pk:
        raise PermissionDenied("Someone else must decide your own advance.")
    if adv.status != Advance.Status.PENDING:
        raise ValidationError("This advance has already been decided.")
    adv.status = Advance.Status.APPROVED if approve else Advance.Status.REJECTED
    adv.decided_by, adv.decided_at, adv.updated_by = user, timezone.now(), user
    adv.save()
    return adv


@transaction.atomic
def confirm_settings(user, note="", **values) -> PayrollSettings:
    _need(user, "payroll.approve", "Only the Accountant confirms the payroll rules.")
    s = PayrollSettings.objects.select_for_update().get(pk=PayrollSettings.get().pk)
    for k, v in values.items():
        setattr(s, k, v)
    s.full_clean()
    s.confirmed_by, s.confirmed_at, s.confirmation_note, s.updated_by = user, timezone.now(), note.strip()[:255], user
    s.save()
    record_event(action="payroll_rules_confirmed", instance=s, changes={k: str(v) for k, v in values.items()})
    return s


# ---------------------------------------------------------------------------
# Daily job: document expiry reminders (60, 30 and 7 days before)
# ---------------------------------------------------------------------------
def remind_expiring_documents(today=None) -> int:
    today = today or timezone.localdate()
    sent = 0
    horizon = today + datetime.timedelta(days=max(StaffDocument.REMIND_DAYS))
    for doc in StaffDocument.objects.filter(
        expires_on__range=(today, horizon), staff__user__is_active=True
    ).select_related("staff__user"):
        left = (doc.expires_on - today).days
        due = [d for d in StaffDocument.REMIND_DAYS if left <= d and d not in doc.reminders_sent]
        if not due:
            continue
        doc.reminders_sent = sorted(set(doc.reminders_sent) | set(due), reverse=True)
        doc.save(update_fields=["reminders_sent", "updated_at"])
        who = doc.staff.user.full_name
        text = f"{doc.get_kind_display()} of {who} expires on {doc.expires_on:%d/%m/%Y} ({left} days)."
        if doc.staff.user.mobile:
            send_message(doc.staff.user.mobile, text)
        notify_perm("staff.manage", text, exclude=doc.staff.user)
        sent += 1
    return sent
