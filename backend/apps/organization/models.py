from decimal import Decimal

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
    duration_days = models.PositiveSmallIntegerField(null=True, blank=True, help_text="How long it stays valid.")
    sessions_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    total_sessions = models.PositiveSmallIntegerField(null=True, blank=True)
    active_from = models.DateField(null=True, blank=True)
    active_until = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["branch__name", "kind", "name"]
        unique_together = [("branch", "name")]

    def __str__(self):
        return f"{self.name} — {self.price} KD"

    @property
    def counts_as_membership(self) -> bool:
        return self.kind == self.Kind.MEMBERSHIP
