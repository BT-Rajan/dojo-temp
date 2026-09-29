"""
Adding staff and managing their sign-in (decision P7-11). A new staff member gets a login with a one-time password
that is shown once to the person adding them and must be changed at first sign-in. The password is never stored in
the audit or message logs (ISO 27001 A.5.17).
"""

import secrets

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.audit.services import record_event
from apps.core.validators import normalize_kuwait_mobile, validate_kuwait_mobile
from apps.rbac.services import effective_access, has_perm

from .models import StaffProfile


def temporary_password() -> str:
    """Easy to read out (no 0/O or 1/l), long enough for the password rules."""
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(3)]
    return "Elite-" + "-".join(groups)


@transaction.atomic
def create_staff(
    creator,
    *,
    email,
    full_name,
    full_name_ar="",
    mobile="",
    job_title,
    job_title_ar="",
    employment_type,
    primary_branch=None,
    reports_to=None,
    second_lead=None,
    start_date=None,
):
    """Returns (profile, one-time password)."""
    if not has_perm(creator, "staff.manage"):
        raise PermissionDenied("Only the CEO and the Operations Manager add staff.")
    User = get_user_model()
    email = (email or "").strip().lower()
    full_name, job_title = (full_name or "").strip(), (job_title or "").strip()
    if not full_name or not job_title:
        raise ValidationError("Give the name and job title.")
    try:
        validate_email(email)
    except ValidationError as exc:
        raise ValidationError("Enter a valid work email; it is the sign-in.") from exc
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError("Someone already signs in with this email.")
    mobile = (mobile or "").strip()
    if mobile:
        mobile = normalize_kuwait_mobile(mobile)
        validate_kuwait_mobile(mobile)
        if User.objects.filter(mobile=mobile).exists():
            raise ValidationError("Another account already uses this mobile number.")
    if employment_type not in StaffProfile.EmploymentType.values:
        raise ValidationError("Choose the employment type.")
    password = temporary_password()
    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        full_name_ar=(full_name_ar or "").strip(),
        mobile=mobile or None,
        must_change_password=True,
    )
    profile = StaffProfile.objects.create(
        user=user,
        job_title=job_title,
        job_title_ar=(job_title_ar or "").strip(),
        employment_type=employment_type,
        primary_branch=primary_branch,
        start_date=start_date,
        created_by=creator,
        updated_by=creator,
    )
    if reports_to is not None or second_lead is not None:
        from apps.management.services import set_reporting_line

        set_reporting_line(creator, profile, reports_to, second_lead)
    record_event(action="staff_added", instance=profile, changes={"email": email, "job_title": job_title})
    return profile, password


def _outranks(actor, user) -> bool:
    """The actor holds every power the other person has (or manages roles)."""
    if has_perm(actor, "rbac.manage_roles"):
        return True
    return effective_access(user).permissions <= effective_access(actor).permissions


@transaction.atomic
def reset_password(actor, user) -> str:
    """A new one-time password; the person is signed out everywhere and must change it at next sign-in."""
    if not (has_perm(actor, "staff.manage") or has_perm(actor, "rbac.assign")):
        raise PermissionDenied("Only the CEO, the Operations Manager or Systems & IT reset passwords.")
    if user.pk == actor.pk:
        raise PermissionDenied("Change your own password from the password page.")
    if not user.is_active:
        raise ValidationError("This account is closed.")
    if not _outranks(actor, user):
        raise PermissionDenied("You can't reset the password of someone with more access than you.")
    password = temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save()
    user.revoke_all_sessions()
    record_event(action="password_reset_by_admin", object_type="User", object_id=str(user.pk))
    return password
