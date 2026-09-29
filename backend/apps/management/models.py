"""
M12 — Communication and management (replaces the mechanics of EA-COMM-PROC-01, the Monthly Leads Meeting MOM
template and the escalation logs) and the Quarterly Business Report EA-OPS-RPT-01.

- Announcement / Recipient   a decision posted once and forwarded unchanged down the chain; every person confirms
                             receipt; leads forward within 2 working days (EA-COMM-PROC-01 §4).
- Handoff                    a request between leads (or to Systems & IT) that the receiver confirms (§5.2); an IT
                             request needs a committed date before work starts.
- Meeting                    the monthly leads meeting: attendance, agenda, decisions and action items (MOM template).
- LeadReport                 the monthly summary from each lead to the CEO, pre-filled from the system (§6.1).
- Escalation                 a safety or conduct concern: same day to the lead, an owner named at once, the CEO within
                             24 hours when member safety or a removal is involved, or straight to the CEO (§6.2, §6.3).
- Procedure / version        the library of procedures, forms and policies with version, effective date, owner,
                             approval and staff read-confirmations.
- QuarterlyReport            RPT-01, frozen when the OM submits it to the CEO.
"""

import datetime
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.members.models import get_private_storage

User = settings.AUTH_USER_MODEL


# ---------------------------------------------------------------------------
# Announcements and the cascade
# ---------------------------------------------------------------------------
class Announcement(BaseModel):
    title = models.CharField(max_length=200)
    body = models.TextField()
    sender = models.ForeignKey(User, on_delete=models.PROTECT, related_name="announcements_sent")
    forwarded_from = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="forwards")
    root = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="+", help_text="The original post."
    )
    sent_at = models.DateTimeField(default=timezone.now)
    confirm_by = models.DateField(help_text="Receipt confirmed, and forwarded by leads, within 2 working days.")

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return self.title

    @property
    def original(self):
        return self.root or self


class Recipient(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="announcements_received")
    is_copy = models.BooleanField(
        default=False, help_text="A copy for the person's other lead (dual reporting line); no confirmation needed."
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    reminded_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["announcement_id", "user__full_name"]
        constraints = [models.UniqueConstraint(fields=["announcement", "user"], name="one_recipient_per_post")]

    def __str__(self):
        return f"{self.announcement} → {self.user}"


# ---------------------------------------------------------------------------
# Handoffs between leads (and requests to Systems & IT)
# ---------------------------------------------------------------------------
class Handoff(BaseModel):
    class Kind(models.TextChoices):
        STORIES = "stories", "Progress stories and program knowledge (Training → Marketing)"
        MESSAGE = "message", "Check a marketing message is accurate (Marketing → Training)"
        LEADS = "leads", "Campaign leads to log (Marketing → Operations)"
        RESULTS = "results", "Conversion results and class photos (Operations → Marketing)"
        ATTENDANCE = "attendance", "Attendance, progress and concerns (Training → Operations)"
        BOOKINGS = "bookings", "Bookings and member processes (Operations → Training)"
        IT_REQUEST = "it_request", "Request to Systems & IT (tool, change or support)"
        IT_NOTICE = "it_notice", "Notice of a system change (Systems & IT → affected lead)"
        UPDATE = "update", "Update or issue for the CEO between monthly reports"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SENT = "sent", "Waiting for confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        DONE = "done", "Done"
        DECLINED = "declined", "Declined"

    class Urgency(models.TextChoices):
        LOW = "low", "Can wait"
        NORMAL = "normal", "Normal"
        HIGH = "high", "Soon"
        URGENT = "urgent", "Urgent"

    OPEN = (Status.SENT, Status.CONFIRMED)

    reference = models.CharField(max_length=20, unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    sender = models.ForeignKey(User, on_delete=models.PROTECT, related_name="handoffs_sent")
    receiver = models.ForeignKey(User, on_delete=models.PROTECT, related_name="handoffs_received")
    subject = models.CharField(max_length=200)
    detail = models.TextField()
    # Change requests to Systems & IT (scope 7.1): why, who benefits, how urgent.
    why = models.TextField(blank=True)
    benefits = models.CharField(max_length=255, blank=True)
    urgency = models.CharField(max_length=6, choices=Urgency.choices, default=Urgency.NORMAL)
    go_live = models.DateField(null=True, blank=True, help_text="For a system change notice: when it goes live.")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.SENT)
    confirm_by = models.DateField()
    confirmed_at = models.DateTimeField(null=True, blank=True)
    committed_date = models.DateField(null=True, blank=True, help_text="Systems & IT's committed timeline.")
    response = models.TextField(blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    reminded_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["receiver", "status"])]

    def __str__(self):
        return f"{self.reference} {self.subject}"

    @property
    def overdue(self):
        return self.status == self.Status.SENT and self.confirm_by < timezone.localdate()


# ---------------------------------------------------------------------------
# The monthly leads meeting (MOM template)
# ---------------------------------------------------------------------------
class Meeting(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft minutes"
        PUBLISHED = "published", "Minutes sent"

    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=120, blank=True, help_text="Room or platform.")
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    prepared_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    next_date = models.DateField(null=True, blank=True)
    next_time = models.TimeField(null=True, blank=True)
    next_location = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"Leads meeting {self.date:%d/%m/%Y}"


class MeetingAttendee(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="attendees")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    present = models.BooleanField(default=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True, help_text="Acknowledged the minutes.")

    class Meta:
        ordering = ["user__full_name"]
        constraints = [models.UniqueConstraint(fields=["meeting", "user"], name="one_attendee_row")]

    def __str__(self):
        return f"{self.user} @ {self.meeting}"


class AgendaItem(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="agenda")
    topic = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    raised_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.topic


class Decision(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="decisions")
    text = models.TextField()
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.text[:60]


class ActionItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        DROPPED = "dropped", "Dropped"

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="actions")
    action = models.TextField()
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="action_items")
    due = models.DateField()
    status = models.CharField(max_length=7, choices=Status.choices, default=Status.OPEN)
    done_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["due", "id"]

    def __str__(self):
        return self.action[:60]


# ---------------------------------------------------------------------------
# Monthly upward reports
# ---------------------------------------------------------------------------
class LeadReport(BaseModel):
    class Function(models.TextChoices):
        TRAINING = "training", "Training"
        OPERATIONS = "operations", "Operations"
        MARKETING = "marketing", "Marketing"
        IT = "it", "Systems & IT"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Sent to the CEO"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"

    month = models.DateField(help_text="First day of the month reported on.")
    function = models.CharField(max_length=10, choices=Function.choices)
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="lead_reports")
    data = models.JSONField(default=dict, help_text="The figures, frozen when sent.")
    summary = models.TextField(blank=True)
    concerns = models.TextField(blank=True, help_text="Unresolved concerns and what is needed.")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    submitted_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    ceo_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-month", "function"]
        constraints = [models.UniqueConstraint(fields=["month", "function"], name="one_lead_report_per_month")]

    def __str__(self):
        return f"{self.get_function_display()} report {self.month:%m/%Y}"


# ---------------------------------------------------------------------------
# Escalation log
# ---------------------------------------------------------------------------
class Escalation(BaseModel):
    class Kind(models.TextChoices):
        SAFETY = "safety", "Safety"
        CONDUCT = "conduct", "Conduct"
        OTHER = "other", "Other urgent matter"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    CEO_HOURS = 24

    reference = models.CharField(max_length=20, unique=True)
    kind = models.CharField(max_length=7, choices=Kind.choices)
    raised_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="escalations_raised")
    raised_at = models.DateTimeField(default=timezone.now)
    branch = models.ForeignKey("organization.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    lead = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.PROTECT, related_name="escalations_to_me", help_text="Their lead."
    )
    description = models.TextField()
    needs_ceo = models.BooleanField(default=False, help_text="Member safety or a possible removal decision.")
    ceo_due_at = models.DateTimeField(null=True, blank=True)
    ceo_informed_at = models.DateTimeField(null=True, blank=True)
    ceo_informed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    ceo_auto = models.BooleanField(default=False, help_text="Sent to the CEO by the system when the 24 hours ran out.")
    direct_to_ceo = models.BooleanField(
        default=False, help_text="Raised straight with the CEO because the lead was not answering or acting."
    )
    direct_call_at = models.DateTimeField(null=True, blank=True, help_text="When the CEO was called.")
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="escalations_owned")
    owner_named_at = models.DateTimeField(null=True, blank=True)
    incident = models.ForeignKey(
        "operations.Incident", null=True, blank=True, on_delete=models.SET_NULL, related_name="escalations"
    )
    status = models.CharField(max_length=6, choices=Status.choices, default=Status.OPEN)
    outcome = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-raised_at"]
        indexes = [models.Index(fields=["status", "ceo_due_at"])]

    def __str__(self):
        return self.reference

    @property
    def ceo_overdue(self):
        return bool(
            self.needs_ceo and self.ceo_informed_at is None and self.ceo_due_at and self.ceo_due_at < timezone.now()
        )


class EscalationNote(models.Model):
    escalation = models.ForeignKey(Escalation, on_delete=models.CASCADE, related_name="notes")
    by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(default=timezone.now)
    text = models.TextField()

    class Meta:
        ordering = ["at"]

    def __str__(self):
        return f"{self.escalation} note"


# ---------------------------------------------------------------------------
# Procedure library
# ---------------------------------------------------------------------------
class Procedure(BaseModel):
    class Kind(models.TextChoices):
        PROCEDURE = "procedure", "Procedure"
        FORM = "form", "Form"
        POLICY = "policy", "Policy"
        REFERENCE = "reference", "Reference"

    code = models.CharField(max_length=30, unique=True, help_text="e.g. EA-COMM-PROC-01")
    title = models.CharField(max_length=200)
    title_ar = models.CharField(max_length=200, blank=True)
    kind = models.CharField(max_length=9, choices=Kind.choices, default=Kind.PROCEDURE)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="procedures_owned")
    audience = models.JSONField(
        default=list, blank=True, help_text="Role codes who must read it; empty means all staff."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.title}"

    @property
    def current(self):
        return self.versions.filter(status=ProcedureVersion.Status.APPROVED).order_by("-effective_date", "-id").first()


def procedure_file_path(instance, filename):
    ext = "pdf" if filename.lower().endswith(".pdf") else "jpg"
    return f"procedures/{instance.procedure_id}/{secrets.token_hex(8)}.{ext}"


class ProcedureVersion(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Waiting for approval"
        APPROVED = "approved", "Approved"
        RETURNED = "returned", "Returned"

    procedure = models.ForeignKey(Procedure, on_delete=models.PROTECT, related_name="versions")
    version = models.CharField(max_length=10)
    effective_date = models.DateField()
    changes = models.TextField(help_text="What changed in this version (what staff must know).")
    file = models.FileField(upload_to=procedure_file_path, storage=get_private_storage, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    prepared_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    return_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-effective_date", "-id"]
        constraints = [models.UniqueConstraint(fields=["procedure", "version"], name="one_row_per_version")]

    def __str__(self):
        return f"{self.procedure.code} v{self.version}"


class ReadConfirmation(models.Model):
    version = models.ForeignKey(ProcedureVersion, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="procedure_reads")
    confirmed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["version", "user"], name="one_read_per_version")]

    def __str__(self):
        return f"{self.user} read {self.version}"


# ---------------------------------------------------------------------------
# Quarterly Business Report (EA-OPS-RPT-01)
# ---------------------------------------------------------------------------
class QuarterlyReport(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Waiting for the CEO"
        RETURNED = "returned", "Returned for changes"
        APPROVED = "approved", "Approved"

    DUE_DAYS = 15

    quarter_start = models.DateField(unique=True)
    reference = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    summary = models.TextField(blank=True, help_text="Section 1: the quarter in a few lines.")
    strategy = models.TextField(blank=True, help_text="Section 2: planned classes, events, camps, system changes.")
    comments = models.JSONField(default=dict, blank=True, help_text="The OM's comment per section.")
    difference_note = models.TextField(blank=True, help_text="Why headline sales and trading income differ.")
    data = models.JSONField(default=dict, blank=True, help_text="The figures, frozen when submitted.")
    prepared_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)
    return_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-quarter_start"]

    def __str__(self):
        return self.reference

    @property
    def quarter_end(self):
        import calendar

        m = self.quarter_start.month + 2
        return datetime.date(self.quarter_start.year, m, calendar.monthrange(self.quarter_start.year, m)[1])

    @property
    def due_date(self):
        return self.quarter_end + datetime.timedelta(days=self.DUE_DAYS)

    @property
    def label(self):
        return f"Q{(self.quarter_start.month - 1) // 3 + 1} {self.quarter_start.year}"
