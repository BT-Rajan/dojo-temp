"""
Payment gateways for KNET and Visa/Mastercard.

The provider is chosen before launch (EA-SYS-SCOPE-01 decision 5). Every gateway
implements the same two steps, so switching provider changes only this file:

    start(order, return_url) -> URL to send the customer to (the provider's payment page)
    verify(order, request)   -> (paid: bool, payment_reference: str)

`TestGateway` simulates the provider's page for development and demos. Production
settings refuse to start with it.
"""

import hashlib
import hmac
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse


class PaymentGateway:
    name = "base"

    def start(self, order, return_url):  # pragma: no cover - interface
        raise NotImplementedError

    def verify(self, order, request):  # pragma: no cover - interface
        raise NotImplementedError


class TestGateway(PaymentGateway):
    """Shows a local page with 'Approve' and 'Decline' buttons in place of the bank's page."""

    name = "test"

    @staticmethod
    def signature(order_reference, outcome):
        return hmac.new(
            settings.SECRET_KEY.encode(), f"{order_reference}:{outcome}".encode(), hashlib.sha256
        ).hexdigest()[:32]

    def start(self, order, return_url):
        return (
            reverse("shop-test-payment", kwargs={"reference": order.reference})
            + "?"
            + urlencode({"return": return_url})
        )

    def verify(self, order, request):
        outcome = request.GET.get("outcome", "")
        sig = request.GET.get("sig", "")
        if outcome not in ("approve", "decline") or not hmac.compare_digest(
            sig, self.signature(order.reference, outcome)
        ):
            return False, ""
        return outcome == "approve", f"TEST-{order.reference}"


GATEWAYS = {"test": TestGateway}


def get_gateway() -> PaymentGateway:
    return GATEWAYS[settings.PAYMENT_GATEWAY]()
