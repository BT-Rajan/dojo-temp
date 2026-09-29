"""Helpers shared by classes, sales and renewals: who to message about a member, and families."""

from .models import GuardianLink, Member


def primary_guardian(member: Member):
    links = sorted(member.guardian_links.all(), key=lambda link: (not link.is_primary, link.pk))
    return links[0].guardian if links else None


def contact_mobile(member: Member) -> str:
    """Children are reached through their primary guardian; adults on their own number."""
    if member.is_minor or not member.mobile:
        guardian = primary_guardian(member)
        if guardian is not None and guardian.mobile:
            return guardian.mobile
    return member.mobile or ""


def contact_language(member: Member) -> str:
    guardian = primary_guardian(member) if member.is_minor else None
    user = (guardian.user if guardian else None) or member.user
    return getattr(user, "preferred_language", "") or "ar"


def siblings(member: Member):
    """Other active members who share a guardian with this member (family discount)."""
    guardian_ids = GuardianLink.objects.filter(member=member).values_list("guardian_id", flat=True)
    return (
        Member.objects.filter(guardian_links__guardian_id__in=guardian_ids, is_active=True)
        .exclude(pk=member.pk)
        .distinct()
    )


def display_name(member: Member, lang: str = "en") -> str:
    if lang == "ar" and member.first_name_ar:
        return f"{member.first_name_ar} {member.last_name_ar}".strip()
    return f"{member.first_name} {member.last_name}"
