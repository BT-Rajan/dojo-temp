import secrets

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from django.utils.functional import LazyObject

from apps.core.crypto import EncryptedTextField, blind_index
from apps.core.models import BaseModel
from apps.core.validators import normalize_kuwait_mobile, validate_civil_id


class PrivateStorage(LazyObject):
    """Member photos and signatures are never served as public media; staff see them through a checked view."""

    def _setup(self):
        self._wrapped = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT, base_url=None)


private_storage = PrivateStorage()


def get_private_storage():
    """Used as a callable so migrations record this function, not a machine-specific path."""
    return private_storage


def new_qr_token() -> str:
    return secrets.token_urlsafe(12)


def member_photo_path(instance, filename):
    return f"members/{instance.pk or 'new'}/photo-{secrets.token_hex(6)}.jpg"


class Guardian(BaseModel):
    """A parent or guardian. One guardian can be linked to several children (family account)."""

    full_name = models.CharField(max_length=150)
    full_name_ar = models.CharField(max_length=150, blank=True)
    mobile = models.CharField(max_length=16)
    email = models.EmailField(blank=True)
    civil_id = EncryptedTextField(blank=True)
    civil_id_index = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="guardian_profile",
        help_text="Portal login, once created.",
    )

    AUDIT_REDACT = ("civil_id", "civil_id_index")

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name

    def clean(self):
        self.mobile = normalize_kuwait_mobile(self.mobile)
        if self.civil_id:
            validate_civil_id(self.civil_id)

    def save(self, *args, **kwargs):
        self.civil_id_index = blind_index(self.civil_id) if self.civil_id else None
        super().save(*args, **kwargs)


class Member(BaseModel):
    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"

    class Source(models.TextChoices):
        WALK_IN = "walk_in", "Walk-in"
        WHATSAPP = "whatsapp", "WhatsApp / SAQR"
        INSTAGRAM = "instagram", "Instagram"
        GOOGLE = "google", "Google"
        REFERRAL = "referral", "Friend or family"
        WEBSITE = "website", "Website"
        GROUP = "group", "School / group"
        OTHER = "other", "Other"
        MINDBODY = "mindbody", "Imported from Mindbody"

    branch = models.ForeignKey(
        "organization.Branch", on_delete=models.PROTECT, related_name="members", help_text="Home branch."
    )
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    first_name_ar = models.CharField(max_length=80, blank=True)
    last_name_ar = models.CharField(max_length=80, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=6, choices=Gender.choices)
    nationality = models.CharField(max_length=60, blank=True)
    civil_id = EncryptedTextField(blank=True)
    civil_id_index = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    mobile = models.CharField(max_length=16, blank=True)
    email = models.EmailField(blank=True)
    area = models.CharField(max_length=80, blank=True, help_text="Residential area, e.g. Salmiya")
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.WALK_IN)
    medical_notes = EncryptedTextField(blank=True)
    allergies = EncryptedTextField(blank=True)
    joined_on = models.DateField(default=timezone.localdate)
    is_active = models.BooleanField(default=True)
    photo = models.ImageField(
        upload_to=member_photo_path,
        storage=get_private_storage,
        blank=True,
        help_text="Shown to the member's instructors on the class list.",
    )
    qr_token = models.CharField(
        max_length=32,
        unique=True,
        default=new_qr_token,
        editable=False,
        help_text="Printed on the member card; scanned at the front desk.",
    )
    guardians = models.ManyToManyField(Guardian, through="GuardianLink", related_name="members", blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="member_profile",
        help_text="Portal login for adult members.",
    )

    AUDIT_REDACT = ("civil_id", "civil_id_index", "medical_notes", "allergies")

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["branch", "is_active"]), models.Index(fields=["last_name", "first_name"])]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        today = timezone.localdate()
        dob = self.date_of_birth
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    @property
    def is_minor(self) -> bool:
        return self.age < 18

    def clean(self):
        if self.mobile:
            self.mobile = normalize_kuwait_mobile(self.mobile)
        if self.civil_id:
            validate_civil_id(self.civil_id)

    def save(self, *args, **kwargs):
        self.civil_id_index = blind_index(self.civil_id) if self.civil_id else None
        super().save(*args, **kwargs)


class GuardianLink(models.Model):
    class Relationship(models.TextChoices):
        FATHER = "father", "Father"
        MOTHER = "mother", "Mother"
        GUARDIAN = "guardian", "Legal guardian"
        OTHER = "other", "Other family"

    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name="links")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="guardian_links")
    relationship = models.CharField(max_length=10, choices=Relationship.choices)
    is_primary = models.BooleanField(default=False, help_text="Pays and receives messages.")

    class Meta:
        unique_together = [("guardian", "member")]

    def __str__(self):
        return f"{self.guardian} → {self.member} ({self.relationship})"


class EmergencyContact(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="emergency_contacts")
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=60)
    mobile = models.CharField(max_length=16)

    def __str__(self):
        return f"{self.name} ({self.relationship})"

    def clean(self):
        self.mobile = normalize_kuwait_mobile(self.mobile)


class MediaConsent(models.Model):
    """
    EA-MKT-FRM-01. Each change creates a new row, so the history of what was agreed and when is kept.
    The newest row is the member's current consent.
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="media_consents")
    internal_records = models.BooleanField(default=False)
    social_media = models.BooleanField(default=False)
    website_marketing = models.BooleanField(default=False)
    signed_by_name = models.CharField(max_length=150, help_text="Parent/guardian, or the adult member.")
    signed_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-signed_at", "-id"]

    def __str__(self):
        return f"Consent for {self.member} ({self.signed_at:%Y-%m-%d})"

    @property
    def is_withdrawn(self) -> bool:
        return not (self.internal_records or self.social_media or self.website_marketing)


class RulesAgreement(models.Model):
    """Agreement to the academy rules and safety instructions, signed on screen (scope M2)."""

    CURRENT_VERSION = "2026-1"

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="rules_agreements")
    rules_version = models.CharField(max_length=20, default=CURRENT_VERSION)
    signed_by_name = models.CharField(max_length=150, help_text="Parent/guardian, or the adult member.")
    signature = models.TextField(blank=True, help_text="The on-screen signature (image data).")
    signed_at = models.DateTimeField(default=timezone.now)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")

    AUDIT_REDACT = ("signature",)

    class Meta:
        ordering = ["-signed_at", "-id"]

    def __str__(self):
        return f"Rules {self.rules_version} · {self.member} ({self.signed_at:%Y-%m-%d})"
