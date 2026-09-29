"""Point of sale, receipts, and freeze / refund / cancellation requests."""

import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.validators import day_range
from apps.organization.models import PricingOption
from apps.rbac.services import scope_queryset
from apps.sales import services as sales
from apps.sales.models import AccountRequest, Discount, Membership, Payment, Sale, SaleLine
from apps.shop.models import BranchStock

from ..access import L, desk
from ..lookup import visible_members

LINES, PAYMENTS = 6, 3


def _money(value) -> Decimal:
    try:
        return Decimal(str(value or "0").strip() or "0").quantize(Decimal("0.001"))
    except InvalidOperation as exc:
        raise ValidationError(L("Enter amounts like 12.500", "أدخل المبالغ مثل 12.500")) from exc


def catalogue(branch):
    today = timezone.localdate()
    options = [
        o
        for o in PricingOption.objects.filter(branch=branch, is_active=True, approval="approved").order_by(
            "kind", "name"
        )
        if o.is_sellable(today)
    ]
    stock = (
        BranchStock.objects.filter(branch=branch, quantity__gt=0, variant__product__is_active=True)
        .select_related("variant", "variant__product")
        .order_by("variant__product__name_en", "variant__sort_order")
    )
    discounts = [
        d
        for d in Discount.objects.filter(is_enabled=True)
        if d.kind != Discount.Kind.REFERRAL and (d.branch_id in (None, branch.pk))
    ]
    return options, stock, discounts


@desk("sales.sell")
def sell(request):
    branch = request.branch
    member = None
    if request.GET.get("member") or request.POST.get("member"):
        member = get_object_or_404(
            visible_members(request.user), pk=request.GET.get("member") or request.POST.get("member")
        )
    options, stock, discounts = catalogue(branch)
    if request.method == "POST":
        sale = _submit(request, branch, member, options, stock, discounts)
        messages.success(request, L(f"Sale {sale.reference} saved.", f"تم حفظ البيع {sale.reference}."))
        return redirect("desk:sale", pk=sale.pk)
    preset = request.GET.get("option", "")  # e.g. from the renewals list: the member's current plan
    return render(
        request,
        "desk/sales/sell.html",
        {
            "member": member,
            "options": options,
            "stock": stock,
            "discounts": discounts,
            "preset": preset,
            "lines": range(LINES),
            "payments": range(PAYMENTS),
            "methods": Payment.Method.choices,
        },
    )


def _submit(request, branch, member, options, stock, discounts):
    p = request.POST
    option_map = {str(o.pk): o for o in options}
    stock_map = {str(s.variant_id): s.variant for s in stock}
    discount_map = {str(d.pk): d for d in discounts}
    cart = sales.Cart()
    for i in range(LINES):
        code = p.get(f"item_{i}", "")
        if not code:
            continue
        kind, _, key = code.partition(":")
        item = sales.Item(
            quantity=int(p.get(f"qty_{i}") or 1),
            discount=discount_map.get(p.get(f"discount_{i}", "")),
            discount_reason=p.get(f"discount_reason_{i}", ""),
        )
        if kind == "p" and key in option_map:
            item.pricing_option = option_map[key]
            start = p.get(f"start_{i}")
            item.start_date = datetime.date.fromisoformat(start) if start else None
        elif kind == "v" and key in stock_map:
            item.variant = stock_map[key]
            item.free_issue = bool(p.get(f"free_{i}"))
            item.free_issue_reason = p.get(f"free_reason_{i}", "")
        else:
            raise ValidationError(L("That item is no longer on sale here.", "هذا الصنف لم يعد متاحاً هنا."))
        cart.items.append(item)
    for i in range(PAYMENTS):
        amount = _money(p.get(f"pay_amount_{i}"))
        if amount:
            cart.payments.append(sales.Pay(p.get(f"pay_method_{i}", ""), amount, p.get(f"pay_ref_{i}", "")))
    referred = None
    if p.get("referred_by"):
        referred = visible_members(request.user).filter(pk=p.get("referred_by")).first()
    return sales.sell(
        branch=branch,
        user=request.user,
        cart=cart,
        member=member,
        customer_name=p.get("customer_name", ""),
        customer_mobile=p.get("customer_mobile", ""),
        referred_by=referred,
        receipt_channels=p.getlist("receipt"),
        note=p.get("note", ""),
    )


@desk("sales.view")
def sale_list(request):
    day = request.GET.get("date")
    day = datetime.date.fromisoformat(day) if day else timezone.localdate()
    start, end = day_range(day)
    qs = (
        scope_queryset(Sale.objects.all(), request.user, "sales.view")
        .filter(branch=request.branch, created_at__gte=start, created_at__lt=end)
        .select_related("member", "created_by")
        .prefetch_related("payments")
    )
    by_category = (
        SaleLine.objects.filter(sale__in=qs).values("category").annotate(total=Sum("line_total")).order_by("category")
    )
    return render(
        request,
        "desk/sales/list.html",
        {"sales": qs, "day": day, "by_category": by_category, "total": sum((s.total for s in qs), Decimal("0"))},
    )


@desk("sales.view")
def sale_detail(request, pk):
    sale = get_object_or_404(
        scope_queryset(Sale.objects.all(), request.user, "sales.view").select_related(
            "branch", "member", "created_by", "refund_of"
        ),
        pk=pk,
    )
    return render(
        request,
        "desk/sales/receipt.html",
        {
            "sale": sale,
            "lines": sale.lines.all(),
            "payments": sale.payments.all(),
            "print": request.GET.get("print") == "1",
        },
    )


@require_POST
@desk("sales.sell")
def sale_resend(request, pk):
    sale = get_object_or_404(Sale, pk=pk, branch=request.branch)
    channels = request.POST.getlist("receipt") or ["whatsapp"]
    Sale.objects.filter(pk=sale.pk).update(receipt_channels=channels)
    sales.send_receipt(sale.pk)
    messages.success(request, L("Receipt sent.", "تم إرسال الإيصال."))
    return redirect("desk:sale", pk=pk)


@desk("sales.request")
def request_new(request):
    membership = sale = None
    if request.GET.get("membership") or request.POST.get("membership"):
        membership = get_object_or_404(
            scope_queryset(Membership.objects.all(), request.user, "sales.request").select_related(
                "member", "pricing_option", "sale_line__sale"
            ),
            pk=request.GET.get("membership") or request.POST.get("membership"),
        )
    elif request.GET.get("sale") or request.POST.get("sale"):
        sale = get_object_or_404(
            scope_queryset(Sale.objects.all(), request.user, "sales.request"),
            pk=request.GET.get("sale") or request.POST.get("sale"),
        )
    kind = request.POST.get("kind") or request.GET.get("kind", "freeze")
    if request.method == "POST":
        p = request.POST
        req = sales.request_change(
            kind=kind,
            user=request.user,
            reason=p.get("reason", ""),
            membership=membership,
            sale=sale,
            freeze_start=datetime.date.fromisoformat(p["freeze_start"]) if p.get("freeze_start") else None,
            freeze_weeks=int(p["freeze_weeks"]) if p.get("freeze_weeks") else None,
            refund_amount=_money(p.get("refund_amount")) if p.get("refund_amount") else None,
            refund_method=p.get("refund_method", ""),
        )
        messages.success(
            request, L("Request logged. The Operations Manager will decide.", "تم تسجيل الطلب. سيقرر مدير العمليات.")
        )
        target = membership.member_id if membership else (sale.member_id if sale else None)
        return redirect("desk:member", pk=target) if target else redirect("desk:sale", pk=req.sale_id)
    return render(
        request,
        "desk/sales/request.html",
        {
            "membership": membership,
            "sale": sale,
            "kind": kind,
            "kinds": AccountRequest.Kind.choices,
            "methods": Payment.Method.choices,
            "today": timezone.localdate(),
            "freeze_weeks": range(sales.FREEZE_MIN_WEEKS, sales.FREEZE_MAX_WEEKS + 1),
        },
    )
