"""
RBAC decisions. All access checks in the system go through these functions.

Rules:
- Deny by default: a user can do only what a current role assignment grants.
- Branch scope: an assignment with no branch applies to all branches; otherwise only
  to that branch. Data belonging to other branches is filtered out of every list.
- Django's `is_superuser` flag grants NO business access; it only opens the technical
  admin site. Business access always comes from roles (ISO 27001 A.5.15, A.8.2, A.8.3).
"""

from dataclasses import dataclass, field

from .models import RoleAssignment

ALL_BRANCHES = None  # sentinel meaning "no branch restriction"


@dataclass
class Access:
    # permission code -> set of branch ids, or None when granted for all branches
    grants: dict[str, set[int] | None] = field(default_factory=dict)
    role_summaries: list[dict] = field(default_factory=list)
    privileged: bool = False

    @property
    def permissions(self) -> set[str]:
        return set(self.grants)


def effective_access(user) -> Access:
    """Computes a user's current permissions once per request and caches it on the user object."""
    if user is None or not user.is_authenticated or not user.is_active:
        return Access()
    cached = getattr(user, "_rbac_access", None)
    if cached is not None:
        return cached

    access = Access()
    assignments = (
        RoleAssignment.objects.current()
        .filter(user=user)
        .select_related("role", "branch")
        .prefetch_related("role__permissions")
    )
    for a in assignments:
        access.privileged = access.privileged or a.role.is_privileged
        access.role_summaries.append(
            {
                "role": a.role.code,
                "name": a.role.name,
                "name_ar": a.role.name_ar,
                "branch": a.branch.code if a.branch_id else None,
            }
        )
        for perm in a.role.permissions.all():
            current = access.grants.get(perm.code, set())
            if a.branch_id is None or current is ALL_BRANCHES:
                access.grants[perm.code] = ALL_BRANCHES
            else:
                current.add(a.branch_id)
                access.grants[perm.code] = current
    user._rbac_access = access
    return access


def has_perm(user, code: str, branch_id: int | None = None) -> bool:
    """True when the user holds `code` — for the given branch if one is given."""
    grants = effective_access(user).grants
    if code not in grants:
        return False
    scope = grants[code]
    if scope is ALL_BRANCHES or branch_id is None:
        return True
    return branch_id in scope


def branch_scope(user, code: str) -> set[int] | None:
    """Branch ids the user may act on for `code`; None means all branches; empty set means none."""
    grants = effective_access(user).grants
    if code not in grants:
        return set()
    return grants[code]


def scope_queryset(queryset, user, code: str, branch_field: str = "branch"):
    scope = branch_scope(user, code)
    if scope is ALL_BRANCHES:
        return queryset
    if not scope:
        return queryset.none()
    return queryset.filter(**{f"{branch_field}__in": scope})


def is_privileged(user) -> bool:
    return effective_access(user).privileged


def is_mfa_verified(user) -> bool:
    """True when this session completed two-factor login (django-otp)."""
    check = getattr(user, "is_verified", None)
    if callable(check):
        return bool(check())
    return getattr(user, "otp_device", None) is not None


def users_with_perm(code: str, branch_id: int | None = None):
    """Active users who currently hold `code` (for `branch_id` when given) — used to route alerts."""
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    assignments = RoleAssignment.objects.current().filter(role__permissions__code=code)
    if branch_id is not None:
        assignments = assignments.filter(Q(branch__isnull=True) | Q(branch_id=branch_id))
    return get_user_model().objects.filter(pk__in=assignments.values("user_id"), is_active=True).distinct()


def notify_perm(code: str, text: str, branch_id: int | None = None, exclude=None) -> int:
    """Sends `text` by WhatsApp to everyone holding `code`. Returns how many were messaged."""
    from apps.core.messaging import send_message

    sent = 0
    for user in users_with_perm(code, branch_id):
        if exclude is not None and user.pk == getattr(exclude, "pk", exclude):
            continue
        if user.mobile:
            send_message(user.mobile, text, category="staff")
            sent += 1
    return sent


# ---------------------------------------------------------------------------
# Granting and ending roles (used by the desk and the API)
# ---------------------------------------------------------------------------
def check_can_grant(granter, role, branch) -> None:
    """No privilege escalation: you hand out only powers you hold, and only for branches you manage."""
    from django.core.exceptions import PermissionDenied

    mine = effective_access(granter).permissions
    missing = set(role.permissions.values_list("code", flat=True)) - mine
    if missing and not has_perm(granter, "rbac.manage_roles"):
        raise PermissionDenied("You cannot grant a role with permissions you don't have yourself.")
    branch_id = branch.pk if branch is not None else None
    if not has_perm(granter, "rbac.assign", branch_id) or (
        branch is None and branch_scope(granter, "rbac.assign") is not None
    ):
        raise PermissionDenied("You cannot grant access for this branch.")


def grant_role(granter, user, role, branch=None, reason="", starts_on=None):
    import datetime

    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import transaction
    from django.utils import timezone

    from apps.audit.services import record_event

    if user.pk == granter.pk:
        raise PermissionDenied("You cannot change your own access. Ask another administrator.")
    if not (reason or "").strip():
        raise ValidationError("Give a reason for granting this access.")
    if role.code == "guardian":
        raise ValidationError("The parent / member role is given through the family record, not here.")
    today = timezone.localdate()
    starts_on = starts_on or today
    if starts_on < today - datetime.timedelta(days=1):
        raise ValidationError("Access can't start in the past.")
    check_can_grant(granter, role, branch)
    with transaction.atomic():
        if RoleAssignment.objects.current().filter(user=user, role=role, branch=branch).exists():
            raise ValidationError("They already have this role for this branch.")
        assignment = RoleAssignment.objects.create(
            user=user, role=role, branch=branch, starts_on=starts_on, granted_by=granter, reason=reason.strip()[:255]
        )
        record_event(
            action="role_granted",
            instance=assignment,
            changes={"user": user.pk, "role": role.code, "branch": branch.code if branch else "all",
                     "reason": assignment.reason},
        )  # fmt: skip
    return assignment


def end_role(ender, assignment):
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.utils import timezone

    from apps.audit.services import record_event

    if assignment.user_id == ender.pk:
        raise PermissionDenied("You cannot change your own access.")
    if not has_perm(ender, "rbac.assign", assignment.branch_id):
        raise PermissionDenied("You cannot change access for this branch.")
    today = timezone.localdate()
    if assignment.ends_on is not None and assignment.ends_on <= today:
        raise ValidationError("This access has already ended.")
    assignment.ends_on = max(today, assignment.starts_on)
    assignment.save(update_fields=["ends_on"])
    assignment.user.revoke_all_sessions()  # the change takes effect immediately
    record_event(
        action="role_ended", instance=assignment, changes={"user": assignment.user_id, "role": assignment.role.code}
    )
    return assignment
