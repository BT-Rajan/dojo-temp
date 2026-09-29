"""M15 — online renewals paid through the payment gateway (decision P6-3)."""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


def _reference():
    return "EA-REN-" + timezone.now().strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper()


class RenewalPayment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for payment"
        PAID = "paid", "Paid"
        FAILED = "failed", "Payment failed"

    reference = models.CharField(max_length=30, unique=True, default=_reference, editable=False)
    member = models.ForeignKey("members.Member", on_delete=models.PROTECT, related_name="online_renewals")
    pricing_option = models.ForeignKey("organization.PricingOption", on_delete=models.PROTECT, related_name="+")
    amount = models.DecimalField(max_digits=10, decimal_places=3)
    method = models.CharField(max_length=4, default="knet")
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.PENDING)
    gateway_reference = models.CharField(max_length=80, blank=True)
    sale = models.OneToOneField("sales.Sale", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference
