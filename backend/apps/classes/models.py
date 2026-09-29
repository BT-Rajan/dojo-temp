"""
M4 — Classes, schedule, bookings and attendance (replaces the Mindbody schedule and
check-in and EA-OPS-FRM-04 Class Change Notice Log).

- ClassSlot     the weekly timetable: one row per class per weekday.
- ClassSession  one dated occurrence of a slot (or a one-off seminar, camp, event or private
                session). Sessions are generated four weeks ahead from the slots.
- Enrollment    a member's regular place in a slot. Regular members just turn up and are
                checked in; booking is needed for trials, full classes and events.
- Booking       a place in one session, with a waiting list when the session is full.
- Attendance    a check-in (front desk search, QR card, or the coach's class list).
- ClassChange   cancel / reschedule / substitute coach, approved by the Training Lead or
                Operations Manager; affected members are messaged and the send is logged.

Weekdays follow the Kuwait week used everywhere in the system: 0 = Saturday … 6 = Friday.
"""

import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel

WEEKDAYS = [
    (0, "Saturday"),
    (1, "Sunday"),
    (2, "Monday"),
    (3, "Tuesday"),
    (4, "Wednesday"),
    (5, "Thursday"),
    (6, "Friday"),
]
WEEKDAYS_AR = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]


def kuwait_weekday(day: datetime.date) -> int:
    """Python counts Monday = 0; the academy's week starts on Saturday = 0."""
    return (day.weekday() + 2) % 7


class AgeGroup(models.TextChoices):
    KIDS = "kids", "Kids"
    TEENS = "teens", "Teens"
    ADULTS = "adults", "Adults"
    LADIES = "ladies", "Ladies"


class Focus(models.TextChoices):
    NONE = "", "—"
    STRIKING = "striking", "Striking"
    GRAPPLING = "grappling", "Grappling"
    MIXED = "mixed", "Mixed"


class ClassSlot(BaseModel):
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="class_slots")
    program = models.ForeignKey("organization.Program", on_delete=models.PROTECT, related_name="class_slots")
    room = models.ForeignKey(
        "organization.Room", null=True, blank=True, on_delete=models.PROTECT, related_name="class_slots"
    )
    title_en = models.CharField(max_length=80, help_text="Shown on the schedule, e.g. Kajukenbo · Ladies")
    title_ar = models.CharField(max_length=80, blank=True)
    ages_en = models.CharField(max_length=60, help_text="e.g. Kids 5–8")
    ages_ar = models.CharField(max_length=60, blank=True)
    age_group = models.CharField(max_length=8, choices=AgeGroup.choices)
    focus = models.CharField(
        max_length=10,
        choices=Focus.choices,
        blank=True,
        default="",
        help_text="Striking / grappling rotation of the Complete Fighter Program.",
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start = models.TimeField()
    end = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=20)
    instructors = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="class_slots")
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    is_public = models.BooleanField(default=True, help_text="Show on the website and to SAQR.")
    is_sample = models.BooleanField(default=False, help_text="Marked 'sample' on the website until confirmed.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["weekday", "start"]
        indexes = [models.Index(fields=["branch", "weekday", "is_active"])]

    def __str__(self):
        return f"{self.get_weekday_display()} {self.start:%H:%M} · {self.title_en} ({self.branch.code})"

    def clean(self):
        if self.end and self.start and self.end <= self.start:
            raise ValidationError({"end": "The class must end after it starts."})
        if self.room_id and self.branch_id and self.room.branch_id != self.branch_id:
            raise ValidationError({"room": "The room belongs to another branch."})
        if self.program_id and self.branch_id and self.program.branch_id != self.branch_id:
            raise ValidationError({"program": "The program belongs to another branch."})
        open_days = (self.branch.open_days or []) if self.branch_id else []
        if open_days and self.weekday not in open_days:
            raise ValidationError({"weekday": "The branch is closed on this day."})

    @property
    def key(self):
        return "promenade" if self.branch.code == "PRM" else "bedaya"

    @property
    def weekday_ar(self):
        return WEEKDAYS_AR[self.weekday]

    # Used by the website schedule filters
    @property
    def discipline_en(self):
        return self.title_en.split("·")[0].strip()

    @property
    def discipline_ar(self):
        return (self.title_ar or self.title_en).split("·")[0].strip()

    @property
    def discipline_key(self):
        return self.discipline_en.lower().replace(" ", "-").replace("'", "")

    def runs_on(self, day: datetime.date) -> bool:
        return (
            self.is_active
            and kuwait_weekday(day) == self.weekday
            and self.valid_from <= day
            and (self.valid_until is None or day <= self.valid_until)
        )


class ClassSession(BaseModel):
    class Kind(models.TextChoices):
        CLASS = "class", "Class"
        SEMINAR = "seminar", "Seminar"
        CAMP = "camp", "Camp"
        EVENT = "event", "Event"
        PRIVATE = "private", "Private session"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        CANCELLED = "cancelled", "Cancelled"

    slot = models.ForeignKey(ClassSlot, null=True, blank=True, on_delete=models.PROTECT, related_name="sessions")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.CLASS)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="class_sessions")
    program = models.ForeignKey(
        "organization.Program", null=True, blank=True, on_delete=models.PROTECT, related_name="class_sessions"
    )
    room = models.ForeignKey("organization.Room", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    title_en = models.CharField(max_length=120)
    title_ar = models.CharField(max_length=120, blank=True)
    date = models.DateField()
    start = models.TimeField()
    end = models.TimeField()
    capacity = models.PositiveSmallIntegerField(default=20)
    instructors = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="class_sessions")
    pricing_option = models.ForeignKey(
        "organization.PricingOption",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="sessions",
        help_text="For paid seminars, camps, events and private sessions.",
    )
    seminar_points = models.PositiveSmallIntegerField(default=0, help_text="Kajukenbo seminar points earned.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["date", "start"]
        constraints = [
            # One-off sessions have no slot; MySQL treats NULLs as distinct, so they never clash.
            models.UniqueConstraint(fields=["slot", "date"], name="one_session_per_slot_per_day"),
        ]
        indexes = [models.Index(fields=["branch", "date"]), models.Index(fields=["date", "status"])]

    def __str__(self):
        return f"{self.date:%Y-%m-%d} {self.start:%H:%M} · {self.title_en} ({self.branch.code})"

    @property
    def starts_at(self):
        return timezone.make_aware(datetime.datetime.combine(self.date, self.start))

    @property
    def ends_at(self):
        return timezone.make_aware(datetime.datetime.combine(self.date, self.end))

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    @property
    def is_over(self):
        return timezone.now() >= self.ends_at

    @property
    def age_group(self):
        return self.slot.age_group if self.slot_id else ""


class Enrollment(BaseModel):
    """A member's regular weekly class. Regulars are expected every week without booking."""

    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="enrollments")
    slot = models.ForeignKey(ClassSlot, on_delete=models.CASCADE, related_name="enrollments")
    start_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["slot__weekday", "slot__start"]
        # "One open enrollment per member per slot" is enforced in services.enroll under a lock
        # (MySQL has no partial unique indexes).

    def __str__(self):
        return f"{self.member} · {self.slot}"

    @property
    def branch_id(self):
        return self.slot.branch_id

    def active_on(self, day):
        return self.start_date <= day and (self.end_date is None or day <= self.end_date)


class Booking(BaseModel):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        WAITLISTED = "waitlisted", "Waiting list"
        CANCELLED = "cancelled", "Cancelled"
        ATTENDED = "attended", "Attended"
        NO_SHOW = "no_show", "No-show"

    class Source(models.TextChoices):
        DESK = "desk", "Front desk"
        PORTAL = "portal", "Member portal"
        TRIAL = "trial", "Trial request"
        COACH = "coach", "Coach"

    ACTIVE = (Status.BOOKED, Status.WAITLISTED, Status.ATTENDED)

    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name="bookings")
    member = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.CASCADE, related_name="bookings"
    )
    # Trials are booked with a name and phone only (scope M3): no member record before the trial.
    trial_request = models.ForeignKey(
        "website.TrialRequest", null=True, blank=True, on_delete=models.SET_NULL, related_name="bookings"
    )
    guest_name = models.CharField(max_length=120, blank=True)
    guest_mobile = models.CharField(max_length=16, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.BOOKED)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.DESK)
    is_trial = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    late_cancellation = models.BooleanField(default=False, help_text="Recorded only; no penalty.")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]
        # "One live booking per member per class" is enforced in services.book while the class row is
        # locked (MySQL has no partial unique indexes).

    def __str__(self):
        return f"{self.display_name} · {self.session} ({self.status})"

    @property
    def display_name(self):
        return str(self.member) if self.member_id else self.guest_name

    @property
    def branch_id(self):
        return self.session.branch_id


class Attendance(BaseModel):
    class Method(models.TextChoices):
        DESK = "desk", "Front desk search"
        QR = "qr", "Member card (QR)"
        COACH = "coach", "Coach's class list"
        IMPORT = "import", "Imported from Mindbody"

    class Warning(models.TextChoices):
        NONE = "", "—"
        NO_MEMBERSHIP = "no_membership", "No membership"
        EXPIRED = "expired", "Membership expired"
        FROZEN = "frozen", "Membership frozen"
        NO_SESSIONS = "no_sessions", "No sessions left"
        OTHER_PROGRAM = "other_program", "Membership does not cover this class"

    session = models.ForeignKey(ClassSession, on_delete=models.PROTECT, related_name="attendance")
    member = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.PROTECT, related_name="visits")
    booking = models.OneToOneField(Booking, null=True, blank=True, on_delete=models.SET_NULL, related_name="attendance")
    membership = models.ForeignKey(
        "sales.Membership", null=True, blank=True, on_delete=models.SET_NULL, related_name="visits"
    )
    checked_in_at = models.DateTimeField(default=timezone.now)
    method = models.CharField(max_length=6, choices=Method.choices)
    walk_in = models.BooleanField(default=False, help_text="Came without a booking or regular place.")
    warning = models.CharField(max_length=16, choices=Warning.choices, blank=True, default="")

    class Meta:
        ordering = ["-checked_in_at"]
        constraints = [
            # Trial guests have no member; NULLs are distinct in MySQL, so only members are limited.
            models.UniqueConstraint(fields=["session", "member"], name="one_check_in_per_member_per_session"),
        ]
        indexes = [models.Index(fields=["member", "checked_in_at"])]

    def __str__(self):
        who = self.member or (self.booking.guest_name if self.booking_id else "guest")
        return f"{who} · {self.session}"

    @property
    def branch_id(self):
        return self.session.branch_id


class ClassChange(BaseModel):
    """EA-OPS-FRM-04: every change is requested, approved, and every affected member is told."""

    class Kind(models.TextChoices):
        CANCEL = "cancel", "Cancel the class"
        RESCHEDULE = "reschedule", "Move to another time"
        SUBSTITUTE = "substitute", "Another coach teaches"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved and members told"
        REJECTED = "rejected", "Rejected"

    session = models.ForeignKey(ClassSession, on_delete=models.PROTECT, related_name="changes")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    new_date = models.DateField(null=True, blank=True)
    new_start = models.TimeField(null=True, blank=True)
    new_end = models.TimeField(null=True, blank=True)
    new_instructors = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="+")
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    urgent = models.BooleanField(default=False, help_text="Requested less than 2 hours before the class.")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)
    notified_at = models.DateTimeField(null=True, blank=True)
    notified_channel = models.CharField(max_length=20, blank=True)
    notified_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.session}"

    @property
    def branch_id(self):
        return self.session.branch_id
