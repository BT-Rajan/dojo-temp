"""
M9 — Daily operations (replaces EA-OPS-FRM-01, FRM-09, FRM-10 and FRM-11).

- ShiftOpening     the 9-point checklist, completed and signed before the first class.
- Incident         injury / safety hazard / conduct; guardian told at once for children, OM the
                   same day, CEO within 24 hours for safety or removal decisions (rule 11).
- Complaint        logged the same day, reply within 24 hours, closed only when the member has
                   been told the outcome (rule 12).
- Handover         cover named by the OM; the open-items list is built by the system and the
                   incoming person accepts each item; a leaver's access ends on the last day (rule 16).
- ReferenceCounter Elite's reference numbers, e.g. FRM-09-BED-2026-004.
"""

import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel

# (code, English, Arabic). Item 9 carries any hazard, which goes straight to the OM.
SHIFT_CHECKS = [
    ("lights", "Lights, A/C and reception equipment on", "الإضاءة والتكييف وأجهزة الاستقبال تعمل"),
    ("floor", "Training floor and mats clean and safe", "أرضية التدريب والحصائر نظيفة وآمنة"),
    ("changing", "Changing areas and toilets clean", "غرف التبديل ودورات المياه نظيفة"),
    ("reception", "Reception tidy; forms and receipt paper stocked", "الاستقبال مرتب والنماذج وورق الإيصالات متوفرة"),
    (
        "schedule",
        "Signed in to the desk; today's classes, bookings and trials checked",
        "تم الدخول إلى المكتب ومراجعة حصص اليوم والحجوزات والتجارب",
    ),
    ("website", "Website schedule shows today's classes correctly", "جدول الموقع يعرض حصص اليوم بشكل صحيح"),
    ("renewals", "Renewals follow-up list reviewed", "تمت مراجعة قائمة متابعة التجديدات"),
    ("saqr", "SAQR conversations since the last shift reviewed", "تمت مراجعة محادثات صقر منذ آخر نوبة"),
    ("hazards", "Hazards or faults reported to the OM", "تم إبلاغ مدير العمليات بأي مخاطر أو أعطال"),
]
SHIFT_CHECK_CODES = [c for c, *_ in SHIFT_CHECKS]


class ReferenceCounter(models.Model):
    form = models.CharField(max_length=10)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="+")
    year = models.PositiveSmallIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["form", "branch", "year"], name="one_counter_per_form")]

    def __str__(self):
        return f"{self.form}-{self.branch.code}-{self.year}: {self.last_number}"


class ShiftOpening(BaseModel):
    class Shift(models.TextChoices):
        MORNING = "morning", "Morning"
        EVENING = "evening", "Afternoon / evening"

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="shift_openings")
    date = models.DateField()
    shift = models.CharField(max_length=8, choices=Shift.choices)
    done = models.JSONField(default=list, help_text="Codes of the checks ticked.")
    notes = models.JSONField(default=dict, blank=True, help_text="Note per check code.")
    hazard = models.TextField(blank=True, help_text="Any hazard or fault; sent to the OM straight away.")
    completed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-date", "-completed_at"]
        constraints = [
            models.UniqueConstraint(fields=["branch", "date", "shift"], name="one_opening_per_shift"),
        ]

    def __str__(self):
        return f"Shift opening {self.branch.code} {self.date} {self.shift}"


class Incident(BaseModel):
    class Kind(models.TextChoices):
        INJURY = "injury", "Injury"
        HAZARD = "hazard", "Safety hazard"
        CONDUCT = "conduct", "Conduct"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    CEO_HOURS = 24

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="incidents")
    reference = models.CharField(max_length=30, unique=True)
    occurred_at = models.DateTimeField()
    kind = models.CharField(max_length=8, choices=Kind.choices)
    member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.PROTECT, related_name="incidents"
    )
    people = models.TextField(blank=True, help_text="Everyone involved: name, age, guardian.")
    session = models.ForeignKey(
        "classes.ClassSession", null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents"
    )
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    what_happened = models.TextField()
    action_taken = models.TextField(help_text="First aid, ambulance, class stopped…")
    guardian_informed_name = models.CharField(max_length=150, blank=True)
    guardian_informed_at = models.DateTimeField(null=True, blank=True)
    witnesses = models.TextField(blank=True)
    om_notified_at = models.DateTimeField(null=True, blank=True)
    needs_ceo = models.BooleanField(default=False, help_text="A safety matter or a decision to remove someone.")
    ceo_due_at = models.DateTimeField(null=True, blank=True)
    ceo_escalated_at = models.DateTimeField(null=True, blank=True)
    ceo_escalated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    ceo_auto_escalated = models.BooleanField(default=False)
    follow_up_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    follow_up_due = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    closure_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["branch", "status"]), models.Index(fields=["status", "ceo_due_at"])]

    def __str__(self):
        return self.reference

    @property
    def ceo_overdue(self):
        return (
            self.needs_ceo
            and self.ceo_escalated_at is None
            and self.ceo_due_at is not None
            and timezone.now() > self.ceo_due_at
        )

    @property
    def ceo_hours_left(self):
        if not self.needs_ceo or self.ceo_escalated_at or self.ceo_due_at is None:
            return None
        return (self.ceo_due_at - timezone.now()).total_seconds() / 3600


class Complaint(BaseModel):
    class Channel(models.TextChoices):
        DESK = "desk", "Front desk"
        WHATSAPP = "whatsapp", "WhatsApp"
        SAQR = "saqr", "SAQR chat"
        CALL = "call", "Phone call"

    class Category(models.TextChoices):
        MONEY = "money", "Money or billing"
        REFUND = "refund", "Refund"
        STAFF = "staff", "Staff conduct"
        SAFETY = "safety", "Safety"
        LEAVING = "leaving", "Threat to leave"
        CLASSES = "classes", "Classes or schedule"
        FACILITY = "facility", "Facility"
        OTHER = "other", "Other"

    # These always go to the OM (scope M9).
    ESCALATE = {Category.MONEY, Category.REFUND, Category.STAFF, Category.SAFETY, Category.LEAVING}
    REPLY_HOURS = 24

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="complaints")
    reference = models.CharField(max_length=30, unique=True)
    received_at = models.DateTimeField(default=timezone.now)
    member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.PROTECT, related_name="complaints"
    )
    contact_name = models.CharField(max_length=150, blank=True)
    contact_mobile = models.CharField(max_length=16, blank=True)
    channel = models.CharField(max_length=8, choices=Channel.choices)
    category = models.CharField(max_length=8, choices=Category.choices)
    details = models.TextField()
    handled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    escalated = models.BooleanField(default=False)
    reply_due_at = models.DateTimeField()
    replied_at = models.DateTimeField(null=True, blank=True)
    reply_reminder_sent = models.BooleanField(default=False)
    action_outcome = models.TextField(blank=True)
    member_informed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-received_at"]
        indexes = [models.Index(fields=["branch", "status"]), models.Index(fields=["status", "reply_due_at"])]

    def __str__(self):
        return self.reference

    @property
    def who(self):
        return str(self.member) if self.member_id else self.contact_name

    @property
    def reply_overdue(self):
        return self.replied_at is None and timezone.now() > self.reply_due_at


class Handover(BaseModel):
    """FRM-11 Cover & Handover. Items: [{code, en, ar, details, accepted_at}]."""

    class Status(models.TextChoices):
        OPEN = "open", "Waiting for the incoming person"
        ACCEPTED = "accepted", "Accepted"

    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="handovers")
    outgoing = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="handovers_out")
    incoming = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="handovers_in")
    cover_from = models.DateField()
    cover_to = models.DateField(null=True, blank=True)
    outgoing_leaving = models.BooleanField(default=False, help_text="The outgoing person is leaving Elite.")
    last_day = models.DateField(null=True, blank=True, help_text="Their access ends after this day.")
    items = models.JSONField(default=list)
    note = models.TextField(blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-cover_from", "-id"]

    def __str__(self):
        return f"Handover {self.branch.code} {self.outgoing} → {self.incoming}"

    @property
    def items_left(self):
        return sum(1 for i in self.items if not i.get("accepted_at"))

    @property
    def access_ends_on(self):
        return self.last_day + datetime.timedelta(days=1) if self.last_day else None
