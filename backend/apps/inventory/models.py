"""
M8 — Inventory, purchasing and vendors (replaces the Mindbody inventory, EA-INV-PROC-01 v3.1 and its
forms, the EA-PO purchase orders and EA-OPS-FRM-08 Monthly Count).

- StockMovement    the ledger: every change to a branch's stock, who, when, why, reference and cost.
- PurchaseRequest  FRM-05 (PRF-): branch asks, the OM decides within 2 business days; one local
                   request per branch per calendar month.
- PurchaseOrder    EA-PO-YYYY-NNN from approved requests, with the landed-cost calculator.
- Receipt          FRM-01 (IRF-): deliveries are received at Promenade only; stock goes up there.
- Discrepancy      FRM-04 (MDR-): raised automatically when received ≠ invoiced.
- Transfer         FRM-03 (ITF-): stock moves only when the receiving branch accepts (rule 9).
- StockCount       FRM-08: monthly count, two people, recount, reason codes, OM approval (rule 10).
- VendorQuote      quotations kept against the vendor.
"""

import secrets
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.members.models import get_private_storage

D = Decimal
ZERO = D("0.000")


def _doc_path(folder):
    def path(instance, filename):
        ext = "pdf" if filename.lower().endswith(".pdf") else "jpg"
        return f"inventory/{folder}/{timezone.localdate():%Y/%m}/{secrets.token_hex(8)}.{ext}"

    path.__name__ = f"{folder}_path"
    path.__qualname__ = path.__name__
    return path


def receipt_invoice_path(instance, filename):
    return _doc_path("receipts")(instance, filename)


def quote_document_path(instance, filename):
    return _doc_path("quotes")(instance, filename)


class StockMovement(models.Model):
    class Kind(models.TextChoices):
        OPENING = "opening", "Opening balance"
        IMPORT = "import", "Imported from Mindbody"
        SALE = "sale", "Sold at the desk"
        FREE_ISSUE = "free_issue", "Free issue (0 KD)"
        REFUND = "refund", "Returned on refund"
        RECEIPT = "receipt", "Received from vendor"
        TRANSFER_OUT = "transfer_out", "Transferred out"
        TRANSFER_IN = "transfer_in", "Transferred in"
        COUNT = "count", "Monthly count correction"
        ONLINE = "online", "Online order fulfilled"
        ADJUST = "adjust", "Other correction (OM)"

    variant = models.ForeignKey("shop.ProductVariant", on_delete=models.PROTECT, related_name="movements")
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="stock_movements")
    change = models.IntegerField()
    balance = models.IntegerField(help_text="Stock on the shelf after this movement.")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    reference = models.CharField(max_length=40, blank=True, help_text="Receipt, form or order reference.")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    reason = models.CharField(max_length=4, blank=True, help_text="Count reason code (US, UT, D, FI, EE, U).")
    note = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["variant", "branch", "created_at"]),
            models.Index(fields=["branch", "kind", "created_at"]),
        ]

    def __str__(self):
        return f"{self.variant} @ {self.branch.code} {self.change:+d} ({self.kind})"


class PurchaseRequest(BaseModel):
    class VendorType(models.TextChoices):
        LOCAL = "local", "Local"
        INTERNATIONAL = "international", "International"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Waiting for the OM"
        APPROVED = "approved", "Approved"
        AMENDED = "amended", "Approved with changes"
        REJECTED = "rejected", "Rejected"
        ORDERED = "ordered", "Ordered"
        RECEIVED = "received", "Received"

    OPEN_FOR_ORDER = (Status.APPROVED, Status.AMENDED)

    reference = models.CharField(max_length=30, unique=True)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="purchase_requests")
    vendor_type = models.CharField(max_length=13, choices=VendorType.choices)
    vendor = models.ForeignKey("finance.Vendor", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.SUBMITTED)
    note = models.CharField(max_length=255, blank=True)
    due_at = models.DateTimeField(help_text="The OM decides within 2 business days.")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)
    reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference

    @property
    def overdue(self):
        return self.status == self.Status.SUBMITTED and timezone.now() > self.due_at


class PurchaseRequestLine(models.Model):
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(
        "shop.ProductVariant", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    item = models.CharField(max_length=120, blank=True, help_text="For items not yet in the catalogue.")
    size = models.CharField(max_length=30, blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    approved_quantity = models.PositiveIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} × {self.quantity}"

    @property
    def name(self):
        return str(self.variant) if self.variant_id else f"{self.item} · {self.size}".strip(" ·")

    @property
    def final_quantity(self):
        return self.quantity if self.approved_quantity is None else self.approved_quantity


class PurchaseOrder(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent to vendor"
        PARTIAL = "partial", "Partly received"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(max_length=20, unique=True)
    vendor = models.ForeignKey("finance.Vendor", on_delete=models.PROTECT, related_name="purchase_orders")
    requests = models.ManyToManyField(PurchaseRequest, related_name="orders", blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    language = models.CharField(max_length=2, default="ar", help_text="Template language sent to the vendor.")
    currency = models.CharField(max_length=3, default="KWD")
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=D("1"), help_text="KWD per 1 unit.")
    freight_kwd = models.DecimalField(
        max_digits=10, decimal_places=3, default=ZERO, help_text="Freight for the order (KD)."
    )
    customs_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=D("20"), help_text="Customs / clearance %."
    )
    target_margin = models.DecimalField(max_digits=5, decimal_places=2, default=D("50"), help_text="Target margin %.")
    note = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.reference


class PurchaseOrderLine(models.Model):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey(
        "shop.ProductVariant", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    item = models.CharField(max_length=120, blank=True)
    size = models.CharField(max_length=30, blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=3, default=ZERO, help_text="In the order currency.")
    received_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} × {self.quantity}"

    @property
    def name(self):
        return str(self.variant) if self.variant_id else f"{self.item} · {self.size}".strip(" ·")

    @property
    def outstanding(self):
        return max(self.quantity - self.received_quantity, 0)


class Receipt(BaseModel):
    reference = models.CharField(max_length=30, unique=True)
    order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.PROTECT, related_name="receipts")
    vendor = models.ForeignKey("finance.Vendor", on_delete=models.PROTECT, related_name="+")
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="+")
    invoice_number = models.CharField(max_length=60)
    invoice = models.FileField(upload_to=receipt_invoice_path, storage=get_private_storage, blank=True)
    received_on = models.DateField(default=timezone.localdate)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-received_on", "-id"]

    def __str__(self):
        return self.reference


class ReceiptLine(models.Model):
    receipt = models.ForeignKey(Receipt, on_delete=models.CASCADE, related_name="lines")
    order_line = models.ForeignKey(
        PurchaseOrderLine, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    variant = models.ForeignKey("shop.ProductVariant", on_delete=models.PROTECT, related_name="+")
    invoiced_quantity = models.PositiveIntegerField()
    received_quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=10, decimal_places=3, help_text="Landed cost per unit (KD).")
    note = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.variant}: {self.received_quantity}/{self.invoiced_quantity}"

    @property
    def shortfall(self):
        return self.invoiced_quantity - self.received_quantity


class Discrepancy(BaseModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"

    reference = models.CharField(max_length=30, unique=True)
    receipt = models.OneToOneField(Receipt, on_delete=models.PROTECT, related_name="discrepancy")
    vendor_notified_on = models.DateField(null=True, blank=True)
    resolution = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "discrepancies"

    def __str__(self):
        return self.reference


class Transfer(BaseModel):
    class Status(models.TextChoices):
        SENT = "sent", "Sent — waiting for the receiving branch"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(max_length=30, unique=True)
    from_branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="transfers_out")
    to_branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="transfers_in")
    receipt = models.ForeignKey(Receipt, null=True, blank=True, on_delete=models.SET_NULL, related_name="transfers")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.SENT)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    sent_at = models.DateTimeField(default=timezone.now)
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    mismatch = models.BooleanField(default=False)
    mismatch_note = models.CharField(max_length=255, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return self.reference


class TransferLine(models.Model):
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey("shop.ProductVariant", on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    received_quantity = models.PositiveIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.variant} × {self.quantity}"


class StockCount(BaseModel):
    """FRM-08. Reason codes follow EA-OPS-PROC-01 §5."""

    class Status(models.TextChoices):
        COUNTING = "counting", "Counting"
        SUBMITTED = "submitted", "Waiting for OM approval"
        APPROVED = "approved", "Approved — stock corrected"
        RETURNED = "returned", "Returned for recount"

    REASONS = [
        ("US", "Unrecorded sale", "بيع غير مسجل"),
        ("UT", "Unrecorded transfer", "تحويل غير مسجل"),
        ("D", "Damaged", "تالف"),
        ("FI", "Free issue not entered", "صرف مجاني غير مسجل"),
        ("EE", "Entry error", "خطأ إدخال"),
        ("U", "Unknown", "غير معروف"),
    ]

    reference = models.CharField(max_length=30, unique=True)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="stock_counts")
    month = models.DateField(help_text="First day of the month counted.")
    count_date = models.DateField()
    due_date = models.DateField(help_text="3rd working day of the next month.")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.COUNTING)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    return_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-month", "branch_id"]
        constraints = [models.UniqueConstraint(fields=["branch", "month"], name="one_count_per_branch_month")]

    def __str__(self):
        return self.reference

    @property
    def overdue(self):
        return self.status in (self.Status.COUNTING, self.Status.RETURNED) and timezone.localdate() > self.due_date


class StockCountLine(models.Model):
    count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="lines")
    variant = models.ForeignKey("shop.ProductVariant", on_delete=models.PROTECT, related_name="+")
    system_quantity = models.IntegerField(help_text="Shelf stock in the system when the sheet was made.")
    counted_quantity = models.IntegerField(null=True, blank=True)
    recount_quantity = models.IntegerField(null=True, blank=True)
    reason = models.CharField(max_length=2, blank=True)
    note = models.CharField(max_length=200, blank=True)
    adjusted_by = models.IntegerField(null=True, blank=True, help_text="Correction applied on approval.")
    short_last_month = models.BooleanField(default=False)

    class Meta:
        ordering = ["variant__product__name_en", "variant__sort_order", "variant_id"]

    def __str__(self):
        return f"{self.variant}: {self.system_quantity} → {self.final_quantity}"

    @property
    def final_quantity(self):
        return self.recount_quantity if self.recount_quantity is not None else self.counted_quantity

    @property
    def difference(self):
        return None if self.final_quantity is None else self.final_quantity - self.system_quantity


class VendorQuote(BaseModel):
    vendor = models.ForeignKey("finance.Vendor", on_delete=models.CASCADE, related_name="quotes")
    date = models.DateField(default=timezone.localdate)
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    currency = models.CharField(max_length=3, default="KWD")
    valid_until = models.DateField(null=True, blank=True)
    document = models.FileField(upload_to=quote_document_path, storage=get_private_storage, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.vendor} · {self.description}"
