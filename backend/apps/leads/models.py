"""
M3 — leads, trials and group sales, and M13 — marketing (decisions P5-1 to P5-10).

- Lead            one enquiry, whatever the channel, with one owner, a stage, and the next action and due date.
- Activity        what happened with a lead or group deal (call, WhatsApp, note, stage change, booking…).
- GroupDeal       schools and companies, with the Operations receiving owner's confirmation before delivery.
- Campaign        spend and a code; leads and conversions are counted from the leads that carry it.
- ReferralCode    one per member; a lead arriving with it records the referrer.
- ReviewRequest   Google review requests sent (at most once per family every 90 days).
- MessagingOptIn  a family's yes/no to WhatsApp broadcasts (the latest record counts).
- Broadcast       a WhatsApp broadcast: drafted by Marketing, approved and sent by the Marketing Lead.
"""

import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class Campaign(BaseModel):
    class Channel(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        TIKTOK = "tiktok", "TikTok"
        GOOGLE = "google", "Google"
        WHATSAPP = "whatsapp", "WhatsApp"
        FLYER = "flyer", "Flyers / print"
        EVENT = "event", "Event"
        REFERRAL = "referral", "Referral"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=30, unique=True, help_text="Used in links: ?c=CODE")
    channel = models.CharField(max_length=10, choices=Channel.choices)
    branch = models.ForeignKey(
        "organization.Branch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Blank = both",
    )
    start = models.DateField()
    end = models.DateField(null=True, blank=True)
    spend = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start"]

    def __str__(self):
        return self.name


class Lead(BaseModel):
    class Source(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        PHONE = "phone", "Phone"
        WEBSITE = "website", "Website trial form"
        SAQR = "saqr", "SAQR chat"
        WHATSAPP = "whatsapp", "WhatsApp"
        REFERRAL = "referral", "Referral"
        GROUP = "group", "Group sales"
        EVENT = "event", "Event"
        OTHER = "other", "Other"

    class Stage(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        TRIAL_BOOKED = "trial_booked", "Trial booked"
        TRIAL_DONE = "trial_done", "Trial done"
        JOINED = "joined", "Joined"
        LOST = "lost", "Lost"

    OPEN = (Stage.NEW, Stage.CONTACTED, Stage.TRIAL_BOOKED, Stage.TRIAL_DONE)

    class LostReason(models.TextChoices):
        PRICE = "price", "Price"
        TIMING = "timing", "Class times don't suit"
        LOCATION = "location", "Location"
        NO_ANSWER = "no_answer", "No answer after several tries"
        NOT_INTERESTED = "not_interested", "Not interested any more"
        CHOSE_OTHER = "chose_other", "Chose another academy"
        AGE = "age", "Age / no suitable class"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=16, db_index=True)
    email = models.EmailField(blank=True)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="leads")
    program = models.ForeignKey(
        "organization.Program", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    interest = models.CharField(max_length=200, blank=True, help_text="Who is it for, ages, what they want.")
    language = models.CharField(max_length=2, default="ar")
    source = models.CharField(max_length=10, choices=Source.choices)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="leads")
    referrer = models.ForeignKey(
        "members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="referred_leads"
    )
    stage = models.CharField(max_length=12, choices=Stage.choices, default=Stage.NEW)
    lost_reason = models.CharField(max_length=15, choices=LostReason.choices, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="owned_leads"
    )
    next_action = models.CharField(max_length=150, blank=True)
    next_due = models.DateTimeField(null=True, blank=True)
    trial_request = models.ForeignKey(
        "website.TrialRequest", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads"
    )
    trial_booking = models.ForeignKey(
        "classes.Booking", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads"
    )
    trial_score = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    trial_feedback = models.CharField(max_length=500, blank=True)
    member = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    joined_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    chat = models.ForeignKey(
        "assistant.Conversation", null=True, blank=True, on_delete=models.SET_NULL, related_name="leads"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["branch", "stage"]), models.Index(fields=["owner", "next_due"])]

    def __str__(self):
        return f"{self.name} ({self.get_stage_display()})"

    @property
    def is_open(self):
        return self.stage in self.OPEN

    @property
    def overdue(self):
        return self.is_open and self.next_due is not None and self.next_due < timezone.now()


class GroupDeal(BaseModel):
    class Kind(models.TextChoices):
        SCHOOL = "school", "School"
        COMPANY = "company", "Company"
        OTHER = "other", "Other group"

    class Stage(models.TextChoices):
        CONTACT = "contact", "Contact"
        MEETING = "meeting", "Meeting"
        PROPOSAL = "proposal", "Proposal"
        AGREEMENT = "agreement", "Agreement"
        PAID = "paid", "Paid registrations"
        DELIVERY = "delivery", "Delivery handed to Training"
        LOST = "lost", "Lost"

    ORDER = ["contact", "meeting", "proposal", "agreement", "paid", "delivery"]

    organisation = models.CharField(max_length=150)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    contact_name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=16)
    email = models.EmailField(blank=True)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="group_deals")
    stage = models.CharField(max_length=10, choices=Stage.choices, default=Stage.CONTACT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="group_deals")
    participants = models.PositiveIntegerField(default=0)
    value = models.DecimalField(max_digits=10, decimal_places=3, default=0, help_text="Agreed value in KD.")
    start_date = models.DateField(null=True, blank=True)
    details = models.TextField(blank=True, help_text="What was agreed: program, schedule, location.")
    next_action = models.CharField(max_length=150, blank=True)
    next_due = models.DateField(null=True, blank=True)
    receiving_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    lost_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.organisation


class Activity(models.Model):
    class Kind(models.TextChoices):
        CALL = "call", "Call"
        WHATSAPP = "whatsapp", "WhatsApp"
        VISIT = "visit", "Visit / meeting"
        NOTE = "note", "Note"
        STAGE = "stage", "Stage changed"
        OWNER = "owner", "Owner changed"
        BOOKING = "booking", "Trial booked"
        FEEDBACK = "feedback", "Trial feedback"
        SYSTEM = "system", "System"

    CONTACT = (Kind.CALL, Kind.WHATSAPP, Kind.VISIT)

    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.CASCADE, related_name="activities")
    deal = models.ForeignKey(GroupDeal, null=True, blank=True, on_delete=models.CASCADE, related_name="activities")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    text = models.TextField(blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-at", "-id"]

    def __str__(self):
        return f"{self.get_kind_display()} · {self.at:%d/%m %H:%M}"


def _referral_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(7))


class ReferralCode(models.Model):
    member = models.OneToOneField("members.Member", on_delete=models.CASCADE, related_name="referral_code")
    code = models.CharField(max_length=10, unique=True, default=_referral_code)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class ReviewRequest(models.Model):
    class Reason(models.TextChoices):
        TRIAL = "trial", "Strong trial"
        PROMOTION = "promotion", "Belt promotion"

    mobile = models.CharField(max_length=16, db_index=True)
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="+")
    reason = models.CharField(max_length=9, choices=Reason.choices)
    member = models.ForeignKey("members.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    lead = models.ForeignKey(Lead, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.get_reason_display()} · {self.sent_at:%d/%m/%Y}"


class MessagingOptIn(models.Model):
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="messaging_opt_ins")
    opted_in = models.BooleanField()
    source = models.CharField(max_length=20, default="desk")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-recorded_at", "-id"]

    def __str__(self):
        return f"{self.member_id}: {'yes' if self.opted_in else 'no'}"


class Broadcast(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        REJECTED = "rejected", "Returned"

    class Ages(models.TextChoices):
        ALL = "all", "Everyone"
        KIDS = "kids", "Children (under 18)"
        ADULTS = "adults", "Adults"

    title = models.CharField(max_length=120)
    message_en = models.TextField(max_length=1000)
    message_ar = models.TextField(max_length=1000)
    branch = models.ForeignKey("organization.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    program = models.ForeignKey(
        "organization.Program", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    ages = models.CharField(max_length=6, choices=Ages.choices, default=Ages.ALL)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decision_note = models.CharField(max_length=255, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    recipients = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
