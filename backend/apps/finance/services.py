"""
Finance rules (scope M11, decisions P2-12 and P2-17).

- Expenses: recorded at the branch with a receipt photo (or a reason there is none), approved
  by the OM or the Accountant (never the person who recorded it). Cash paid out of the drawer is
  taken off the cash expected at that day's cash-up, so it can't be recorded after the cash-up.
- Vendor invoices: the Accountant records, the OM approves, the Accountant pays.
- Income statement: services and products, refunds, expenses, payroll and purchases; the
  headline sales from the verified weekly reports must agree with trading income or the
  difference is explained before the statement is finalised.
"""

import datetime
from collections import OrderedDict, defaultdict
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.files import clean_document
from apps.core.validators import day_range
from apps.organization.models import Branch
from apps.rbac.services import has_perm
from apps.sales.models import CashUp, Sale, SaleLine

from .models import Expense, IncomeStatement, VendorInvoice

ZERO = Decimal("0.000")
PRODUCTS = {SaleLine.Category.EQUIPMENT}


def _need(user, perm, branch_id, message):
    if not has_perm(user, perm, branch_id):
        raise PermissionDenied(message)


def _range(start, end):
    return day_range(start)[0], day_range(end)[1]


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
def _week_verified(branch, day) -> bool:
    from apps.reports.models import WeeklyReport, week_start

    return WeeklyReport.objects.filter(
        kind=WeeklyReport.Kind.SALES, branch=branch, week_start=week_start(day), status=WeeklyReport.Status.VERIFIED
    ).exists()


@transaction.atomic
def record_expense(
    branch,
    user,
    *,
    date,
    description,
    paid_to,
    category,
    amount,
    paid_from=Expense.PaidFrom.DRAWER,
    receipt=None,
    no_receipt_reason="",
) -> Expense:
    _need(user, "finance.expense", branch.pk, "You cannot record expenses for this branch.")
    today = timezone.localdate()
    if date > today:
        raise ValidationError("An expense cannot be dated in the future.")
    if _week_verified(branch, date):
        raise ValidationError("That week's sales report is already verified. Ask the OM to record it this week.")
    if paid_from == Expense.PaidFrom.DRAWER:
        closed = CashUp.objects.filter(branch=branch, date=date).exclude(status=CashUp.Status.DRAFT).exists()
        if closed:
            raise ValidationError("The cash-up for that day is already submitted. Record the expense on today's date.")
    if amount is None or amount <= 0:
        raise ValidationError("Enter the amount.")
    if receipt is None and not no_receipt_reason.strip():
        raise ValidationError("Attach a photo of the receipt, or say why there is none.")
    expense = Expense(
        branch=branch,
        date=date,
        description=description.strip(),
        paid_to=paid_to.strip(),
        category=category,
        amount=amount,
        paid_from=paid_from,
        no_receipt_reason=no_receipt_reason.strip() if receipt is None else "",
        created_by=user,
        updated_by=user,
    )
    if receipt is not None:
        expense.receipt.save("receipt", clean_document(receipt), save=False)
    expense.full_clean()
    expense.save()
    return expense


@transaction.atomic
def decide_expense(expense: Expense, user, approve: bool, note="") -> Expense:
    expense = Expense.objects.select_for_update().get(pk=expense.pk)
    _need(user, "finance.expense_approve", expense.branch_id, "Only the OM or the Accountant approves expenses.")
    if expense.created_by_id == user.pk:
        raise PermissionDenied("Someone else must approve an expense you recorded.")
    if expense.status != Expense.Status.PENDING:
        raise ValidationError("This expense has already been decided.")
    if not approve and not note.strip():
        raise ValidationError("Say why the expense is rejected.")
    expense.status = Expense.Status.APPROVED if approve else Expense.Status.REJECTED
    expense.decided_by, expense.decided_at, expense.decision_note, expense.updated_by = (
        user,
        timezone.now(),
        note.strip()[:255],
        user,
    )
    expense.save()
    return expense


# ---------------------------------------------------------------------------
# Vendor invoices
# ---------------------------------------------------------------------------
@transaction.atomic
def record_invoice(user, *, vendor, number, date, description, amount, currency="KWD", exchange_rate=1, **extra):
    _need(user, "finance.manage", None, "Only the Accountant records vendor invoices.")
    document = extra.pop("document", None)
    currency = (currency or "KWD").upper()
    rate = Decimal(str(exchange_rate or 1))
    if currency == "KWD":
        rate = Decimal(1)
    if rate <= 0:
        raise ValidationError("Enter the exchange rate (KWD for one unit of the invoice currency).")
    if VendorInvoice.objects.filter(vendor=vendor, number=number.strip()).exists():
        raise ValidationError("This vendor's invoice number is already recorded.")
    inv = VendorInvoice(
        vendor=vendor,
        number=number.strip(),
        date=date,
        description=description.strip(),
        amount=amount,
        currency=currency,
        exchange_rate=rate,
        amount_kwd=(Decimal(amount) * rate).quantize(Decimal("0.001")),
        created_by=user,
        updated_by=user,
        **extra,
    )
    if document is not None:
        inv.document.save("invoice", clean_document(document), save=False)
    inv.full_clean()
    inv.save()
    return inv


@transaction.atomic
def approve_invoice(inv: VendorInvoice, user, approve=True, note="") -> VendorInvoice:
    inv = VendorInvoice.objects.select_for_update().get(pk=inv.pk)
    _need(user, "inventory.approve", inv.branch_id, "Only the Operations Manager approves vendor invoices.")
    if inv.created_by_id == user.pk:
        raise PermissionDenied("Someone else must approve an invoice you recorded.")
    if inv.status != VendorInvoice.Status.RECORDED:
        raise ValidationError("This invoice has already been decided.")
    inv.status = VendorInvoice.Status.APPROVED if approve else VendorInvoice.Status.REJECTED
    inv.approved_by, inv.approved_at, inv.note, inv.updated_by = user, timezone.now(), note.strip()[:255], user
    inv.save()
    return inv


@transaction.atomic
def pay_invoice(inv: VendorInvoice, user, *, paid_on, method, reference="") -> VendorInvoice:
    inv = VendorInvoice.objects.select_for_update().get(pk=inv.pk)
    _need(user, "finance.manage", None, "Only the Accountant records payments.")
    if inv.status != VendorInvoice.Status.APPROVED:
        raise ValidationError("Only an approved invoice can be paid.")
    inv.status, inv.paid_on, inv.paid_method, inv.paid_reference, inv.updated_by = (
        VendorInvoice.Status.PAID,
        paid_on,
        method,
        reference.strip(),
        user,
    )
    inv.save()
    return inv


# ---------------------------------------------------------------------------
# Reconciliation (cash-up and terminal settlements)
# ---------------------------------------------------------------------------
def reconciliation(branches, start, end) -> list[dict]:
    from apps.reports.services import _python_open_days

    rows = []
    cash_ups = {(c.branch_id, c.date): c for c in CashUp.objects.filter(branch__in=branches, date__range=(start, end))}
    day = start
    while day <= min(end, timezone.localdate()):
        for b in branches:
            c = cash_ups.get((b.pk, day))
            if c is None and day.weekday() not in _python_open_days(b):
                continue
            flags = []
            if c is None or c.status == CashUp.Status.DRAFT:
                flags.append("missing")
            else:
                for d in (c.cash_difference, c.knet_difference, c.card_difference):
                    if d is not None and d != 0:
                        flags.append("difference")
                        break
                if c.status == CashUp.Status.SUBMITTED:
                    flags.append("unverified")
            rows.append({"date": day, "branch": b, "cash_up": c, "flags": flags})
        day += datetime.timedelta(days=1)
    return rows


# ---------------------------------------------------------------------------
# Revenue and the income statement
# ---------------------------------------------------------------------------
def _lines(start, end, branch=None):
    s0, e1 = _range(start, end)
    qs = SaleLine.objects.filter(sale__created_at__gte=s0, sale__created_at__lt=e1)
    if branch is not None:
        qs = qs.filter(sale__branch=branch)
    return qs


def revenue(start, end, branches) -> dict:
    """By category (services vs products), program, branch and month."""
    lines = (
        _lines(start, end)
        .filter(sale__branch__in=branches)
        .select_related("sale__branch", "pricing_option")
        .prefetch_related("pricing_option__programs")
    )
    by_category, by_program, by_branch, by_month = (
        defaultdict(lambda: ZERO),
        defaultdict(lambda: ZERO),
        defaultdict(lambda: ZERO),
        OrderedDict(),
    )
    services = products = ZERO
    for line in lines:
        amount = line.line_total
        by_category[line.category] += amount
        by_branch[line.sale.branch.name] += amount
        month = timezone.localtime(line.sale.created_at).date().replace(day=1)
        by_month[month] = by_month.get(month, ZERO) + amount
        if line.category in PRODUCTS:
            products += amount
        else:
            services += amount
        if line.pricing_option_id:
            progs = list(line.pricing_option.programs.all())
            label = progs[0].name if len(progs) == 1 else line.pricing_option.name
        else:
            label = "Equipment" if line.category in PRODUCTS else line.description
        by_program[label] += amount
    return {
        "services": services,
        "products": products,
        "total": services + products,
        "by_category": dict(by_category),
        "by_program": sorted(by_program.items(), key=lambda r: -r[1]),
        "by_branch": dict(by_branch),
        "by_month": list(by_month.items()),
    }


def headline_sales(start, end, branch=None) -> tuple[Decimal, list]:
    """Sales as reported in the verified FRM-06 reports, for the days inside the period."""
    from apps.reports.models import WeeklyReport, week_start

    total, unverified = ZERO, []
    week = week_start(start)
    branches = [branch] if branch else list(Branch.objects.filter(is_active=True))
    while week <= end:
        for b in branches:
            report = WeeklyReport.objects.filter(
                kind=WeeklyReport.Kind.SALES, branch=b, week_start=week, status=WeeklyReport.Status.VERIFIED
            ).first()
            if report is None:
                if week + datetime.timedelta(days=6) < timezone.localdate():
                    unverified.append(f"{b.code} {week:%d/%m}")
                continue
            for row in report.data.get("rows", []):
                day = datetime.date.fromisoformat(row["date"])
                if start <= day <= end:
                    total += Decimal(row["amount"])
        week += datetime.timedelta(days=7)
    return total, unverified


EXPENSE_LABELS = dict(Expense.Category.choices)


def income_statement(start, end, branch=None) -> dict:
    from apps.payroll.services import payroll_cost

    lines = _lines(start, end, branch)
    sales = lines.filter(sale__kind=Sale.Kind.SALE)
    refunds = lines.filter(sale__kind=Sale.Kind.REFUND)
    services = sales.exclude(category__in=PRODUCTS).aggregate(t=Sum("line_total"))["t"] or ZERO
    products = sales.filter(category__in=PRODUCTS).aggregate(t=Sum("line_total"))["t"] or ZERO
    refunded = refunds.aggregate(t=Sum("line_total"))["t"] or ZERO  # negative
    trading = services + products + refunded

    expenses = Expense.objects.filter(date__range=(start, end), status=Expense.Status.APPROVED)
    pending = Expense.objects.filter(date__range=(start, end), status=Expense.Status.PENDING)
    invoices = VendorInvoice.objects.filter(
        date__range=(start, end), status__in=[VendorInvoice.Status.APPROVED, VendorInvoice.Status.PAID]
    )
    if branch is not None:
        expenses, pending = expenses.filter(branch=branch), pending.filter(branch=branch)
        invoices = invoices.filter(branch=branch)
    by_cat = [
        (EXPENSE_LABELS[r["category"]], r["t"])
        for r in expenses.values("category").annotate(t=Sum("amount")).order_by("category")
    ]
    total_expenses = sum((t for _, t in by_cat), ZERO)
    payroll = payroll_cost(start.replace(day=1), end, branch)
    purchases = invoices.aggregate(t=Sum("amount_kwd"))["t"] or ZERO
    costs = total_expenses + payroll + purchases
    headline, unverified = headline_sales(start, end, branch)
    return {
        "start": start,
        "end": end,
        "branch": branch.name if branch else "Combined",
        "services": services,
        "products": products,
        "refunds": refunded,
        "trading_income": trading,
        "expenses": by_cat,
        "total_expenses": total_expenses,
        "pending_expenses": pending.count(),
        "payroll": payroll,
        "purchases": purchases,
        "total_costs": costs,
        "net_income": trading - costs,
        "headline_sales": headline,
        "difference": trading - headline,
        "unverified_weeks": unverified,
    }


@transaction.atomic
def finalise_statement(kind, start, end, branch, user, note="") -> IncomeStatement:
    from apps.reports.services import jsonable

    _need(user, "finance.manage", branch.pk if branch else None, "Only the Accountant finalises statements.")
    if end >= timezone.localdate():
        raise ValidationError("A statement can be finalised once the period has ended.")
    if IncomeStatement.objects.filter(kind=kind, period_start=start, branch=branch).exists():
        raise ValidationError("This statement has already been finalised.")
    data = income_statement(start, end, branch)
    if (data["difference"] != 0 or data["unverified_weeks"]) and not note.strip():
        raise ValidationError(
            "Headline sales and trading income differ (or some weeks are not verified): explain the difference."
        )
    stmt = IncomeStatement.objects.create(
        kind=kind,
        period_start=start,
        period_end=end,
        branch=branch,
        data=jsonable(data),
        headline_sales=data["headline_sales"],
        trading_income=data["trading_income"],
        difference_note=note.strip(),
        finalised_by=user,
        created_by=user,
        updated_by=user,
    )
    record_event(action="income_statement_finalised", instance=stmt)
    return stmt


def quarter_bounds(day):
    q = (day.month - 1) // 3
    start = datetime.date(day.year, q * 3 + 1, 1)
    end_month = start.month + 2
    import calendar

    return start, datetime.date(day.year, end_month, calendar.monthrange(day.year, end_month)[1])
