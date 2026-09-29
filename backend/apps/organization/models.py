from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class Branch(BaseModel):
    code = models.SlugField(max_length=20, unique=True, help_text="Short code for reference numbers, e.g. PRM, BED.")
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100)
    area = models.CharField(max_length=100, help_text="e.g. Hawalli, Sabah Al Salem")
    area_ar = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=16, blank=True)
    # Weekday numbers the branch is open, Kuwait style: 0=Saturday … 6=Friday
    open_days = models.JSONField(default=list, blank=True)
    positioning = models.CharField(max_length=150, blank=True, help_text="e.g. The Complete Fighter Program")
    google_review_url = models.URLField(blank=True, help_text="Google Business Profile review link (decision P5-9).")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "branches"

    def __str__(self):
        return self.name


class Discipline(BaseModel):
    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=80)
    name_ar = models.CharField(max_length=80)
    track = models.CharField(
        max_length=20,
        choices=[("striking", "Striking"), ("grappling", "Grappling"), ("mixed", "Mixed"), ("other", "Other")],
        default="other",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Program(BaseModel):
    """A class offering at a branch, e.g. 'Kajukenbo – Boys 6-13' or 'Elite Promenade All-Access 5-7'."""

    class Audience(models.TextChoices):
        ANY = "any", "Everyone"
        BOYS = "boys", "Boys"
        MEN = "men", "Men"
        LADIES = "ladies", "Girls & ladies"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="programs")
    name = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    disciplines = models.ManyToManyField(Discipline, related_name="programs")
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.ANY)
    age_min = models.PositiveSmallIntegerField(null=True, blank=True)
    age_max = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["branch__name", "name"]
        unique_together = [("branch", "name")]

    def __str__(self):
        return f"{self.name} ({self.branch.code})"


class PricingOption(BaseModel):
    """
    What a client buys. `kind` replaces the old ">12 KD" rule: only MEMBERSHIP kinds
    count towards active members (EA-OPS-PROC-01 §3.2).
    """

    class Kind(models.TextChoices):
        MEMBERSHIP = "membership", "Membership / class package"
        TRIAL = "trial", "Trial pass"
        DAY_PASS = "day_pass", "Day pass"
        PRIVATE = "private", "Private session"
        SEMINAR = "seminar", "Seminar"
        CAMP = "camp", "Camp"
        EVENT = "event", "Event"
        OTHER = "other", "Other (not a membership)"

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="pricing_options")
    name = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120, blank=True)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    programs = models.ManyToManyField(Program, related_name="pricing_options", blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])

    class Approval(models.TextChoices):
        PENDING = "pending", "Waiting for Operations Manager approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    duration_days = models.PositiveSmallIntegerField(null=True, blank=True, help_text="How long it stays valid.")
    sessions_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    total_sessions = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Session packages: e.g. 10 for a 10×4 package (10 sessions in 4 weeks)."
    )
    package_weeks = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Session packages: weeks to use the sessions, e.g. 4 for 10×4."
    )
    all_access = models.BooleanField(default=False, help_text="Covers every program at the branch.")
    family_discount_allowed = models.BooleanField(default=True)
    active_from = models.DateField(null=True, blank=True)
    active_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    # A new option (and every price change) goes live only after the Operations Manager approves it (FRM-05).
    approval = models.CharField(max_length=10, choices=Approval.choices, default=Approval.PENDING)

    class Meta:
        ordering = ["branch__name", "kind", "name"]
        unique_together = [("branch", "name")]

    def __str__(self):
        return f"{self.name} — {self.price} KD"

    @property
    def counts_as_membership(self) -> bool:
        return self.kind == self.Kind.MEMBERSHIP

    @property
    def validity_days(self) -> int | None:
        """Days a purchase stays valid: the duration, or the package weeks."""
        if self.duration_days:
            return self.duration_days
        if self.package_weeks:
            return self.package_weeks * 7
        return None

    def is_sellable(self, on=None) -> bool:
        from django.utils import timezone

        on = on or timezone.localdate()
        return (
            self.is_active
            and self.approval == self.Approval.APPROVED
            and (self.active_from is None or self.active_from <= on)
            and (self.active_until is None or self.active_until >= on)
        )


class PriceChange(BaseModel):
    """
    A requested price change. It changes nothing until the Operations Manager approves it;
    then the new price applies from `effective_from` (EA-OPS-FRM-05 rule, scope M1).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        APPLIED = "applied", "Applied"

    pricing_option = models.ForeignKey(PricingOption, on_delete=models.PROTECT, related_name="price_changes")
    old_price = models.DecimalField(max_digits=10, decimal_places=3)
    new_price = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal("0"))])
    effective_from = models.DateField()
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.pricing_option}: {self.old_price} → {self.new_price}"

    @property
    def branch_id(self):
        return self.pricing_option.branch_id


class Room(BaseModel):
    """A mat or studio. One per branch unless the academy adds more."""

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="rooms")
    name = models.CharField(max_length=60)
    name_ar = models.CharField(max_length=60, blank=True)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Safe number on the mat.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["branch__name", "name"]
        unique_together = [("branch", "name")]

    def __str__(self):
        return f"{self.name} ({self.branch.code})"
