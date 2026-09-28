"""Shop views served by ShopPage (routable). The cart lives in the visitor's session."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.translation import get_language

from apps.audit.services import record_event
from apps.core.validators import normalize_kuwait_mobile
from apps.organization.models import Branch
from apps.shop.models import Category, Order, OutOfStock, Product, ProductVariant, ShopSettings, SizeGuide, place_order
from apps.shop.payments import get_gateway

MAX_QTY = 10


def _lang():
    return "ar" if get_language() == "ar" else "en"


def _cart(request):
    return {int(k): int(v) for k, v in request.session.get("cart", {}).items()}


def _save_cart(request, cart):
    request.session["cart"] = {str(k): v for k, v in cart.items() if v > 0}


def cart_lines(request):
    cart = _cart(request)
    variants = ProductVariant.objects.filter(pk__in=cart).select_related("product", "product__image")
    lines, total = [], Decimal("0")
    for v in variants:
        qty = min(cart[v.pk], MAX_QTY)
        line_total = v.product.price * qty
        total += line_total
        lines.append(
            {
                "variant": v,
                "product": v.product,
                "qty": qty,
                "total": line_total,
                "available": v.stock >= qty and v.product.is_active,
            }
        )
    return lines, total


def cart_count(request):
    return sum(_cart(request).values())


def _render(page, request, template, **extra):
    context = page.get_context(request)
    context.update(extra)
    context["cart_count"] = cart_count(request)
    return TemplateResponse(request, template, context)


def product_list(page, request):
    products = Product.objects.filter(is_active=True).prefetch_related("variants").select_related("image")
    category = request.GET.get("cat", "")
    if category in Category.values:
        products = products.filter(category=category)
    return _render(
        page,
        request,
        "website/pages/shop_index.html",
        products=products,
        category=category,
        categories=Category.choices,
    )


def product_detail(page, request, slug):
    product = Product.objects.filter(slug=slug, is_active=True).prefetch_related("variants").first()
    if product is None:
        raise Http404
    error = ""
    if request.method == "POST":
        variant = product.variants.filter(pk=request.POST.get("variant") or 0).first()
        try:
            qty = max(1, min(int(request.POST.get("qty", 1)), MAX_QTY))
        except ValueError:
            qty = 1
        if variant is None:
            error = "size"
        elif variant.stock < qty:
            error = "stock"
        else:
            cart = _cart(request)
            cart[variant.pk] = min(cart.get(variant.pk, 0) + qty, MAX_QTY)
            _save_cart(request, cart)
            return HttpResponseRedirect(page.url + "cart/")
    guide = SizeGuide.objects.filter(category=product.category).prefetch_related("rows").first()
    variants = list(product.variants.all())
    first_available = next((v for v in variants if v.stock > 0), None)
    return _render(
        page,
        request,
        "website/pages/shop_product.html",
        product=product,
        variants=variants,
        guide=guide,
        error=error,
        selected=first_available,
        sold_out_sizes=[v.size for v in variants if v.stock == 0],
        show_guide=request.GET.get("guide") == "1",
    )


def cart(page, request):
    if request.method == "POST":
        cart = _cart(request)
        variant_id = int(request.POST.get("variant") or 0)
        action = request.POST.get("action")
        if action == "remove":
            cart.pop(variant_id, None)
        elif action in ("inc", "dec") and variant_id in cart:
            cart[variant_id] = max(0, min(cart[variant_id] + (1 if action == "inc" else -1), MAX_QTY))
        _save_cart(request, cart)
        return HttpResponseRedirect(page.url + "cart/")
    lines, total = cart_lines(request)
    return _render(page, request, "website/pages/shop_cart.html", lines=lines, total=total)


def checkout(page, request, payment_failed=False):
    lang = _lang()
    settings_ = ShopSettings.load(request_or_site=request)
    lines, subtotal = cart_lines(request)
    if not lines:
        return HttpResponseRedirect(page.url + "cart/")
    branches = Branch.objects.filter(is_active=True).order_by("code").reverse()  # PRM before BED
    errors = {}
    values = {"fulfilment": "pickup", "payment": "knet", "branch": "PRM"}
    if request.method == "POST":
        values.update(
            {
                k: request.POST.get(k, "").strip()
                for k in ("name", "mobile", "email", "fulfilment", "branch", "area", "address", "payment")
            }
        )
        if not values["name"]:
            errors["name"] = True
        try:
            values["mobile"] = normalize_kuwait_mobile(values["mobile"])
        except ValidationError:
            errors["mobile"] = True
        if values["fulfilment"] == "delivery" and (not settings_.delivery_enabled or not values["address"]):
            errors["address"] = True
        pickup_branch = branches.filter(code=values["branch"]).first()
        if values["fulfilment"] == "pickup" and pickup_branch is None:
            errors["branch"] = True
        if values["payment"] not in Order.Method.values:
            errors["payment"] = True
        if not errors:
            try:
                order = place_order(
                    cart_lines=[(line["variant"].pk, line["qty"]) for line in lines],
                    customer={
                        "customer_name": values["name"],
                        "mobile": values["mobile"],
                        "email": values["email"],
                        "pickup_branch": pickup_branch if values["fulfilment"] == "pickup" else None,
                        "delivery_area": values["area"],
                        "delivery_address": values["address"],
                    },
                    fulfilment=values["fulfilment"],
                    payment_method=values["payment"],
                    delivery_fee=settings_.delivery_fee,
                    language=lang,
                    user=request.user if request.user.is_authenticated else None,
                )
            except OutOfStock:
                errors["stock"] = True
            else:
                request.session.setdefault("orders", [])
                request.session["orders"] = request.session["orders"] + [order.reference]
                record_event(action="order_placed", instance=order, changes={"total": str(order.total)})
                return_url = request.build_absolute_uri(page.url + f"pay/return/{order.reference}/")
                return HttpResponseRedirect(get_gateway().start(order, return_url))
    fee = settings_.delivery_fee if values.get("fulfilment") == "delivery" else Decimal("0")
    return _render(
        page,
        request,
        "website/pages/shop_checkout.html",
        lines=lines,
        subtotal=subtotal,
        fee=fee,
        total=subtotal + fee,
        delivery_fee=settings_.delivery_fee,
        shop_settings=settings_,
        branches=branches,
        errors=errors,
        values=values,
        payment_failed=payment_failed,
    )


def _own_order(request, reference):
    if reference not in request.session.get("orders", []):
        raise Http404
    return Order.objects.filter(reference=reference).prefetch_related("items").first() or _raise404()


def _raise404():
    raise Http404


def payment_return(page, request, reference):
    order = _own_order(request, reference)
    if order.status != Order.Status.PENDING:  # already settled (e.g. the return page was reloaded)
        if order.status == Order.Status.PAID:
            return HttpResponseRedirect(page.url + f"order/{order.reference}/")
        return checkout(page, request, payment_failed=True)
    paid, payment_ref = get_gateway().verify(order, request)
    if paid:
        order.mark_paid(payment_ref)
        request.session["cart"] = {}
        record_event(action="order_paid", instance=order)
        return HttpResponseRedirect(page.url + f"order/{order.reference}/")
    order.mark_failed()
    record_event(action="order_payment_failed", instance=order)
    # The cart is kept so the parent can try again.
    return checkout(page, request, payment_failed=True)


def order_done(page, request, reference):
    order = _own_order(request, reference)
    return _render(page, request, "website/pages/shop_order.html", order=order)
