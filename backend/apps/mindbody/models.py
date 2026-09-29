"""
M18 — Replacing Mindbody (scope Section 6, decisions P3-8 to P3-10).

- ImportBatch       one uploaded Mindbody export: dry run first (report only), then applied.
- ExternalRef       Mindbody ID → our record, so re-running an import updates instead of duplicating
                    (the same tool does the final delta at cut-over).
- OptionMap         each Mindbody pricing option name (per branch) → a pricing option here, or skipped.
- ParallelRunCheck  a week's Mindbody figures typed in next to the system's, with the difference explained.
- CutoverStep       the cut-over checklist.
"""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.members.models import get_private_storage


def import_file_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "dat"
    ext = ext if ext in ("csv", "xls", "xlsx", "txt", "htm", "html") else "dat"
    return f"mindbody/{timezone.localdate():%Y/%m}/{secrets.token_hex(8)}.{ext}"


class ImportBatch(BaseModel):
    class Kind(models.TextChoices):
        CLIENTS = "clients", "Clients"
        RELATIONSHIPS = "relationships", "Client relationships (families)"
        MEMBERSHIPS = "memberships", "Pricing option expirations (memberships)"
        VISITS = "visits", "Visit history"
        SALES = "sales", "Sales"
        INVENTORY = "inventory", "Inventory on hand"

    ORDER = [Kind.CLIENTS, Kind.RELATIONSHIPS, Kind.INVENTORY, Kind.MEMBERSHIPS, Kind.VISITS, Kind.SALES]

    class Status(models.TextChoices):
        CHECKED = "checked", "Dry run done — nothing changed yet"
        APPLIED = "applied", "Applied"
        FAILED = "failed", "Could not be read"

    kind = models.CharField(max_length=13, choices=Kind.choices)
    branch = models.ForeignKey(
        "organization.Branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Used when the file has no location column.",
    )
    file = models.FileField(upload_to=import_file_path, storage=get_private_storage)
    original_name = models.CharField(max_length=200)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.CHECKED)
    rows = models.PositiveIntegerField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    issues = models.JSONField(default=list, blank=True)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    applied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.original_name}"


class ExternalRef(models.Model):
    kind = models.CharField(max_length=20)
    external_id = models.CharField(max_length=120)
    object_id = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kind", "external_id"], name="one_ref_per_external_id")]
        indexes = [models.Index(fields=["kind", "object_id"])]

    def __str__(self):
        return f"{self.kind}:{self.external_id} → {self.object_id}"


class OptionMap(BaseModel):
    mindbody_name = models.CharField(max_length=200)
    branch = models.ForeignKey("organization.Branch", on_delete=models.CASCADE, related_name="+")
    pricing_option = models.ForeignKey(
        "organization.PricingOption", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    skip = models.BooleanField(default=False, help_text="Not brought across (e.g. test options, old events).")

    class Meta:
        ordering = ["branch_id", "mindbody_name"]
        constraints = [models.UniqueConstraint(fields=["mindbody_name", "branch"], name="one_map_per_option")]

    def __str__(self):
        return f"{self.mindbody_name} ({self.branch.code})"

    @property
    def done(self):
        return self.skip or self.pricing_option_id is not None


class ParallelRunCheck(BaseModel):
    """One branch, one week: Mindbody's numbers (typed from its reports) against the system's."""

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="+")
    week_start = models.DateField()
    mb_knet = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    mb_card = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    mb_cash = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    mb_active_members = models.PositiveIntegerField(default=0)
    system = models.JSONField(default=dict, blank=True)
    explanation = models.TextField(blank=True)
    agreed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-week_start", "branch_id"]
        constraints = [models.UniqueConstraint(fields=["branch", "week_start"], name="one_check_per_branch_week")]

    def __str__(self):
        return f"Parallel run {self.branch.code} {self.week_start}"


class CutoverStep(BaseModel):
    order = models.PositiveSmallIntegerField()
    title_en = models.CharField(max_length=200)
    title_ar = models.CharField(max_length=200)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    done_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.title_en
