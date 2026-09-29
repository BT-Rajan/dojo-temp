"""
M17 — messages to families and staff (decisions P6-7 to P6-9).

- MessageLog         every outgoing message: to whom, channel, category, what, and whether it went.
- FamilyPreference   a family's choice (by contact mobile) to stop service messages; essential ones always go.
- MessageTemplate    the Marketing Lead's wording overrides for a message key, in English and Arabic.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Category(models.TextChoices):
    ESSENTIAL = "essential", "Essential (always sent)"
    SERVICE = "service", "Service (family can turn off)"
    MARKETING = "marketing", "Marketing (opt-in only)"
    STAFF = "staff", "Staff alert"


class MessageLog(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        SKIPPED = "skipped", "Not sent (family turned these off)"
        FAILED = "failed", "Failed"

    to = models.CharField(max_length=32, db_index=True)
    channel = models.CharField(max_length=10, default="whatsapp")
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.ESSENTIAL)
    kind = models.CharField(max_length=40, blank=True)
    text = models.TextField()
    member = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.SENT)
    error = models.CharField(max_length=255, blank=True)
    at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-at", "-id"]

    def __str__(self):
        return f"{self.kind or self.category} → {self.to}"


class FamilyPreference(models.Model):
    mobile = models.CharField(max_length=16, unique=True)
    service_messages = models.BooleanField(default=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.mobile}: service {'on' if self.service_messages else 'off'}"


class MessageTemplate(models.Model):
    key = models.CharField(max_length=40, unique=True)
    text_en = models.TextField()
    text_ar = models.TextField()
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key
