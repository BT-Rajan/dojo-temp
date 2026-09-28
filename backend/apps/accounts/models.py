import secrets

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.validators import validate_kuwait_mobile


def new_security_stamp() -> str:
    return secrets.token_hex(16)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        # Break-glass account for the Django admin only. Business access still comes from RBAC roles.
        extra.update(is_staff=True, is_superuser=True)
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    """
    One login for everyone: staff, coaches, parents and adult members.
    What a user may see and do comes only from their RBAC role assignments (apps.rbac).
    """

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        ARABIC = "ar", "العربية"

    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=16, unique=True, null=True, blank=True, validators=[validate_kuwait_mobile])
    full_name = models.CharField(max_length=150)
    full_name_ar = models.CharField(max_length=150, blank=True)
    preferred_language = models.CharField(max_length=2, choices=Language.choices, default=Language.ENGLISH)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False, help_text="Can open the technical admin site (Systems & IT only).")
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    # Changing the stamp signs the user out of every device (see get_session_auth_hash).
    security_stamp = models.CharField(max_length=32, default=new_security_stamp, editable=False)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name or self.email

    def get_session_auth_hash(self):
        # Sessions are bound to both the password and the security stamp.
        return super().get_session_auth_hash() + self.security_stamp

    def revoke_all_sessions(self):
        self.security_stamp = new_security_stamp()
        self.save(update_fields=["security_stamp"])

    def set_password(self, raw_password):
        super().set_password(raw_password)
        self.password_changed_at = timezone.now()

    def deactivate(self):
        """Leaver process (ISO 27001 A.5.18 / OPS-PROC §7.4): no login, all sessions ended, roles ended."""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.security_stamp = new_security_stamp()
        self.save(update_fields=["is_active", "deactivated_at", "security_stamp"])
        today = timezone.localdate()
        self.role_assignments.filter(Q(ends_on__isnull=True) | Q(ends_on__gt=today)).update(ends_on=today)
