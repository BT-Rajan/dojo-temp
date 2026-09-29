"""Finding members from the desk: by name (English or Arabic), mobile, or the QR card token."""

from django.db.models import Q

from apps.members.models import Member
from apps.rbac.services import scope_queryset


def visible_members(user):
    return scope_queryset(Member.objects.all(), user, "members.view")


def search_members(user, q: str, limit=20):
    q = (q or "").strip()
    qs = visible_members(user).select_related("branch")
    if not q:
        return qs.none()
    exact = qs.filter(qr_token=q)
    if exact.exists():
        return exact
    digits = "".join(ch for ch in q if ch.isdigit())
    cond = Q()
    for part in q.split():
        cond &= (
            Q(first_name__icontains=part)
            | Q(last_name__icontains=part)
            | Q(first_name_ar__icontains=part)
            | Q(last_name_ar__icontains=part)
        )
    if len(digits) >= 4:
        cond |= Q(mobile__contains=digits[-8:]) | Q(guardian_links__guardian__mobile__contains=digits[-8:])
    return qs.filter(cond).distinct().order_by("-is_active", "first_name")[:limit]
