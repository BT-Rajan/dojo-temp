"""
M10 — Reports (replaces EA-OPS-FRM-06, FRM-07, the Active Members Report EA-DOC-003 and the
Mindbody reporting cadence).

Figures are always calculated from live data. When a Branch Admin prepares a weekly report the
figures are frozen into `data`, so what the OM verifies can never change afterwards; if the live
figures move later (a late refund), the report shows that it differs from the verified copy.
"""

import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


def week_start(day: datetime.date) -> datetime.date:
    """Reporting week Saturday–Friday (business rule 3)."""
    return day - datetime.timedelta(days=(day.weekday() - 5) % 7)


class WeeklyReport(BaseModel):
    class Kind(models.TextChoices):
        SALES = "sales", "Weekly Sales Report (FRM-06)"
        BRANCH = "branch", "Weekly Branch Report (FRM-07)"

    class Status(models.TextChoices):
        PREPARED = "prepared", "Waiting for OM verification"
        VERIFIED = "verified", "Verified"
        RETURNED = "returned", "Returned for correction"

    FORM = {Kind.SALES: "FRM-06", Kind.BRANCH: "FRM-07"}

    kind = models.CharField(max_length=6, choices=Kind.choices)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="weekly_reports")
    week_start = models.DateField()
    reference = models.CharField(max_length=30, unique=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PREPARED)
    data = models.JSONField(default=dict)
    # FRM-07 text sections (the figures fill themselves in)
    leaving_reasons = models.TextField(blank=True)
    facility_issues = models.TextField(blank=True)
    om_decisions = models.TextField(blank=True)
    prepared_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    prepared_at = models.DateTimeField(default=timezone.now)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    return_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-week_start", "branch_id", "kind"]
        constraints = [
            models.UniqueConstraint(fields=["kind", "branch", "week_start"], name="one_report_per_branch_week")
        ]

    def __str__(self):
        return self.reference

    @property
    def week_end(self):
        return self.week_start + datetime.timedelta(days=6)

    @property
    def due_at(self):
        """Due Saturday 12:00 after the week ends."""
        return timezone.make_aware(
            datetime.datetime.combine(self.week_end + datetime.timedelta(days=1), datetime.time(12, 0))
        )


class ActiveMembersSnapshot(models.Model):
    """Taken every Friday night per branch, for the week-over-week change."""

    date = models.DateField()
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="+")
    total = models.PositiveIntegerField()
    by_program = models.JSONField(default=dict)
    member_ids = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["date", "branch"], name="one_snapshot_per_branch_day")]

    def __str__(self):
        return f"Active members {self.branch.code} {self.date}: {self.total}"


class ReportSubscription(BaseModel):
    """'Email me this report': sent automatically to people who may see it (checked at every send)."""

    class Report(models.TextChoices):
        WEEKLY_SALES = "weekly_sales", "Weekly Sales Report (every Saturday)"
        WEEKLY_BRANCH = "weekly_branch", "Weekly Branch Report (every Saturday)"
        ACTIVE_MEMBERS = "active_members", "Active Members (every Friday)"
        DAILY = "daily", "Daily dashboard (every morning)"
        MONTHLY = "monthly", "Monthly dashboard (1st of the month)"

    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        XLSX = "xlsx", "Excel"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="report_subscriptions")
    report = models.CharField(max_length=16, choices=Report.choices)
    branch = models.ForeignKey(
        "organization.Branch",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="Empty = both branches combined.",
    )
    format = models.CharField(max_length=4, choices=Format.choices, default=Format.PDF)
    language = models.CharField(max_length=2, default="en")
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user_id", "report"]

    def __str__(self):
        return f"{self.user} · {self.get_report_display()}"
