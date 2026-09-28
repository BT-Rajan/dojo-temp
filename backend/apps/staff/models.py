from django.conf import settings
from django.db import models

from apps.core.crypto import EncryptedTextField
from apps.core.models import BaseModel


class StaffProfile(BaseModel):
    """HR details for a staff user. Payroll fields are added in Phase 2 (M20)."""

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        HOURLY = "hourly", "Hourly (directly hired)"
        FREELANCE = "freelance", "Freelance / contracted (paid as vendor)"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="staff_profile")
    job_title = models.CharField(max_length=100)
    job_title_ar = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(max_length=12, choices=EmploymentType.choices)
    primary_branch = models.ForeignKey(
        "organization.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="staff"
    )
    reports_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    nationality = models.CharField(max_length=60, blank=True)
    civil_id = EncryptedTextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    disciplines = models.ManyToManyField("organization.Discipline", blank=True, related_name="staff")
    bio = models.TextField(blank=True, help_text="Public instructor profile text.")

    AUDIT_REDACT = ("civil_id",)

    class Meta:
        ordering = ["user__full_name"]

    def __str__(self):
        return f"{self.user} — {self.job_title}"
