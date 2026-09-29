"""
Class rules (scope M4 and the Phase 1 decisions of 29 Sep 2026):

- Regular members are enrolled in their weekly classes and simply checked in; booking is for
  trials, full classes and events. Walk-ins are allowed.
- A class has a capacity; regulars and bookings share it. When full, bookings go on a
  waiting list, and the first person waiting moves up (and is told) when a place frees.
- Check-in with an expired or missing membership shows a warning but is allowed; the member
  goes onto the renewals list.
- No-shows and late cancellations (less than 2 hours before) are recorded, with no penalty.
- Class changes need approval by the Training Lead or Operations Manager (not the requester).
  Changes asked for less than 2 hours before the class are allowed but flagged urgent.
  Every booked and regular member is messaged and the send is logged.
"""

import datetime
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.messaging import send_message
from apps.core.validators import normalize_kuwait_mobile
from apps.members.models import Member
from apps.members.services import contact_language, contact_mobile
from apps.rbac.services import has_perm

from .models import Attendance, Booking, ClassChange, ClassSession, ClassSlot, Enrollment, kuwait_weekday

DAYS_AHEAD = 28
NOTICE = datetime.timedelta(hours=2)
CHECK_IN_EARLY = datetime.timedelta(minutes=60)


def _need(user, perm, branch_id, message):
    if not has_perm(user, perm, branch_id):
        raise PermissionDenied(message)


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
@transaction.atomic
def generate_sessions(start=None, days=DAYS_AHEAD, slots=None) -> int:
    """Creates the dated sessions for the next `days` days. Safe to run any number of times."""
    start = start or timezone.localdate()
    slots = list(
        (slots or ClassSlot.objects.filter(is_active=True)).select_related("branch").prefetch_related("instructors")
    )
    created = 0
    for offset in range(days):
        day = start + datetime.timedelta(days=offset)
        for slot in slots:
            if not slot.runs_on(day) or kuwait_weekday(day) not in (slot.branch.open_days or range(7)):
                continue
            session, made = ClassSession.objects.get_or_create(
                slot=slot,
                date=day,
                defaults=dict(
                    branch=slot.branch,
                    program=slot.program,
                    room=slot.room,
                    title_en=slot.title_en,
                    title_ar=slot.title_ar,
                    start=slot.start,
                    end=slot.end,
                    capacity=slot.capacity,
                ),
            )
            if made:
                session.instructors.set(slot.instructors.all())
                created += 1
    return created


def enrolled_members(session: ClassSession):
    if not session.slot_id:
        return Member.objects.none()
    return (
        Member.objects.filter(
            enrollments__slot_id=session.slot_id,
            enrollments__start_date__lte=session.date,
            is_active=True,
        )
        .filter(Q(enrollments__end_date__isnull=True) | Q(enrollments__end_date__gte=session.date))
        .distinct()
    )


def places_taken(session: ClassSession) -> int:
    regulars = set(enrolled_members(session).values_list("pk", flat=True))
    booked = session.bookings.filter(status__in=[Booking.Status.BOOKED, Booking.Status.ATTENDED])
    extra = sum(1 for b in booked if b.member_id is None or b.member_id not in regulars)
    return len(regulars) + extra


@dataclass
class RosterRow:
    member: Member | None
    name: str
    kind: str  # regular, booked, trial, walk_in, waitlist
    booking: Booking | None
    attendance: Attendance | None


def roster(session: ClassSession) -> list[RosterRow]:
    """The coach's class list: regulars, bookings, trials, walk-ins and the waiting list."""
    visits = {a.member_id: a for a in session.attendance.select_related("member") if a.member_id}
    guest_visits = {a.booking_id: a for a in session.attendance.all() if a.member_id is None}
    rows, seen = [], set()
    for m in enrolled_members(session).prefetch_related("guardian_links__guardian"):
        rows.append(RosterRow(m, str(m), "regular", None, visits.get(m.pk)))
        seen.add(m.pk)
    for b in session.bookings.exclude(status=Booking.Status.CANCELLED).select_related("member"):
        if b.member_id in seen:
            continue
        kind = "waitlist" if b.status == Booking.Status.WAITLISTED else ("trial" if b.is_trial else "booked")
        visit = visits.get(b.member_id) if b.member_id else guest_visits.get(b.pk)
        rows.append(RosterRow(b.member, b.display_name, kind, b, visit))
        if b.member_id:
            seen.add(b.member_id)
    for member_id, visit in visits.items():
        if member_id not in seen:
            rows.append(RosterRow(visit.member, str(visit.member), "walk_in", None, visit))
    return rows


@transaction.atomic
def enroll(member: Member, slot: ClassSlot, user, start_date=None) -> Enrollment:
    """Gives a member a regular weekly place (one open enrollment per slot)."""
    _need(user, "classes.book", slot.branch_id, "You cannot enrol members at this branch.")
    slot = ClassSlot.objects.select_for_update().get(pk=slot.pk)
    if Enrollment.objects.filter(member=member, slot=slot, end_date__isnull=True).exists():
        raise ValidationError(f"{member} is already a regular in this class.")
    enrollment = Enrollment.objects.create(
        member=member, slot=slot, start_date=start_date or timezone.localdate(), created_by=user, updated_by=user
    )
    record_event(action="enrolled", instance=enrollment, branch_id=slot.branch_id)
    return enrollment


@transaction.atomic
def end_enrollment(enrollment: Enrollment, user, end_date=None) -> Enrollment:
    _need(user, "classes.book", enrollment.slot.branch_id, "You cannot change enrolments at this branch.")
    enrollment.end_date = end_date or timezone.localdate()
    enrollment.updated_by = user
    enrollment.save(update_fields=["end_date", "updated_by", "updated_at"])
    record_event(action="enrollment_ended", instance=enrollment, branch_id=enrollment.slot.branch_id)
    return enrollment


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------
@transaction.atomic
def book(
    session: ClassSession,
    user,
    *,
    member: Member | None = None,
    guest_name="",
    guest_mobile="",
    trial_request=None,
    source=Booking.Source.DESK,
    is_trial=False,
    note="",
) -> Booking:
    _need(user, "classes.book", session.branch_id, "You cannot book classes at this branch.")
    session = ClassSession.objects.select_for_update().get(pk=session.pk)  # one booking at a time per class
    if session.is_cancelled:
        raise ValidationError("This class is cancelled.")
    if session.is_over:
        raise ValidationError("This class has already finished.")
    if member is None:
        if not guest_name.strip() or not guest_mobile:
            raise ValidationError("A trial booking needs a name and a mobile number.")
        guest_mobile = normalize_kuwait_mobile(guest_mobile)
        is_trial = True
    elif enrolled_members(session).filter(pk=member.pk).exists():
        raise ValidationError(f"{member} already has a regular place in this class.")
    elif session.bookings.filter(member=member).exclude(status=Booking.Status.CANCELLED).exists():
        raise ValidationError(f"{member} is already booked into this class.")
    status = Booking.Status.BOOKED if places_taken(session) < session.capacity else Booking.Status.WAITLISTED
    booking = Booking.objects.create(
        session=session,
        member=member,
        guest_name=guest_name.strip(),
        guest_mobile=guest_mobile,
        trial_request=trial_request,
        status=status,
        source=source,
        is_trial=is_trial,
        note=note,
        created_by=user,
        updated_by=user,
    )
    record_event(
        action="class_booked",
        instance=booking,
        branch_id=session.branch_id,
        changes={"status": status, "trial": is_trial},
    )
    return booking


@transaction.atomic
def cancel_booking(booking: Booking, user) -> Booking:
    booking = Booking.objects.select_for_update().select_related("session").get(pk=booking.pk)
    _need(user, "classes.book", booking.session.branch_id, "You cannot change bookings at this branch.")
    if booking.status in (Booking.Status.CANCELLED, Booking.Status.ATTENDED, Booking.Status.NO_SHOW):
        raise ValidationError("This booking can no longer be cancelled.")
    was_place = booking.status == Booking.Status.BOOKED
    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = timezone.now()
    booking.late_cancellation = was_place and booking.session.starts_at - booking.cancelled_at < NOTICE
    booking.updated_by = user
    booking.save()
    record_event(
        action="booking_cancelled",
        instance=booking,
        branch_id=booking.session.branch_id,
        changes={"late": booking.late_cancellation},
    )
    if was_place:
        promote_waitlist(booking.session)
    return booking


def promote_waitlist(session: ClassSession):
    session = ClassSession.objects.select_for_update().get(pk=session.pk)
    while places_taken(session) < session.capacity:
        nxt = session.bookings.filter(status=Booking.Status.WAITLISTED).order_by("created_at").first()
        if nxt is None:
            return
        nxt.status = Booking.Status.BOOKED
        nxt.save(update_fields=["status", "updated_at"])
        record_event(action="waitlist_promoted", instance=nxt, branch_id=session.branch_id)
        mobile = contact_mobile(nxt.member) if nxt.member_id else nxt.guest_mobile
        lang = contact_language(nxt.member) if nxt.member_id else "ar"
        if mobile:
            when = f"{session.date:%d/%m} {session.start:%H:%M}"
            text = (
                f"أصبح لديك مكان في حصة {session.title_ar or session.title_en} يوم {when}."
                if lang == "ar"
                else f"A place opened up for you: {session.title_en} on {when}."
            )
            transaction.on_commit(lambda m=mobile, t=text: send_message(m, t))


# ---------------------------------------------------------------------------
# Check-in
# ---------------------------------------------------------------------------
def sessions_for_check_in(member: Member, branch, now=None):
    """Today's classes at this branch the member could be checking into, best match first."""
    now = now or timezone.localtime()
    today = now.date()
    sessions = list(
        ClassSession.objects.filter(branch=branch, date=today, status=ClassSession.Status.SCHEDULED).select_related(
            "slot", "program"
        )
    )
    open_now = [s for s in sessions if s.starts_at - CHECK_IN_EARLY <= now <= s.ends_at]
    mine = set(
        Enrollment.objects.filter(member=member, start_date__lte=today)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .values_list("slot_id", flat=True)
    )
    booked = set(
        Booking.objects.filter(member=member, session__in=sessions)
        .exclude(status=Booking.Status.CANCELLED)
        .values_list("session_id", flat=True)
    )

    def rank(s):
        return (0 if (s.slot_id in mine or s.pk in booked) else 1, abs((s.starts_at - now).total_seconds()))

    return sorted(open_now, key=rank), mine, booked


@transaction.atomic
def check_in(member: Member, session: ClassSession, user, method=Attendance.Method.DESK):
    """
    Records a visit. Returns (attendance, created, warning). Warnings never block the check-in
    (decision of 29 Sep 2026); they are shown to the desk and put the member on the renewals list.
    """
    from apps.sales.models import Membership
    from apps.sales.services import membership_for_class

    _need(user, "classes.checkin", session.branch_id, "You cannot check people in at this branch.")
    if session.is_cancelled:
        raise ValidationError("This class is cancelled.")
    existing = Attendance.objects.filter(session=session, member=member).first()
    if existing is not None:
        return existing, False, existing.warning
    membership, warning = membership_for_class(member, session.program_id, session.date)
    if membership is not None and not warning and membership.sessions_total is not None:
        # Lock the package so two desks can't both use its last session.
        membership = Membership.objects.select_for_update().get(pk=membership.pk)
        if membership.sessions_used >= membership.sessions_total:
            warning = Attendance.Warning.NO_SESSIONS
    enrolled = enrolled_members(session).filter(pk=member.pk).exists()
    booking = (
        Booking.objects.select_for_update()
        .filter(session=session, member=member)
        .exclude(status=Booking.Status.CANCELLED)
        .first()
    )
    try:
        with transaction.atomic():
            attendance = Attendance.objects.create(
                session=session,
                member=member,
                booking=booking,
                membership=membership if not warning else None,
                method=method,
                walk_in=not enrolled and booking is None,
                warning=warning,
                created_by=user,
                updated_by=user,
            )
    except IntegrityError:  # the coach and the desk pressed at the same moment
        existing = Attendance.objects.get(session=session, member=member)
        return existing, False, existing.warning
    if membership is not None and not warning and membership.sessions_total is not None:
        Membership.objects.filter(pk=membership.pk).update(sessions_used=F("sessions_used") + 1)
    if booking is not None:
        booking.status = Booking.Status.ATTENDED
        booking.save(update_fields=["status", "updated_at"])
    record_event(
        action="check_in",
        instance=attendance,
        branch_id=session.branch_id,
        changes={"method": method, "warning": warning, "walk_in": attendance.walk_in},
    )
    return attendance, True, warning


@transaction.atomic
def check_in_guest(booking: Booking, user) -> Attendance:
    """A trial guest (name and phone only) arrives."""
    booking = Booking.objects.select_for_update().select_related("session").get(pk=booking.pk)
    _need(user, "classes.checkin", booking.session.branch_id, "You cannot check people in at this branch.")
    if booking.member_id:
        return check_in(booking.member, booking.session, user)[0]
    attendance, _ = Attendance.objects.get_or_create(
        booking=booking,
        defaults=dict(session=booking.session, method=Attendance.Method.DESK, created_by=user, updated_by=user),
    )
    booking.status = Booking.Status.ATTENDED
    booking.save(update_fields=["status", "updated_at"])
    record_event(action="trial_attended", instance=booking, branch_id=booking.session.branch_id)
    return attendance


@transaction.atomic
def undo_check_in(attendance: Attendance, user):
    """Corrects a mistaken check-in on the same day; gives back a package session."""
    from apps.sales.models import Membership

    attendance = Attendance.objects.select_for_update().select_related("session").get(pk=attendance.pk)
    _need(user, "classes.checkin", attendance.session.branch_id, "You cannot change attendance at this branch.")
    if attendance.session.date != timezone.localdate():
        raise ValidationError("Only today's check-ins can be undone.")
    if attendance.membership_id:
        m = Membership.objects.select_for_update().get(pk=attendance.membership_id)
        if m.sessions_total is not None and m.sessions_used > 0:
            m.sessions_used -= 1
            m.save(update_fields=["sessions_used"])
    if attendance.booking_id:
        Booking.objects.filter(pk=attendance.booking_id).update(status=Booking.Status.BOOKED)
    record_event(action="check_in_undone", instance=attendance, branch_id=attendance.session.branch_id)
    attendance.delete()


def mark_no_shows(now=None) -> int:
    """Bookings for classes that have ended without a check-in are recorded as no-shows (no penalty)."""
    now = now or timezone.localtime()
    count = 0
    for b in Booking.objects.filter(status=Booking.Status.BOOKED, session__date__lte=now.date()).select_related(
        "session"
    ):
        if b.session.ends_at <= now:
            b.status = Booking.Status.NO_SHOW
            b.save(update_fields=["status", "updated_at"])
            count += 1
    return count


# ---------------------------------------------------------------------------
# Class changes (EA-OPS-FRM-04)
# ---------------------------------------------------------------------------
@transaction.atomic
def request_change(
    session: ClassSession, user, *, kind, reason, new_date=None, new_start=None, new_end=None, new_instructors=()
) -> ClassChange:
    _need(user, "classes.change_request", session.branch_id, "You cannot request class changes at this branch.")
    if session.is_cancelled or session.is_over:
        raise ValidationError("This class can no longer be changed.")
    if not reason.strip():
        raise ValidationError("Give a reason for the change.")
    if kind == ClassChange.Kind.RESCHEDULE:
        if not (new_date and new_start and new_end) or new_end <= new_start:
            raise ValidationError("Choose the new day, start and end time.")
        if new_date < timezone.localdate():
            raise ValidationError("A class cannot be moved into the past.")
    if kind == ClassChange.Kind.SUBSTITUTE and not new_instructors:
        raise ValidationError("Choose the coach who will teach.")
    if session.changes.filter(status=ClassChange.Status.PENDING).exists():
        raise ValidationError("A change for this class is already waiting for approval.")
    change = ClassChange.objects.create(
        session=session,
        kind=kind,
        reason=reason.strip(),
        new_date=new_date,
        new_start=new_start,
        new_end=new_end,
        urgent=session.starts_at - timezone.now() < NOTICE,
        created_by=user,
        updated_by=user,
    )
    if new_instructors:
        change.new_instructors.set(new_instructors)
    record_event(
        action="class_change_requested",
        instance=change,
        branch_id=session.branch_id,
        changes={"kind": kind, "urgent": change.urgent},
    )
    return change


def affected_contacts(session: ClassSession):
    """Mobile numbers of everyone expecting to be in this class: regulars, bookings, trial guests."""
    people = {}
    for m in enrolled_members(session).prefetch_related("guardian_links__guardian"):
        people[contact_mobile(m)] = contact_language(m)
    for b in session.bookings.filter(status__in=[Booking.Status.BOOKED, Booking.Status.WAITLISTED]).select_related(
        "member"
    ):
        if b.member_id:
            people[contact_mobile(b.member)] = contact_language(b.member)
        elif b.guest_mobile:
            people[b.guest_mobile] = "ar"
    people.pop("", None)
    return people


def _change_text(change: ClassChange, lang: str) -> str:
    s = change.session
    title = (s.title_ar or s.title_en) if lang == "ar" else s.title_en
    when = f"{s.date:%d/%m} {s.start:%H:%M}"
    if change.kind == ClassChange.Kind.CANCEL:
        return (
            f"نعتذر، تم إلغاء حصة {title} يوم {when}. السبب: {change.reason}"
            if lang == "ar"
            else f"Sorry — {title} on {when} is cancelled. Reason: {change.reason}"
        )
    if change.kind == ClassChange.Kind.RESCHEDULE:
        new = f"{change.new_date:%d/%m} {change.new_start:%H:%M}"
        return (
            f"تم تغيير موعد حصة {title} من {when} إلى {new}."
            if lang == "ar"
            else f"{title} on {when} has moved to {new}."
        )
    names = ", ".join(u.full_name for u in change.new_instructors.all())
    return (
        f"حصة {title} يوم {when} سيدرّبها {names}." if lang == "ar" else f"{title} on {when} will be taught by {names}."
    )


@transaction.atomic
def decide_change(change: ClassChange, approve: bool, user, note="") -> ClassChange:
    change = ClassChange.objects.select_for_update().select_related("session").get(pk=change.pk)
    session = ClassSession.objects.select_for_update().get(pk=change.session_id)
    _need(
        user,
        "classes.change_approve",
        session.branch_id,
        "Class changes are approved by the Training Lead or the Operations Manager.",
    )
    if change.status != ClassChange.Status.PENDING:
        raise ValidationError("This change has already been decided.")
    if change.created_by_id == user.pk:
        raise PermissionDenied("A change you requested must be approved by someone else.")
    change.decided_by, change.decided_at, change.decision_note = user, timezone.now(), note
    if not approve:
        change.status = ClassChange.Status.REJECTED
        change.save()
        record_event(action="class_change_rejected", instance=change, branch_id=session.branch_id)
        return change

    contacts = affected_contacts(session)  # before the change, so everyone who expected the class is told
    if change.kind == ClassChange.Kind.CANCEL:
        session.status = ClassSession.Status.CANCELLED
        session.bookings.filter(status__in=[Booking.Status.BOOKED, Booking.Status.WAITLISTED]).update(
            status=Booking.Status.CANCELLED, cancelled_at=timezone.now()
        )
    elif change.kind == ClassChange.Kind.RESCHEDULE:
        session.date, session.start, session.end = change.new_date, change.new_start, change.new_end
    else:
        session.instructors.set(change.new_instructors.all())
    session.updated_by = user
    session.save()

    for mobile, lang in contacts.items():
        text = _change_text(change, lang)
        transaction.on_commit(lambda m=mobile, t=text: send_message(m, t))
    change.status = ClassChange.Status.APPROVED
    change.notified_at, change.notified_channel, change.notified_count = timezone.now(), "whatsapp", len(contacts)
    change.save()
    record_event(
        action="class_change_approved",
        instance=change,
        branch_id=session.branch_id,
        changes={"kind": change.kind, "notified": len(contacts)},
    )
    return change


# ---------------------------------------------------------------------------
# Utilisation (scope M4: booked vs capacity, visit trends)
# ---------------------------------------------------------------------------
def utilisation(branch=None, start=None, end=None):
    end = end or timezone.localdate()
    start = start or end - datetime.timedelta(days=27)
    sessions = ClassSession.objects.filter(date__range=(start, end), status=ClassSession.Status.SCHEDULED)
    if branch is not None:
        sessions = sessions.filter(branch=branch)
    rows = (
        sessions.values("slot_id", "title_en", "title_ar", "branch__code", "start", "capacity")
        .annotate(held=Count("id", distinct=True), visits=Count("attendance", distinct=True))
        .order_by("branch__code", "title_en", "start")
    )
    out = []
    for r in rows:
        average = r["visits"] / r["held"] if r["held"] else 0
        out.append(
            {**r, "average": round(average, 1), "fill": round(100 * average / r["capacity"]) if r["capacity"] else 0}
        )
    return out
