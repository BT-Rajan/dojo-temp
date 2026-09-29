import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.crypto import EncryptedTextField
from apps.core.models import BaseModel
from apps.members.models import get_private_storage


class StaffProfile(BaseModel):
    """HR details for a staff user. Pay set-up lives in apps.payroll (PayProfile)."""

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        HOURLY = "hourly", "Hourly (directly hired)"
        FREELANCE = "freelance", "Freelance / contracted (no PIFSS, end-of-service or leave)"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="staff_profile")
    job_title = models.CharField(max_length=100)
    job_title_ar = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(max_length=12, choices=EmploymentType.choices)
    primary_branch = models.ForeignKey(
        "organization.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="staff"
    )
    reports_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    second_lead = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dotted_reports",
        help_text="A second lead (dotted line), e.g. operations staff who also coach. Both leads see instructions.",
    )
    nationality = models.CharField(max_length=60, blank=True)
    civil_id = EncryptedTextField(blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    end_reason = models.CharField(
        max_length=12,
        blank=True,
        choices=[("resignation", "Resignation"), ("termination", "Ended by Elite"), ("contract_end", "Contract ended")],
        help_text="Used for the end-of-service indemnity on the final payslip.",
    )
    disciplines = models.ManyToManyField("organization.Discipline", blank=True, related_name="staff")
    bio = models.TextField(blank=True, help_text="Public instructor profile text.")
    contract_terms = models.TextField(blank=True, help_text="Hours, probation, notice period, other terms.")

    AUDIT_REDACT = ("civil_id",)

    class Meta:
        ordering = ["user__full_name"]

    def __str__(self):
        return f"{self.user} — {self.job_title}"


def staff_document_path(instance, filename):
    ext = "pdf" if filename.lower().endswith(".pdf") else "jpg"
    return f"staff/{instance.staff_id}/{secrets.token_hex(8)}.{ext}"


class StaffDocument(BaseModel):
    """Civil ID, residency, work permit, passport and coaching certificates, with expiry reminders."""

    class Kind(models.TextChoices):
        CIVIL_ID = "civil_id", "Civil ID"
        RESIDENCY = "residency", "Residency"
        WORK_PERMIT = "work_permit", "Work permit"
        PASSPORT = "passport", "Passport"
        CERTIFICATE = "certificate", "Coaching certificate"
        FIRST_AID = "first_aid", "First aid certificate"
        CONTRACT = "contract", "Employment contract"
        OTHER = "other", "Other"

    REMIND_DAYS = (60, 30, 7)

    staff = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    title = models.CharField(max_length=120, blank=True, help_text="e.g. the certificate name.")
    number = EncryptedTextField(blank=True)
    expires_on = models.DateField(null=True, blank=True)
    file = models.FileField(upload_to=staff_document_path, storage=get_private_storage, blank=True)
    reminders_sent = models.JSONField(default=list, blank=True)

    AUDIT_REDACT = ("number",)

    class Meta:
        ordering = ["expires_on", "kind"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.staff.user.full_name}"

    @property
    def days_left(self):
        return (self.expires_on - timezone.localdate()).days if self.expires_on else None
