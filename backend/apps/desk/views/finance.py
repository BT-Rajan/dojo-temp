"""Finance (M11): expenses, reconciliation, revenue, income statement, vendor invoices, exports."""

import datetime

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.services import record_event
from apps.core.files import content_type_for
from apps.finance import services as fin
from apps.finance.models import Expense, IncomeStatement, Vendor, VendorInvoice
from apps.organization.models import Branch
from apps.payroll.services import month_end, previous_month
from apps.rbac.services import has_perm, scope_queryset
from apps.reports import documents
from apps.reports.export import render as render_doc
from apps.reports.services import branches_for, jsonable
from apps.sales.models import Sale

from ..access import L, can, desk, lang
from .ops import _date
from .sales import _money

EXPENSE_AR = {
    "supplies": "لوازم وقرطاسية",
    "cleaning": "تنظيف",
    "maintenance": "إصلاح وصيانة",
    "utilities": "خدمات وإنترنت",
    "transport": "نقل وتوصيل",
    "hospitality": "ضيافة",
    "marketing": "تسويق وطباعة",
    "events": "فعاليات وترقيات وبطولات",
    "rent": "إيجار",
    "other": "أخرى",
}
PAID_FROM_AR = {"drawer": "صندوق الفرع", "card": "بطاقة الشركة", "bank": "تحويل بنكي"}


def download(content, ctype, filename):
    response = HttpResponse(content, content_type=ctype)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    return response


def export_doc(request, doc, name):
    fmt = "xlsx" if request.GET.get("format") == "xlsx" else "pdf"
    content, ctype, ext = render_doc(doc, fmt, lang())
    record_event(action="report_exported", object_type="report", object_id=name[:64], changes={"format": fmt})
    return download(content, ctype, f"{name}.{ext}")


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
EXPENSE_PERMS = ["finance.expense", "finance.expense_approve", "finance.manage"]


@desk(any_of=EXPENSE_PERMS)
def expenses(request):
    qs = scope_queryset(Expense.objects.all(), request.user, "finance.expense_approve")
    own = Expense.objects.filter(branch=request.branch)
    if not (can(request, "finance.expense_approve") or can(request, "finance.manage")):
        qs = own
    elif can(request, "finance.manage"):
        qs = scope_queryset(Expense.objects.all(), request.user, "finance.manage") | qs
    status = request.GET.get("status", "")
    if status in Expense.Status.values:
        qs = qs.filter(status=status)
    categories = [(v, EXPENSE_AR[v] if lang() == "ar" else label) for v, label in Expense.Category.choices]
    paid_from = [(v, PAID_FROM_AR[v] if lang() == "ar" else label) for v, label in Expense.PaidFrom.choices]
    return render(
        request,
        "desk/finance/expenses.html",
        {
            "expenses": qs.select_related("branch", "created_by", "decided_by").distinct()[:150],
            "status": status,
            "categories": categories,
            "paid_from": paid_from,
            "today": timezone.localdate(),
            "labels": EXPENSE_AR if lang() == "ar" else dict(Expense.Category.choices),
            "can_approve": can(request, "finance.expense_approve"),
            "is_finance": can(request, "finance.manage"),
        },
    )


@require_POST
@desk("finance.expense")
def expense_new(request):
    p = request.POST
    fin.record_expense(
        request.branch,
        request.user,
        date=_date(p.get("date"), timezone.localdate()),
        description=p.get("description", "")[:200],
        paid_to=p.get("paid_to", "")[:150],
        category=p.get("category", "other"),
        amount=_money(p.get("amount")),
        paid_from=p.get("paid_from", "drawer"),
        receipt=request.FILES.get("receipt"),
        no_receipt_reason=p.get("no_receipt_reason", "")[:200],
    )
    messages.success(request, L("Expense recorded. It waits for approval.", "تم تسجيل المصروف وهو بانتظار الاعتماد."))
    return redirect("desk:expenses")


@require_POST
@desk("finance.expense_approve")
def expense_decide(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    fin.decide_expense(expense, request.user, request.POST.get("decision") == "approve", request.POST.get("note", ""))
    return redirect(request.POST.get("next") or "desk:expenses")


@desk(any_of=EXPENSE_PERMS)
def expense_receipt(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if not expense.receipt or not any(has_perm(request.user, p, expense.branch_id) for p in EXPENSE_PERMS):
        raise Http404
    response = FileResponse(expense.receipt.open("rb"), content_type=content_type_for(expense.receipt.name))
    response["Cache-Control"] = "private, max-age=300"
    return response


# ---------------------------------------------------------------------------
# Reconciliation, revenue, income statement
# ---------------------------------------------------------------------------
def _period(request, default_days=30):
    today = timezone.localdate()
    end = _date(request.GET.get("end"), today)
    start = _date(request.GET.get("start"), end - datetime.timedelta(days=default_days - 1))
    if start > end:
        start, end = end, start
    return start, end


def _scope(request):
    branches, combined = branches_for(request.user, "finance.manage", "finance.manage")
    if not branches:
        branches, combined = branches_for(request.user)
    wanted = request.GET.get("branch", "all" if combined else (request.branch.code if request.branch else ""))
    if wanted != "all":
        chosen = [b for b in branches if b.code == wanted]
        if chosen:
            return chosen, chosen[0], combined, wanted
    if not combined:
        return branches[:1], branches[0] if branches else None, combined, branches[0].code if branches else ""
    return branches, None, combined, "all"


@desk("finance.manage")
def reconciliation(request):
    start, end = _period(request, 14)
    branches, _, combined, wanted = _scope(request)
    rows = fin.reconciliation(branches, start, end)
    return render(
        request,
        "desk/finance/reconciliation.html",
        {
            "rows": rows,
            "start": start,
            "end": end,
            "branches": branches_for(request.user, "finance.manage", "finance.manage")[0],
            "wanted": wanted,
            "combined": combined,
        },
    )


@desk(any_of=["finance.manage", "reports.all"])
def revenue(request):
    start, end = _period(request, 90)
    branches, _, combined, wanted = _scope(request)
    data = fin.revenue(start, end, branches)
    if request.GET.get("format"):
        doc = {
            "title": L("Revenue", "الإيرادات"),
            "subtitle": f"{start:%d/%m/%Y} – {end:%d/%m/%Y}",
            "sheet": "Revenue",
            "blocks": [
                (
                    "table",
                    [L("Services", "الخدمات"), L("Products", "المنتجات"), L("Total", "المجموع")],
                    [(data["services"], data["products"], data["total"])],
                ),
                ("heading", L("By category", "حسب الفئة")),
                (
                    "table",
                    [L("Category", "الفئة"), "KD"],
                    [(documents.category(k, lang()), v) for k, v in data["by_category"].items()],
                ),
                ("heading", L("By program", "حسب البرنامج")),
                ("table", [L("Program", "البرنامج"), "KD"], data["by_program"]),
                ("heading", L("By branch", "حسب الفرع")),
                ("table", [L("Branch", "الفرع"), "KD"], list(data["by_branch"].items())),
                ("heading", L("By month", "حسب الشهر")),
                ("table", [L("Month", "الشهر"), "KD"], [(m.strftime("%m/%Y"), v) for m, v in data["by_month"]]),
            ],
        }
        return export_doc(request, doc, f"elite-revenue-{start:%Y%m%d}-{end:%Y%m%d}")
    return render(
        request,
        "desk/finance/revenue.html",
        {
            "data": data,
            "start": start,
            "end": end,
            "branches": branches_for(request.user)[0],
            "wanted": wanted,
            "combined": combined,
        },
    )


def _statement_period(request):
    today = timezone.localdate()
    kind = request.GET.get("kind", "month")
    if kind == "quarter":
        default = fin.quarter_bounds(fin.quarter_bounds(today)[0] - datetime.timedelta(days=1))[0]
        start = _date(request.GET.get("start"), default)
        start, end = fin.quarter_bounds(start)
    else:
        kind = "month"
        start = _date(request.GET.get("start"), previous_month(today.replace(day=1))).replace(day=1)
        end = month_end(start)
    return kind, start, end


@desk(any_of=["finance.manage", "reports.all"])
def income_statement(request):
    kind, start, end = _statement_period(request)
    branches, branch, combined, wanted = _scope(request)
    if branch is None and not combined:
        raise PermissionDenied
    final = IncomeStatement.objects.filter(kind=kind, period_start=start, branch=branch).first()
    data = final.data if final else jsonable(fin.income_statement(start, end, branch))
    if request.GET.get("format"):
        return export_doc(
            request, documents.income_statement_doc(data, kind, lang()), f"elite-income-{kind}-{start:%Y%m}"
        )
    if request.method == "POST":
        if not can(request, "finance.manage"):
            raise PermissionDenied
        fin.finalise_statement(kind, start, end, branch, request.user, request.POST.get("note", ""))
        messages.success(request, L("Statement finalised.", "تم اعتماد القائمة."))
        return redirect(request.get_full_path())
    months = []
    m = previous_month(timezone.localdate().replace(day=1))
    for _ in range(12):
        months.append(m)
        m = previous_month(m)
    return render(
        request,
        "desk/finance/income.html",
        {
            "data": data,
            "final": final,
            "kind": kind,
            "start": start,
            "end": end,
            "branches": branches_for(request.user)[0],
            "wanted": wanted,
            "combined": combined,
            "months": months,
            "history": IncomeStatement.objects.select_related("branch", "finalised_by")[:24],
            "ended": end < timezone.localdate(),
            "is_finance": can(request, "finance.manage"),
        },
    )


# ---------------------------------------------------------------------------
# Vendor invoices
# ---------------------------------------------------------------------------
@desk(any_of=["finance.manage", "inventory.approve"])
def invoices(request):
    if request.method == "POST" and request.POST.get("action") == "vendor":
        if not can(request, "finance.manage"):
            raise PermissionDenied
        name = request.POST.get("name", "").strip()
        if name:
            Vendor.objects.get_or_create(
                name=name[:150],
                defaults={
                    "name_ar": request.POST.get("name_ar", "")[:150],
                    "country": request.POST.get("country", "Kuwait")[:60] or "Kuwait",
                    "contact": request.POST.get("contact", "")[:200],
                    "created_by": request.user,
                },
            )
        return redirect("desk:invoices")
    if request.method == "POST":
        if not can(request, "finance.manage"):
            raise PermissionDenied
        p = request.POST
        fin.record_invoice(
            request.user,
            vendor=get_object_or_404(Vendor, pk=p.get("vendor") or 0),
            number=p.get("number", "")[:60],
            date=_date(p.get("date"), timezone.localdate()),
            due_date=_date(p.get("due_date")),
            description=p.get("description", "")[:255],
            amount=_money(p.get("amount")),
            currency=p.get("currency", "KWD")[:3],
            exchange_rate=_money(p.get("exchange_rate") or "1"),
            branch=Branch.objects.filter(pk=p.get("branch") or 0).first(),
            document=request.FILES.get("document"),
        )
        messages.success(
            request,
            L(
                "Invoice recorded. It waits for the OM's approval.",
                "تم تسجيل الفاتورة وهي بانتظار موافقة مدير العمليات.",
            ),
        )
        return redirect("desk:invoices")
    return render(
        request,
        "desk/finance/invoices.html",
        {
            "invoices": VendorInvoice.objects.select_related("vendor", "branch", "created_by", "approved_by")[:100],
            "vendors": Vendor.objects.filter(is_active=True),
            "branches": Branch.objects.filter(is_active=True),
            "today": timezone.localdate(),
            "methods": VendorInvoice.Method.choices,
        },
    )


@require_POST
@desk(any_of=["finance.manage", "inventory.approve"])
def invoice_action(request, pk):
    inv = get_object_or_404(VendorInvoice, pk=pk)
    action = request.POST.get("action")
    if action in ("approve", "reject"):
        fin.approve_invoice(inv, request.user, action == "approve", request.POST.get("note", ""))
    elif action == "pay":
        fin.pay_invoice(
            inv,
            request.user,
            paid_on=_date(request.POST.get("paid_on"), timezone.localdate()),
            method=request.POST.get("method", "bank"),
            reference=request.POST.get("reference", "")[:60],
        )
    return redirect("desk:invoices")


@desk(any_of=["finance.manage", "inventory.approve"])
def invoice_document(request, pk):
    inv = get_object_or_404(VendorInvoice, pk=pk)
    if not inv.document:
        raise Http404
    return FileResponse(inv.document.open("rb"), content_type=content_type_for(inv.document.name))


# ---------------------------------------------------------------------------
# Exports for the accountant's tool (decision 8: Excel / CSV until the tool is chosen)
# ---------------------------------------------------------------------------
@desk("finance.manage")
def export_sales(request):
    start, end = _period(request, 30)
    branches, _, _, _ = _scope(request)
    from apps.core.validators import day_range

    s0, e1 = day_range(start)[0], day_range(end)[1]
    rows = []
    for sale in (
        Sale.objects.filter(branch__in=branches, created_at__gte=s0, created_at__lt=e1)
        .select_related("branch", "member", "created_by")
        .prefetch_related("lines", "payments")
        .order_by("created_at")
    ):
        methods = ", ".join(sorted({p.get_method_display() for p in sale.payments.all()}))
        for line in sale.lines.all():
            rows.append(
                (
                    timezone.localtime(sale.created_at).date(),
                    sale.reference,
                    sale.get_kind_display(),
                    sale.branch.code,
                    sale.customer,
                    line.description,
                    line.get_category_display(),
                    line.quantity,
                    line.unit_price,
                    line.discount_amount,
                    line.line_total,
                    methods,
                    sale.created_by.full_name if sale.created_by else "",
                )
            )
    kind = request.GET.get("what", "sales")
    if kind == "expenses":
        rows = [
            (
                e.date,
                e.branch.code,
                e.get_category_display(),
                e.description,
                e.paid_to,
                e.get_paid_from_display(),
                e.amount,
                e.get_status_display(),
                "yes" if e.receipt else "no",
            )
            for e in Expense.objects.filter(branch__in=branches, date__range=(start, end))
            .select_related("branch")
            .order_by("date")
        ]
        header = ["Date", "Branch", "Category", "Description", "Paid to", "Paid from", "Amount", "Status", "Receipt"]
    else:
        header = [
            "Date",
            "Receipt",
            "Type",
            "Branch",
            "Customer",
            "Item",
            "Category",
            "Qty",
            "Unit price",
            "Discount",
            "Line total",
            "Paid by",
            "Staff",
        ]
    fmt = request.GET.get("format", "xlsx")
    name = f"elite-{kind}-{start:%Y%m%d}-{end:%Y%m%d}"
    record_event(action="finance_exported", object_type="export", object_id=name, changes={"format": fmt})
    if fmt == "csv":
        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        for r in rows:
            writer.writerow([f"{v:.3f}" if hasattr(v, "quantize") else v for v in r])
        return download(buf.getvalue().encode("utf-8-sig"), "text/csv", f"{name}.csv")
    doc = {"title": name, "subtitle": "", "sheet": kind, "blocks": [("table", header, rows)]}
    content, ctype, ext = render_doc(doc, "xlsx", "en")
    return download(content, ctype, f"{name}.{ext}")
