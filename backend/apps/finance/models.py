"""
M11 — Finance (the Accountant's area).

- Expense         branch expenses with a receipt photo, category and approval. Cash paid out of the
                  drawer is taken off the cash expected at the end-of-day cash-up (decision P2-12).
- Vendor, VendorInvoice  local and international suppliers; the OM approves, the Accountant pays.
                  Landed costs are added with purchasing in Phase 3.
- IncomeStatement a finalised monthly or quarterly statement ("for the quarter ended"); the
                  headline sales must agree with trading income or the difference is explained.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.members.models import get_private_storage

ZERO = Decimal("0.000")


def expense_receipt_path(instance, filename):
    ext = "pdf" if filename.lower().endswith(".pdf") else "jpg"
    return f"finance/expenses/{timezone.localdate():%Y/%m}/{secrets.token_hex(8)}.{ext}"


def invoice_document_path(instance, filename):
    ext = "pdf" if filename.lower().endswith(".pdf") else "jpg"
    return f"finance/invoices/{timezone.localdate():%Y/%m}/{secrets.token_hex(8)}.{ext}"


class Expense(BaseModel):
    class Category(models.TextChoices):
        SUPPLIES = "supplies", "Supplies and stationery"
        CLEANING = "cleaning", "Cleaning"
        MAINTENANCE = "maintenance", "Repairs and maintenance"
        UTILITIES = "utilities", "Utilities and internet"
        TRANSPORT = "transport", "Transport and delivery"
        HOSPITALITY = "hospitality", "Refreshments and hospitality"
        MARKETING = "marketing", "Marketing and printing"
        EVENTS = "events", "Events, gradings and competitions"
        RENT = "rent", "Rent"
        OTHER = "other", "Other"

    class PaidFrom(models.TextChoices):
        DRAWER = "drawer", "Branch cash drawer"
        CARD = "card", "Company card"
        BANK = "bank", "Bank transfer"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="expenses")
    date = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=200)
    paid_to = models.CharField(max_length=150, help_text="Shop, supplier or person paid ('For' on FRM-06).")
    category = models.CharField(max_length=12, choices=Category.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    paid_from = models.CharField(max_length=6, choices=PaidFrom.choices, default=PaidFrom.DRAWER)
    receipt = models.FileField(upload_to=expense_receipt_path, storage=get_private_storage, blank=True)
    no_receipt_reason = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["branch", "date"]), models.Index(fields=["status"])]

    def __str__(self):
        return f"{self.date} {self.description} {self.amount}"

    @property
    def has_receipt(self):
        return bool(self.receipt)


class Vendor(BaseModel):
    class Type(models.TextChoices):
        LOCAL = "local", "Local"
        INTERNATIONAL = "international", "International"

    name = models.CharField(max_length=150, unique=True)
    name_ar = models.CharField(max_length=150, blank=True)
    vendor_type = models.CharField(max_length=13, choices=Type.choices, default=Type.LOCAL)
    country = models.CharField(max_length=60, default="Kuwait")
    contact = models.CharField(max_length=200, blank=True, help_text="Contact person.")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    currency = models.CharField(max_length=3, default="KWD")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class VendorInvoice(BaseModel):
    class Status(models.TextChoices):
        RECORDED = "recorded", "Waiting for OM approval"
        APPROVED = "approved", "Approved to pay"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    class Method(models.TextChoices):
        BANK = "bank", "Bank transfer"
        CARD = "card", "Company card"
        CASH = "cash", "Cash"
        CHEQUE = "cheque", "Cheque"

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="invoices")
    branch = models.ForeignKey(
        "organization.Branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vendor_invoices",
        help_text="Empty = shared by both branches.",
    )
    number = models.CharField(max_length=60)
    date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    description = models.CharField(max_length=255)
    currency = models.CharField(max_length=3, default="KWD")
    amount = models.DecimalField(max_digits=12, decimal_places=3, validators=[MinValueValidator(Decimal("0.001"))])
    exchange_rate = models.DecimalField(
        max_digits=12, decimal_places=6, default=Decimal("1"), help_text="KWD per 1 unit of the invoice currency."
    )
    amount_kwd = models.DecimalField(max_digits=12, decimal_places=3)
    document = models.FileField(upload_to=invoice_document_path, storage=get_private_storage, blank=True)
    purchase_order = models.ForeignKey(
        "inventory.PurchaseOrder", null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices"
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.RECORDED)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_on = models.DateField(null=True, blank=True)
    paid_method = models.CharField(max_length=6, choices=Method.choices, blank=True)
    paid_reference = models.CharField(max_length=60, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        constraints = [models.UniqueConstraint(fields=["vendor", "number"], name="one_invoice_number_per_vendor")]

    def __str__(self):
        return f"{self.vendor} #{self.number}"


class IncomeStatement(BaseModel):
    class Kind(models.TextChoices):
        MONTH = "month", "Monthly"
        QUARTER = "quarter", "Quarterly"

    kind = models.CharField(max_length=7, choices=Kind.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    branch = models.ForeignKey("organization.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    data = models.JSONField(default=dict)
    headline_sales = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO)
    trading_income = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO)
    difference_note = models.TextField(blank=True)
    finalised_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    finalised_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-period_start"]

    def __str__(self):
        scope = self.branch.code if self.branch_id else "Combined"
        return f"{self.get_kind_display()} statement {self.period_start:%b %Y} ({scope})"

    @property
    def difference(self):
        return self.trading_income - self.headline_sales
