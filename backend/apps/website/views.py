"""Non-CMS website views: the development payment page and the robots file."""

from django.conf import settings
from django.http import Http404, HttpResponse
from django.template.response import TemplateResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language

from apps.shop.models import Order
from apps.shop.payments import TestGateway


def test_payment(request, reference):
    """Stands in for the bank's KNET / card page while no provider is chosen (never in production)."""
    if settings.PAYMENT_GATEWAY != "test":
        raise Http404
    if reference not in request.session.get("orders", []):
        raise Http404
    order = Order.objects.filter(reference=reference).first()
    if order is None:  # an online membership renewal from the portal (P6-3)
        from types import SimpleNamespace

        from apps.portal.models import RenewalPayment

        renewal = RenewalPayment.objects.filter(reference=reference).first()
        if renewal is not None:
            order = SimpleNamespace(reference=reference, payment_method=renewal.method, total=renewal.amount)
    return_url = request.GET.get("return", "")
    if order is None or not url_has_allowed_host_and_scheme(
        return_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        raise Http404
    sep = "&" if "?" in return_url else "?"
    outcomes = {
        o: f"{return_url}{sep}outcome={o}&sig={TestGateway.signature(reference, o)}" for o in ("approve", "decline")
    }
    return TemplateResponse(
        request,
        "website/pages/test_payment.html",
        {
            "order": order,
            "outcomes": outcomes,
            "lang": "ar" if get_language() == "ar" else "en",
            "dir": "rtl" if get_language() == "ar" else "ltr",
        },
    )


def robots_txt(request):
    from django.conf import settings

    if getattr(settings, "ENVIRONMENT", "") == "staging":  # the review server is not for search engines
        return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")
    lines = [
        "User-agent: *",
        "Disallow: /cms/",
        "Disallow: /api/",
        "Disallow: /en/portal/",
        "Disallow: /ar/portal/",
        "Disallow: /en/shop/cart/",
        "Disallow: /ar/shop/cart/",
        "Disallow: /en/shop/checkout/",
        "Disallow: /ar/shop/checkout/",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
