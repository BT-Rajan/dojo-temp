"""
M5 — Point of sale, payments, receipts, memberships, requests and cash-up (replaces the
Mindbody point of sale, Guide G3 and the cash handling rules).

- Membership      what a member bought and may use (dates, sessions, freezes).
- Sale            one receipt, numbered per branch (PRM-000123); lines and payments below it.
- Discount        family, Elite Member tier, referral, promotional and manual discounts.
- AccountRequest  freeze / refund / cancellation: logged by the admin, decided by the OM.
- CashUp          end-of-day count at each branch, sent to the OM and the Accountant.
"""

import datetime
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel

ZERO = Decimal("0.000")


class Membership(BaseModel):
    """A purchased pricing option. Only kind=membership options make someone an active member."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    member = models.ForeignKey("members.Member", on_delete=models.PROTECT, related_name="memberships")
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="memberships")
    pricing_option = models.ForeignKey(
        "organization.PricingOption", on_delete=models.PROTECT, related_name="memberships"
    )
    sale_line = models.OneToOneField(
        "SaleLine", null=True, blank=True, on_delete=models.SET_NULL, related_name="membership"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    sessions_total = models.PositiveSmallIntegerField(null=True, blank=True)
    sessions_used = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    freeze_used = models.BooleanField(default=False, help_text="One freeze per membership.")

    class Meta:
        ordering = ["-end_date", "-id"]
        indexes = [models.Index(fields=["member", "end_date"]), models.Index(fields=["branch", "end_date"])]

    def __str__(self):
        return f"{self.member} · {self.pricing_option.name} ({self.start_date:%d %b} – {self.end_date:%d %b %Y})"

    @property
    def is_membership(self) -> bool:
        return self.pricing_option.kind == "membership"

    @property
    def sessions_left(self):
        if self.sessions_total is None:
            return None
        return max(self.sessions_total - self.sessions_used, 0)

    def frozen_on(self, day) -> bool:
        return any(f.start_date <= day <= f.end_date for f in self.freezes.all())

    def valid_on(self, day) -> bool:
        return self.status == self.Status.ACTIVE and self.start_date <= day <= self.end_date

    def covers_program(self, program_id) -> bool:
        option = self.pricing_option
        if option.all_access or program_id is None:
            return True
        ids = [p.pk for p in option.programs.all()]
        return not ids or program_id in ids


class Freeze(models.Model):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="freezes")
    start_date = models.DateField()
    end_date = models.DateField()
    request = models.OneToOneField("AccountRequest", null=True, on_delete=models.SET_NULL, related_name="freeze")

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"Freeze {self.start_date} – {self.end_date}"

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


class Discount(BaseModel):
    class Kind(models.TextChoices):
        FAMILY = "family", "Family / sibling"
        ELITE = "elite", "Elite Member tier"
        REFERRAL = "referral", "Referral reward"
        PROMO = "promo", "Promotion"
        MANUAL = "manual", "Manual (needs a reason)"

    name = models.CharField(max_length=80)
    name_ar = models.CharField(max_length=80, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    branch = models.ForeignKey(
        "organization.Branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="discounts",
        help_text="Empty = both branches.",
    )
    percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))]
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True, validators=[MinValueValidator(Decimal("0"))]
    )
    applies_to_kinds = models.JSONField(
        default=list, blank=True, help_text='Pricing option kinds, e.g. ["membership"]. Empty = all.'
    )
    active_from = models.DateField(null=True, blank=True)
    active_until = models.DateField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return self.name

    def usable_on(self, day, branch_id, kind) -> bool:
        return (
            self.is_enabled
            and (self.branch_id is None or self.branch_id == branch_id)
            and (not self.applies_to_kinds or kind in self.applies_to_kinds)
            and (self.active_from is None or self.active_from <= day)
            and (self.active_until is None or day <= self.active_until)
        )

    def value_for(self, price: Decimal) -> Decimal:
        if self.percent:
            value = (price * self.percent / Decimal("100")).quantize(Decimal("0.001"))
        else:
            value = self.amount or ZERO
        return min(value, price)


class ReferralCredit(models.Model):
    """A member who brings a friend gets a fixed KD off their next renewal."""

    referrer = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="referral_credits")
    referred = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="+")
    amount = models.DecimalField(max_digits=10, decimal_places=3)
    created_at = models.DateTimeField(auto_now_add=True)
    used_on = models.ForeignKey("SaleLine", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["referred"], name="one_referral_credit_per_new_member")]

    def __str__(self):
        return f"{self.referrer} ← {self.referred} ({self.amount})"


class ReceiptCounter(models.Model):
    """Receipt numbers per branch, handed out under a row lock so two desks never share a number."""

    branch = models.OneToOneField("organization.Branch", on_delete=models.PROTECT, related_name="receipt_counter")
    last_number = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.branch.code}: {self.last_number}"


class Sale(BaseModel):
    class Kind(models.TextChoices):
        SALE = "sale", "Sale"
        REFUND = "refund", "Refund"

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="sales")
    number = models.PositiveIntegerField()
    kind = models.CharField(max_length=6, choices=Kind.choices, default=Kind.SALE)
    member = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.PROTECT, related_name="sales")
    customer_name = models.CharField(max_length=150, blank=True, help_text="Trial or day-pass buyer without a profile.")
    customer_mobile = models.CharField(max_length=16, blank=True)
    refund_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="refunds")
    subtotal = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    discount_total = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    total = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    receipt_channels = models.JSONField(default=list, blank=True, help_text="printed / whatsapp / email")
    receipt_sent_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["branch", "number"], name="one_receipt_number_per_branch")]
        indexes = [models.Index(fields=["branch", "created_at"])]

    def __str__(self):
        return self.reference

    @property
    def reference(self):
        return f"{self.branch.code}-{self.number:06d}"

    @property
    def customer(self):
        return str(self.member) if self.member_id else self.customer_name

    @property
    def paid(self):
        return sum((p.amount for p in self.payments.all()), ZERO)


class SaleLine(models.Model):
    class Category(models.TextChoices):
        """FRM-06 mapping (business rule 2). A trial is never recorded as a day pass."""

        NEW = "new", "New"
        RENEW = "renew", "Renew"
        TRIAL = "trial", "Trial Pass"
        DAY_PASS = "day_pass", "Day Pass"
        EQUIPMENT = "equipment", "Equipment"
        OTHER = "other", "Sessions & events"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="lines")
    pricing_option = models.ForeignKey(
        "organization.PricingOption", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    variant = models.ForeignKey(
        "shop.ProductVariant", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    description = models.CharField(max_length=200)
    description_ar = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=10, choices=Category.choices)
    quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=3)
    discount = models.ForeignKey(Discount, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    discount_reason = models.CharField(max_length=200, blank=True)
    line_total = models.DecimalField(max_digits=10, decimal_places=3)
    free_issue = models.BooleanField(default=False, help_text="0 KD issue (e.g. grading belt); stock still reduces.")

    def __str__(self):
        return f"{self.description} × {self.quantity}"


class Payment(models.Model):
    class Method(models.TextChoices):
        KNET = "knet", "KNET"
        CARD = "card", "Visa / Mastercard"
        CASH = "cash", "Cash"

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments")
    method = models.CharField(max_length=4, choices=Method.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=3, help_text="Negative for refunds.")
    reference = models.CharField(max_length=60, blank=True, help_text="Terminal reference for KNET and cards.")
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["received_at"]
        indexes = [models.Index(fields=["method", "received_at"])]

    def __str__(self):
        return f"{self.get_method_display()} {self.amount}"


class AccountRequest(BaseModel):
    """Freeze, refund and cancellation: the admin logs it, only the OM decides (scope M5, rule 5)."""

    class Kind(models.TextChoices):
        FREEZE = "freeze", "Freeze"
        REFUND = "refund", "Refund"
        CANCEL = "cancel", "Cancellation"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for the OM"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    kind = models.CharField(max_length=6, choices=Kind.choices)
    membership = models.ForeignKey(Membership, null=True, blank=True, on_delete=models.PROTECT, related_name="requests")
    sale = models.ForeignKey(
        Sale,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="requests",
        help_text="For refunds of items that are not memberships.",
    )
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="account_requests")
    reason = models.CharField(max_length=255)
    freeze_start = models.DateField(null=True, blank=True)
    freeze_weeks = models.PositiveSmallIntegerField(null=True, blank=True)
    refund_amount = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    refund_method = models.CharField(max_length=4, choices=Payment.Method.choices, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)
    refund_sale = models.OneToOneField(Sale, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.membership or self.sale}"

    @property
    def freeze_end(self):
        if self.freeze_start and self.freeze_weeks:
            return self.freeze_start + datetime.timedelta(weeks=self.freeze_weeks) - datetime.timedelta(days=1)
        return None


class CashUp(BaseModel):
    """End-of-day cash-up (scope M5): counted vs system, terminal settlement vs system."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        VERIFIED = "verified", "Verified by the OM"

    REASON_THRESHOLD = Decimal("1.000")  # differences above this need a written reason

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="cash_ups")
    date = models.DateField()
    expected_cash = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    counted_cash = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    expected_knet = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    terminal_knet = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    expected_card = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    terminal_card = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["branch", "date"], name="one_cash_up_per_branch_per_day")]

    def __str__(self):
        return f"Cash-up {self.branch.code} {self.date}"

    @staticmethod
    def _diff(actual, expected):
        return None if actual is None else actual - expected

    @property
    def cash_difference(self):
        return self._diff(self.counted_cash, self.expected_cash)

    @property
    def knet_difference(self):
        return self._diff(self.terminal_knet, self.expected_knet)

    @property
    def card_difference(self):
        return self._diff(self.terminal_card, self.expected_card)

    @property
    def needs_reason(self):
        return any(
            d is not None and abs(d) > self.REASON_THRESHOLD
            for d in (self.cash_difference, self.knet_difference, self.card_difference)
        )
