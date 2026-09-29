"""
Daily operations rules (scope M9, business rules 11, 12 and 16). The desk calls these; the
rules live here only.
"""

import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.rbac.services import has_perm, notify_perm

from .models import SHIFT_CHECK_CODES, Complaint, Handover, Incident, ReferenceCounter, ShiftOpening


def _need(user, perm, branch_id, message):
    if not has_perm(user, perm, branch_id):
        raise PermissionDenied(message)


# ---------------------------------------------------------------------------
# Reference numbers: FRM-09-BED-2026-004
# ---------------------------------------------------------------------------
def next_reference(form: str, branch, year: int | None = None) -> str:
    """Next number for a form at a branch, handed out under a row lock (two desks never share one)."""
    year = year or timezone.localdate().year
    for _ in range(3):
        try:
            with transaction.atomic():
                counter, _ = ReferenceCounter.objects.select_for_update().get_or_create(
                    form=form, branch=branch, year=year
                )
                counter.last_number += 1
                counter.save(update_fields=["last_number"])
                return f"{form}-{branch.code}-{year}-{counter.last_number:03d}"
        except IntegrityError:
            continue  # another desk created the counter at the same moment; try again
    raise ValidationError("Could not assign a reference number. Try again.")


# ---------------------------------------------------------------------------
# Shift opening checklist (FRM-01)
# ---------------------------------------------------------------------------
@transaction.atomic
def complete_shift_opening(branch, day, shift, user, *, done, notes=None, hazard="", confirmed=False):
    _need(user, "ops.shift", branch.pk, "You cannot open a shift at this branch.")
    done = [c for c in SHIFT_CHECK_CODES if c in set(done)]
    missing = [c for c in SHIFT_CHECK_CODES if c not in done]
    notes = {k: v.strip()[:300] for k, v in (notes or {}).items() if k in SHIFT_CHECK_CODES and v.strip()}
    unexplained = [c for c in missing if c not in notes]
    if unexplained:
        raise ValidationError("Tick every check, or write a note for each one that could not be done.")
    if not confirmed:
        raise ValidationError("Confirm the checklist with your signature.")
    if ShiftOpening.objects.filter(branch=branch, date=day, shift=shift).exists():
        raise ValidationError("This shift has already been opened.")
    opening = ShiftOpening.objects.create(
        branch=branch,
        date=day,
        shift=shift,
        done=done,
        notes=notes,
        hazard=hazard.strip(),
        completed_by=user,
        created_by=user,
        updated_by=user,
    )
    if opening.hazard or missing:
        text = f"Shift opening {branch.code} {day:%d/%m} ({user.full_name}): " + (
            f"HAZARD: {opening.hazard}" if opening.hazard else ""
        )
        if missing:
            text += f" Not done: {', '.join(missing)}."
        transaction.on_commit(lambda: notify_perm("ops.manage", text, branch.pk, exclude=user))
    return opening


def shift_opened(branch, day) -> bool:
    return ShiftOpening.objects.filter(branch=branch, date=day).exists()


# ---------------------------------------------------------------------------
# Incidents (FRM-09)
# ---------------------------------------------------------------------------
@transaction.atomic
def report_incident(branch, user, **data) -> Incident:
    _need(user, "ops.incident", branch.pk, "You cannot report incidents for this branch.")
    member = data.get("member")
    if member is not None and member.is_minor:
        if not data.get("guardian_informed_at") or not (data.get("guardian_informed_name") or "").strip():
            raise ValidationError("A child was involved: record which guardian was told and when (rule 11).")
    if data.get("occurred_at") and data["occurred_at"] > timezone.now() + datetime.timedelta(minutes=5):
        raise ValidationError("The incident time cannot be in the future.")
    now = timezone.now()
    needs_ceo = bool(data.pop("needs_ceo", False))
    incident = Incident.objects.create(
        branch=branch,
        reference=next_reference("FRM-09", branch),
        needs_ceo=needs_ceo,
        ceo_due_at=now + datetime.timedelta(hours=Incident.CEO_HOURS) if needs_ceo else None,
        om_notified_at=now,
        created_by=user,
        updated_by=user,
        **data,
    )
    text = (
        f"Incident {incident.reference} ({incident.get_kind_display()}) at {branch.code}, reported by "
        f"{user.full_name}: {incident.what_happened[:200]}"
        + (" — safety/removal: the CEO must be told within 24 hours." if needs_ceo else "")
    )
    transaction.on_commit(lambda: notify_perm("ops.manage", text, branch.pk, exclude=user))
    return incident


def _ceo_users():
    from django.contrib.auth import get_user_model

    from apps.rbac.models import RoleAssignment

    ceo_ids = RoleAssignment.objects.current().filter(role__code="ceo").values("user_id")
    return list(get_user_model().objects.filter(pk__in=ceo_ids, is_active=True))


@transaction.atomic
def escalate_to_ceo(incident: Incident, user, note="") -> Incident:
    incident = Incident.objects.select_for_update().get(pk=incident.pk)
    _need(user, "ops.manage", incident.branch_id, "Only the Operations Manager escalates incidents.")
    if incident.ceo_escalated_at:
        raise ValidationError("This incident has already been escalated to the CEO.")
    incident.needs_ceo = True
    incident.ceo_escalated_at, incident.ceo_escalated_by = timezone.now(), user
    incident.updated_by = user
    incident.save()
    record_event(action="incident_escalated", instance=incident, branch_id=incident.branch_id)
    text = f"Incident {incident.reference} escalated by {user.full_name}: {incident.what_happened[:200]} {note}".strip()
    transaction.on_commit(lambda: _message(_ceo_users(), text))
    return incident


def auto_escalate_overdue(now=None) -> int:
    """Hourly: a safety or removal incident not escalated within 24 hours goes to the CEO anyway."""
    now = now or timezone.now()
    count = 0
    for incident in Incident.objects.filter(needs_ceo=True, ceo_escalated_at__isnull=True, ceo_due_at__lt=now):
        with transaction.atomic():
            updated = Incident.objects.filter(pk=incident.pk, ceo_escalated_at__isnull=True).update(
                ceo_escalated_at=now, ceo_auto_escalated=True
            )
        if updated:
            record_event(action="incident_auto_escalated", instance=incident, branch_id=incident.branch_id)
            _message(
                _ceo_users(),
                f"Incident {incident.reference} was not escalated within 24 hours and is sent to you automatically: "
                f"{incident.what_happened[:200]}",
            )
            count += 1
    return count


@transaction.atomic
def update_incident_follow_up(incident: Incident, user, *, owner=None, due=None) -> Incident:
    _need(user, "ops.manage", incident.branch_id, "Only the Operations Manager assigns incident follow-up.")
    incident.follow_up_owner, incident.follow_up_due, incident.updated_by = owner, due, user
    incident.save(update_fields=["follow_up_owner", "follow_up_due", "updated_by", "updated_at"])
    if owner is not None and owner.mobile and owner != user:
        text = f"You own the follow-up of incident {incident.reference}" + (f", due {due:%d/%m}." if due else ".")
        transaction.on_commit(lambda: _message([owner], text))
    return incident


@transaction.atomic
def close_incident(incident: Incident, user, note: str) -> Incident:
    incident = Incident.objects.select_for_update().get(pk=incident.pk)
    _need(user, "ops.manage", incident.branch_id, "Only the Operations Manager closes incidents.")
    if incident.status == Incident.Status.CLOSED:
        raise ValidationError("This incident is already closed.")
    if not note.strip():
        raise ValidationError("Write what was done before closing the incident.")
    if incident.needs_ceo and not incident.ceo_escalated_at:
        raise ValidationError("A safety or removal incident must reach the CEO before it is closed.")
    incident.status, incident.closed_at, incident.closed_by = Incident.Status.CLOSED, timezone.now(), user
    incident.closure_note, incident.updated_by = note.strip(), user
    incident.save()
    return incident


# ---------------------------------------------------------------------------
# Complaints (FRM-10)
# ---------------------------------------------------------------------------
@transaction.atomic
def log_complaint(branch, user, **data) -> Complaint:
    _need(user, "ops.complaint", branch.pk, "You cannot log complaints for this branch.")
    if not data.get("member") and not (data.get("contact_name") or "").strip():
        raise ValidationError("Choose the member or write the person's name.")
    received = data["received_at"] = data.get("received_at") or timezone.now()
    escalated = data["category"] in Complaint.ESCALATE
    complaint = Complaint.objects.create(
        branch=branch,
        reference=next_reference("FRM-10", branch),
        handled_by=user,
        escalated=escalated,
        reply_due_at=received + datetime.timedelta(hours=Complaint.REPLY_HOURS),
        created_by=user,
        updated_by=user,
        **data,
    )
    if escalated:
        text = (
            f"Complaint {complaint.reference} ({complaint.get_category_display()}) at {branch.code} from "
            f"{complaint.who}: {complaint.details[:200]}. Reply due within 24 hours."
        )
        transaction.on_commit(lambda: notify_perm("ops.manage", text, branch.pk, exclude=user))
    return complaint


def _can_handle(user, complaint):
    return complaint.handled_by_id == user.pk or has_perm(user, "ops.manage", complaint.branch_id)


@transaction.atomic
def record_reply(complaint: Complaint, user, note: str) -> Complaint:
    complaint = Complaint.objects.select_for_update().get(pk=complaint.pk)
    if not _can_handle(user, complaint):
        raise PermissionDenied("Only the person handling this complaint or the OM can update it.")
    if not note.strip():
        raise ValidationError("Write what the member was told.")
    complaint.replied_at = complaint.replied_at or timezone.now()
    complaint.action_outcome = (complaint.action_outcome + "\n" if complaint.action_outcome else "") + note.strip()
    complaint.updated_by = user
    complaint.save()
    return complaint


@transaction.atomic
def close_complaint(complaint: Complaint, user, *, outcome: str, member_informed_at) -> Complaint:
    complaint = Complaint.objects.select_for_update().get(pk=complaint.pk)
    if complaint.escalated:
        _need(user, "ops.manage", complaint.branch_id, "An escalated complaint is closed by the Operations Manager.")
    elif not _can_handle(user, complaint):
        raise PermissionDenied("Only the person handling this complaint or the OM can close it.")
    if complaint.status == Complaint.Status.CLOSED:
        raise ValidationError("This complaint is already closed.")
    if not member_informed_at:
        raise ValidationError("A complaint is closed only when the member has been told the outcome (rule 12).")
    if not outcome.strip():
        raise ValidationError("Write the outcome.")
    complaint.action_outcome = (complaint.action_outcome + "\n" if complaint.action_outcome else "") + outcome.strip()
    complaint.member_informed_at = member_informed_at
    complaint.replied_at = complaint.replied_at or member_informed_at
    complaint.status, complaint.closed_at, complaint.closed_by = Complaint.Status.CLOSED, timezone.now(), user
    complaint.updated_by = user
    complaint.save()
    return complaint


def remind_overdue_complaints(now=None) -> int:
    """Hourly: one reminder to the handler and the OM when the 24-hour reply is missed."""
    now = now or timezone.now()
    count = 0
    for c in Complaint.objects.filter(
        status=Complaint.Status.OPEN, replied_at__isnull=True, reply_due_at__lt=now, reply_reminder_sent=False
    ).select_related("handled_by", "branch"):
        if not Complaint.objects.filter(pk=c.pk, reply_reminder_sent=False).update(reply_reminder_sent=True):
            continue
        text = f"Complaint {c.reference} from {c.who} has had no reply for 24 hours."
        _message([c.handled_by], text)
        notify_perm("ops.manage", text, c.branch_id, exclude=c.handled_by)
        count += 1
    return count


# ---------------------------------------------------------------------------
# Cover & handover (FRM-11)
# ---------------------------------------------------------------------------
def handover_items(branch, outgoing, today=None) -> list[dict]:
    """The open-items list, built from live data (scope M9)."""
    from apps.classes.models import Booking
    from apps.renewals.models import InstructorHandoff
    from apps.renewals.services import follow_up_list
    from apps.sales.models import AccountRequest, CashUp
    from apps.sales.services import expected_totals
    from apps.website.models import TrialRequest

    today = today or timezone.localdate()
    cash_today = expected_totals(branch, today)["cash"]
    last_cash_up = CashUp.objects.filter(branch=branch).order_by("-date").first()
    unsubmitted = CashUp.objects.filter(branch=branch, status=CashUp.Status.DRAFT).count()
    pending_requests = AccountRequest.objects.filter(branch=branch, status=AccountRequest.Status.PENDING).count()
    follow_ups = follow_up_list(branch, today)
    leads = TrialRequest.objects.filter(branch=branch, status__in=["new", "contacted"]).count()
    trials = Booking.objects.filter(
        session__branch=branch, session__date__gte=today, is_trial=True, status=Booking.Status.BOOKED
    ).count()
    complaints = list(
        Complaint.objects.filter(branch=branch, status=Complaint.Status.OPEN).values_list("reference", flat=True)
    )
    incidents = list(
        Incident.objects.filter(branch=branch, status=Incident.Status.OPEN).values_list("reference", flat=True)
    )
    own_handoffs = InstructorHandoff.objects.filter(instructor=outgoing, done_at__isnull=True).count()

    def item(code, en, ar, details):
        return {"code": code, "en": en, "ar": ar, "details": details, "accepted_at": None}

    last = (
        f"last cash-up {last_cash_up.date:%d/%m/%Y} ({last_cash_up.get_status_display()})"
        if last_cash_up
        else "no cash-up yet"
    )
    return [
        item(
            "cash",
            "Cash held and last sales report",
            "النقد الموجود وآخر تقرير مبيعات",
            f"Cash taken today {cash_today:.3f} KD; {last}; {unsubmitted} cash-up(s) not submitted.",
        ),
        item(
            "payments",
            "Pending payments and requests",
            "المدفوعات والطلبات المعلقة",
            f"{pending_requests} freeze/refund/cancellation request(s) waiting for the OM.",
        ),
        item(
            "follow_ups",
            "Open renewal follow-ups",
            "متابعات التجديد المفتوحة",
            f"{len(follow_ups)} member(s) on the renewals list; {own_handoffs} handed to {outgoing.full_name}.",
        ),
        item(
            "leads",
            "Open leads and booked trials",
            "العملاء المحتملون والتجارب المحجوزة",
            f"{leads} trial request(s) not yet booked; {trials} trial(s) booked from today.",
        ),
        item(
            "cases",
            "Open complaints and incidents",
            "الشكاوى والحوادث المفتوحة",
            f"Complaints: {', '.join(complaints) or 'none'}. Incidents: {', '.join(incidents) or 'none'}.",
        ),
        item(
            "purchasing",
            "Pending purchase requests and transfers",
            "طلبات الشراء والتحويلات المعلقة",
            "On the paper forms (EA-INV-FRM-03/05) until inventory moves into the system in Phase 3.",
        ),
        item(
            "stock",
            "Stock count status and keys",
            "حالة الجرد والمفاتيح",
            "Last monthly count sheet (FRM-08) and the stock room keys.",
        ),
        item(
            "logins",
            "System access",
            "صلاحيات الأنظمة",
            "The incoming person uses their own desk login; no passwords are shared.",
        ),
        item("files", "Files, forms and branch keys", "الملفات والنماذج ومفاتيح الفرع", "Handed over in person."),
    ]


@transaction.atomic
def name_cover(branch, user, *, outgoing, incoming, cover_from, cover_to=None, leaving=False, last_day=None, note=""):
    _need(user, "ops.manage", branch.pk, "Only the Operations Manager names cover.")
    if outgoing == incoming:
        raise ValidationError("The cover must be a different person.")
    if not has_perm(incoming, "sales.view", branch.pk) and not has_perm(incoming, "classes.view", branch.pk):
        raise ValidationError(f"{incoming.full_name} has no access to this branch yet. Assign a role first.")
    if cover_to and cover_to < cover_from:
        raise ValidationError("The cover must end after it starts.")
    if leaving and not last_day:
        raise ValidationError("Enter the leaver's last day; their access ends after it (rule 16).")
    handover = Handover.objects.create(
        branch=branch,
        outgoing=outgoing,
        incoming=incoming,
        cover_from=cover_from,
        cover_to=cover_to,
        outgoing_leaving=leaving,
        last_day=last_day if leaving else None,
        items=handover_items(branch, outgoing),
        note=note.strip(),
        created_by=user,
        updated_by=user,
    )
    if leaving:
        end_access_after(outgoing, last_day, user)
    text = (
        f"{user.full_name} named you to cover for {outgoing.full_name} at {branch.name} from "
        f"{cover_from:%d/%m}. Open the desk to accept the handover items."
    )
    transaction.on_commit(lambda: _message([incoming], text))
    return handover


def end_access_after(person, last_day, by):
    """A leaver's roles end the day after their last day; the account is closed by the daily job."""
    from apps.rbac.models import RoleAssignment

    ends = last_day + datetime.timedelta(days=1)
    RoleAssignment.objects.filter(user=person).filter(ends_on__isnull=True).update(ends_on=ends)
    RoleAssignment.objects.filter(user=person, ends_on__gt=ends).update(ends_on=ends)
    profile = getattr(person, "staff_profile", None)
    if profile is not None:
        profile.end_date = last_day
        profile.save(update_fields=["end_date", "updated_at"])
    record_event(
        action="leaver_access_scheduled",
        object_type="User",
        object_id=str(person.pk),
        changes={"last_day": str(last_day)},
        actor=by,
    )


def close_leaver_accounts(today=None) -> int:
    """Daily: staff whose last day has passed lose all access (rule 16, ISO 27001 A.5.18)."""
    from apps.staff.models import StaffProfile

    today = today or timezone.localdate()
    count = 0
    for profile in StaffProfile.objects.filter(end_date__lt=today, user__is_active=True).select_related("user"):
        profile.user.deactivate()
        record_event(action="leaver_deactivated", object_type="User", object_id=str(profile.user_id))
        count += 1
    return count


@transaction.atomic
def accept_handover_item(handover: Handover, user, code: str) -> Handover:
    handover = Handover.objects.select_for_update().get(pk=handover.pk)
    if handover.incoming_id != user.pk:
        raise PermissionDenied("Only the incoming person accepts handover items.")
    found = False
    for item in handover.items:
        if item["code"] == code and not item.get("accepted_at"):
            item["accepted_at"] = timezone.now().isoformat()
            found = True
    if not found:
        raise ValidationError("That item is already accepted.")
    if handover.items_left == 0:
        handover.status, handover.accepted_at = Handover.Status.ACCEPTED, timezone.now()
    handover.updated_by = user
    handover.save()
    return handover


def _message(users, text):
    from apps.core.messaging import send_message

    for u in users:
        if u is not None and u.mobile:
            send_message(u.mobile, text)
