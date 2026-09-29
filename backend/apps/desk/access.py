"""
Access to the staff desk (/en/desk/, /ar/desk/).

Every desk view is wrapped by @desk(...), which enforces, in order:
1. signed in (otherwise the desk sign-in page);
2. a password change when one is due;
3. two-factor sign-in for privileged roles when MFA is enforced (ISO 27001 A.8.5);
4. the view's permission, checked for the branch the user is working at (deny by default).

The "current branch" is kept in the session and can only be a branch the user holds a role for.
"""

from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import get_language

from apps.organization.models import Branch
from apps.rbac.services import effective_access, has_perm, is_mfa_verified, is_privileged

SESSION_BRANCH = "desk_branch"


def lang(request=None) -> str:
    return "ar" if get_language() == "ar" else "en"


def L(en, ar):
    return ar if lang() == "ar" else en


def allowed_branches(user):
    grants = effective_access(user).grants
    if not grants:
        return Branch.objects.none()
    if any(scope is None for scope in grants.values()):
        return Branch.objects.filter(is_active=True)
    ids = set().union(*grants.values())
    return Branch.objects.filter(is_active=True, pk__in=ids)


def current_branch(request):
    branches = list(allowed_branches(request.user).order_by("code").reverse())  # PRM before BED
    if not branches:
        return None
    wanted = request.session.get(SESSION_BRANCH)
    for b in branches:
        if b.pk == wanted:
            return b
    staff = getattr(request.user, "staff_profile", None)
    for b in branches:
        if staff is not None and staff.primary_branch_id == b.pk:
            return b
    return branches[0]


def can(request, perm) -> bool:
    branch = getattr(request, "branch", None)
    return has_perm(request.user, perm, branch.pk if branch else None)


def desk(perm=None, any_of=None):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect(f"{reverse('desk:login')}?next={request.get_full_path()}")
            if user.must_change_password and view.__name__ != "change_password":
                return redirect("desk:change_password")
            if (
                settings.ENFORCE_PRIVILEGED_MFA
                and is_privileged(user)
                and not is_mfa_verified(user)
                and view.__name__ not in ("mfa_setup", "change_password")
            ):
                messages.info(request, L("Set up two-factor sign-in to continue.", "فعّل التحقق بخطوتين للمتابعة."))
                return redirect("desk:mfa_setup")
            request.branch = current_branch(request)
            codes = ([perm] if perm else []) + list(any_of or [])
            if codes and not any(can(request, c) for c in codes):
                _record_denied(request, codes)
                raise PermissionDenied
            try:
                return view(request, *args, **kwargs)
            except ValidationError as exc:
                for message in exc.messages:
                    messages.error(request, message)
                return redirect(request.get_full_path())
            except PermissionDenied as exc:
                if request.method != "POST" or not str(exc):
                    raise
                messages.error(request, str(exc))  # a rule said no (e.g. approving your own request)
                return redirect(request.get_full_path())

        wrapper.desk_perm = perm
        return wrapper

    return decorator


def _record_denied(request, codes):
    request._security_events = getattr(request, "_security_events", []) + [
        {"action": "access_denied", "object_type": "desk", "object_id": request.path[:64], "changes": {"needs": codes}}
    ]


def safe_next(request, fallback):
    """A 'next' URL only if it stays on this site (no open redirects)."""
    from django.utils.http import url_has_allowed_host_and_scheme

    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return nxt
    return reverse(fallback)
