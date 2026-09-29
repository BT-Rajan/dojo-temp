"""
Renewals and retention (scope M6, business rule 4, Phase 1 decisions of 29 Sep 2026):

- Daily list per branch: memberships expired in the last 30 days or expiring within 5 days,
  excluding trials, passes, camps, seminars and private sessions, and skipping anyone who
  already renewed. Members who were checked in without a valid membership in the last week
  are added too, however long ago their membership ended.
- Outcomes R / W / F / L / N. "No answer" carries to the next shift; after 3 attempts the
  member is passed to their instructor.
- Automatic reminders 5 days and 1 day before expiry.
- At risk: active members with no visit in 14 days.
"""

import datetime
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.audit.services import record_event
from apps.classes.models import Attendance, Enrollment
from apps.core.messaging import send_message
from apps.core.validators import day_range
from apps.members.services import contact_language, contact_mobile, display_name
from apps.organization.models import PricingOption
from apps.rbac.services import has_perm
from apps.sales.models import Membership

from .models import FollowUp, InstructorHandoff, ReminderSent

EXPIRED_WINDOW = 30
EXPIRING_WINDOW = 5
NO_ANSWER_LIMIT = 3
REMINDER_DAYS = (5, 1)
AT_RISK_DAYS = 14


@dataclass
class Row:
    membership: Membership
    member: object
    state: str  # expiring, expired, checked_in_expired
    days: int  # days left (positive) or days since expiry (negative)
    last: FollowUp | None
    no_answers: int
    handoff: InstructorHandoff | None


def _membership_qs():
    return Membership.objects.filter(
        pricing_option__kind=PricingOption.Kind.MEMBERSHIP,
        status=Membership.Status.ACTIVE,
        member__is_active=True,
    ).select_related("member", "pricing_option", "branch")


def _renewed(membership: Membership) -> bool:
    return Membership.objects.filter(
        member_id=membership.member_id,
        pricing_option__kind=PricingOption.Kind.MEMBERSHIP,
        status=Membership.Status.ACTIVE,
        end_date__gt=membership.end_date,
    ).exists()


def follow_up_list(branch, today=None) -> list[Row]:
    today = today or timezone.localdate()
    window = _membership_qs().filter(
        branch=branch,
        end_date__gte=today - datetime.timedelta(days=EXPIRED_WINDOW),
        end_date__lte=today + datetime.timedelta(days=EXPIRING_WINDOW),
    )
    # Latest membership per member only.
    candidates = {}
    for m in window.order_by("end_date"):
        candidates[m.member_id] = m
    # Checked in without a valid membership this week → straight onto the list (decision 2).
    recent = Attendance.objects.filter(
        session__branch=branch,
        checked_in_at__gte=day_range(today - datetime.timedelta(days=7))[0],
        warning__in=[Attendance.Warning.EXPIRED, Attendance.Warning.NO_MEMBERSHIP],
    ).values_list("member_id", flat=True)
    for member_id in set(recent) - set(candidates):
        latest = _membership_qs().filter(member_id=member_id).order_by("-end_date").first()
        if latest is not None and latest.end_date < today:
            candidates[member_id] = latest

    rows = []
    for m in candidates.values():
        if _renewed(m):
            continue
        attempts = list(m.follow_ups.all())
        last = attempts[0] if attempts else None
        if last is not None and last.outcome in (FollowUp.Outcome.RENEWED, FollowUp.Outcome.LEAVING):
            continue
        state = (
            "expiring"
            if m.end_date >= today
            else ("expired" if (today - m.end_date).days <= EXPIRED_WINDOW else "checked_in_expired")
        )
        rows.append(
            Row(
                m,
                m.member,
                state,
                (m.end_date - today).days,
                last,
                sum(1 for a in attempts if a.outcome == FollowUp.Outcome.NO_ANSWER),
                InstructorHandoff.objects.filter(membership=m).first(),
            )
        )
    # Expiring soonest first, then most recently expired.
    return sorted(rows, key=lambda r: (r.state != "expiring", abs(r.days)))


def instructor_for(member):
    enrollment = (
        Enrollment.objects.filter(member=member, end_date__isnull=True)
        .select_related("slot")
        .prefetch_related("slot__instructors")
        .first()
    )
    if enrollment is None:
        return None
    return enrollment.slot.instructors.first()


@transaction.atomic
def record_follow_up(
    membership: Membership,
    user,
    *,
    outcome,
    channel=FollowUp.Channel.WHATSAPP,
    will_renew_on=None,
    leaving_reason="",
    note="",
) -> FollowUp:
    if not has_perm(user, "renewals.follow_up", membership.branch_id):
        raise PermissionDenied("You cannot work the renewals list for this branch.")
    if outcome not in FollowUp.Outcome.values:
        raise ValidationError("Choose R, W, F, L or N.")
    if outcome == FollowUp.Outcome.WILL_RENEW and will_renew_on is None:
        raise ValidationError("When will they renew?")
    if outcome == FollowUp.Outcome.LEAVING and not leaving_reason.strip():
        raise ValidationError("Why are they leaving? (It feeds the weekly report.)")
    membership = Membership.objects.select_for_update().get(pk=membership.pk)
    attempt = 1
    if outcome == FollowUp.Outcome.NO_ANSWER:
        attempt = membership.follow_ups.filter(outcome=FollowUp.Outcome.NO_ANSWER).count() + 1
    fu = FollowUp.objects.create(
        membership=membership,
        member=membership.member,
        branch=membership.branch,
        outcome=outcome,
        channel=channel,
        attempt=attempt,
        will_renew_on=will_renew_on,
        leaving_reason=leaving_reason.strip(),
        note=note.strip(),
        contacted_by=user,
    )
    record_event(
        action="renewal_follow_up",
        instance=fu,
        branch_id=membership.branch_id,
        changes={"outcome": outcome, "attempt": attempt},
    )
    if outcome == FollowUp.Outcome.NO_ANSWER and attempt >= NO_ANSWER_LIMIT:
        try:
            with transaction.atomic():
                InstructorHandoff.objects.create(
                    membership=membership, member=membership.member, instructor=instructor_for(membership.member)
                )
        except IntegrityError:
            pass
    return fu


@transaction.atomic
def complete_handoff(handoff: InstructorHandoff, user, note=""):
    if handoff.instructor_id not in (None, user.pk) and not has_perm(
        user, "renewals.follow_up", handoff.membership.branch_id
    ):
        raise PermissionDenied("This conversation is assigned to another instructor.")
    handoff.done_at, handoff.note = timezone.now(), note.strip()
    handoff.save(update_fields=["done_at", "note"])
    record_event(
        action="renewal_handoff_done",
        object_type="InstructorHandoff",
        object_id=str(handoff.pk),
        branch_id=handoff.membership.branch_id,
    )


def reminder_text(membership: Membership, lang: str, days: int) -> str:
    name = display_name(membership.member, lang)
    end = membership.end_date.strftime("%d/%m/%Y")
    if lang == "ar":
        when = "غداً" if days == 1 else f"خلال {days} أيام"
        return (
            f"مرحباً! اشتراك {name} في أكاديمية إيليت ينتهي {when} ({end}). جدّد في الفرع أو راسلنا هنا ليبقى على مساره."
        )
    when = "tomorrow" if days == 1 else f"in {days} days"
    return (
        f"Hi! {name}'s Elite Academy membership ends {when} ({end}). "
        "Renew at the front desk or reply here to keep the path going."
    )


def send_reminders(today=None) -> int:
    """Runs every morning. One message per membership per reminder day."""
    today = today or timezone.localdate()
    sent = 0
    for days in REMINDER_DAYS:
        for m in _membership_qs().filter(end_date=today + datetime.timedelta(days=days)):
            if _renewed(m):
                continue
            mobile = contact_mobile(m.member)
            if not mobile:
                continue
            try:
                with transaction.atomic():
                    ReminderSent.objects.create(membership=m, days_before=days, sent_to=mobile)
            except IntegrityError:
                continue  # already sent
            send_message(mobile, reminder_text(m, contact_language(m.member), days))
            sent += 1
    return sent


def at_risk(branch, today=None, days=AT_RISK_DAYS):
    """Active members with no visit in `days` days (the 'No visit found' check)."""
    today = today or timezone.localdate()
    since = today - datetime.timedelta(days=days)
    active = _membership_qs().filter(branch=branch, start_date__lte=since, end_date__gte=today)
    member_ids = set(active.values_list("member_id", flat=True))
    last_visits = dict(
        Attendance.objects.filter(member_id__in=member_ids)
        .values("member_id")
        .annotate(last=Max("checked_in_at"))
        .values_list("member_id", "last")
    )
    out = []
    for m in active.order_by("member__last_name"):
        last = last_visits.get(m.member_id)
        if last is None or timezone.localtime(last).date() < since:
            out.append((m.member, m, last))
    seen, unique = set(), []
    for row in out:
        if row[0].pk not in seen:
            seen.add(row[0].pk)
            unique.append(row)
    return unique
