"""
M6 — Renewals and retention (replaces EA-OPS-FRM-02 and Guide G2).

The daily follow-up list itself is calculated (see services.follow_up_list); this app keeps
what people did about it: every contact attempt and its outcome, the hand-over to the
instructor after three unanswered attempts, and the automatic reminders that were sent.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class FollowUp(models.Model):
    class Outcome(models.TextChoices):
        RENEWED = "R", "R · Renewed"
        WILL_RENEW = "W", "W · Will renew"
        FREEZE = "F", "F · Freeze requested"
        LEAVING = "L", "L · Leaving"
        NO_ANSWER = "N", "N · No answer"

    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        CALL = "call", "Phone call"
        IN_PERSON = "in_person", "In person"

    membership = models.ForeignKey("sales.Membership", on_delete=models.CASCADE, related_name="follow_ups")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="follow_ups")
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="+")
    outcome = models.CharField(max_length=1, choices=Outcome.choices)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.WHATSAPP)
    attempt = models.PositiveSmallIntegerField(default=1, help_text="No-answer attempt number (1–3).")
    will_renew_on = models.DateField(null=True, blank=True)
    leaving_reason = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=255, blank=True)
    contacted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["membership", "created_at"])]

    def __str__(self):
        return f"{self.member} · {self.outcome} ({self.created_at:%Y-%m-%d})"


class InstructorHandoff(models.Model):
    """After three unanswered attempts the member's instructor has a personal word at class."""

    membership = models.OneToOneField("sales.Membership", on_delete=models.CASCADE, related_name="handoff")
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="+")
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="renewal_handoffs"
    )
    created_at = models.DateTimeField(default=timezone.now)
    done_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Talk to {self.member}"


class ReminderSent(models.Model):
    """Automatic renewal reminders (5 and 1 days before expiry); one per membership per day-mark."""

    membership = models.ForeignKey("sales.Membership", on_delete=models.CASCADE, related_name="reminders")
    days_before = models.PositiveSmallIntegerField()
    sent_to = models.CharField(max_length=16)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["membership", "days_before"], name="one_reminder_per_mark")]

    def __str__(self):
        return f"Reminder {self.days_before}d · {self.membership_id}"
