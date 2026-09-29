"""
Leads, trials, group sales and marketing rules (M3, M13; decisions P5-1 to P5-10).
"""

import datetime
from collections import Counter
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.messaging import send_message
from apps.core.validators import normalize_kuwait_mobile
from apps.members.models import GuardianLink, Member
from apps.members.services import contact_language, contact_mobile
from apps.rbac.services import has_perm, notify_perm

from .models import (
    Activity,
    Broadcast,
    Campaign,
    GroupDeal,
    Lead,
    MessagingOptIn,
    ReferralCode,
    ReviewRequest,
)

FIRST_CONTACT_HOURS = 2  # P5-3
FOLLOW_UP_HOURS = 24
MATCH_DAYS = 180  # an enquiry from the same mobile within this time updates the open lead
REVIEW_EVERY_DAYS = 90  # P5-9
D = Decimal


def _need(user, perm, branch_id, message):
    if not has_perm(user, perm, branch_id):
        raise PermissionDenied(message)


def _log(user, text, kind=Activity.Kind.SYSTEM, lead=None, deal=None):
    return Activity.objects.create(lead=lead, deal=deal, kind=kind, text=text[:2000], by=user)


# ---------------------------------------------------------------------------
# Intake (P5-1)
# ---------------------------------------------------------------------------
def campaign_for(code):
    code = (code or "").strip().lower()
    return Campaign.objects.filter(code=code).first() if code else None


def referrer_for_code(code):
    code = (code or "").strip().upper()
    ref = ReferralCode.objects.filter(code=code).select_related("member").first() if code else None
    return ref.member if ref else None


@transaction.atomic
def intake(
    *,
    name,
    mobile,
    branch,
    source,
    program=None,
    interest="",
    language="ar",
    campaign=None,
    referrer=None,
    trial_request=None,
    chat=None,
    user=None,
    note="",
) -> Lead:
    """Every channel comes in here. Staff-entered leads (walk-in, phone) are owned by whoever records them."""
    if user is not None:
        _need(user, "leads.manage", branch.pk, "You cannot record leads for this branch.")
    if not (name or "").strip():
        raise ValidationError("Enter the name.")
    mobile = normalize_kuwait_mobile(mobile)
    if referrer is not None and source not in (Lead.Source.GROUP,):
        source = Lead.Source.REFERRAL if source in (Lead.Source.WALK_IN, Lead.Source.PHONE) else source
    now = timezone.now()
    lead = (
        Lead.objects.select_for_update()
        .filter(mobile=mobile, stage__in=Lead.OPEN, created_at__gte=now - datetime.timedelta(days=MATCH_DAYS))
        .order_by("-created_at")
        .first()
    )
    label = Lead.Source(source).label
    if lead is not None:
        lead.interest = lead.interest or interest[:200]
        lead.program = lead.program or program
        lead.campaign = lead.campaign or campaign
        lead.referrer = lead.referrer or referrer
        lead.trial_request = trial_request or lead.trial_request
        lead.chat = chat or lead.chat
        if lead.stage == Lead.Stage.NEW:
            due = now + datetime.timedelta(hours=FIRST_CONTACT_HOURS)
            lead.next_due = min(lead.next_due or due, due)
        lead.save()
        _log(user, f"New enquiry again ({label}). {note}".strip(), lead=lead)
        return lead
    staff = user is not None and source in (Lead.Source.WALK_IN, Lead.Source.PHONE, Lead.Source.REFERRAL)
    lead = Lead.objects.create(
        name=name.strip()[:120],
        mobile=mobile,
        branch=branch,
        program=program,
        interest=(interest or "")[:200],
        language=language if language in ("en", "ar") else "ar",
        source=source,
        campaign=campaign,
        referrer=referrer,
        trial_request=trial_request,
        chat=chat,
        stage=Lead.Stage.CONTACTED if staff else Lead.Stage.NEW,
        owner=user if staff else None,
        next_action="Book a trial" if staff else "Call or WhatsApp",
        next_due=now + datetime.timedelta(hours=FOLLOW_UP_HOURS if staff else FIRST_CONTACT_HOURS),
        created_by=user,
        updated_by=user,
    )
    _log(user, f"Enquiry via {label}. {note}".strip(), lead=lead)
    record_event(action="lead_created", instance=lead, branch_id=branch.pk, changes={"source": source})
    if not staff:
        text = f"New lead at {branch.name}: {lead.name} ({label}) — contact within {FIRST_CONTACT_HOURS} hours."
        transaction.on_commit(lambda: notify_perm("leads.manage", text, branch.pk))
    return lead


def intake_from_trial_request(trial_request, session=None) -> Lead:
    """The website form (P5-7: campaign and referral codes remembered from the visitor's first page)."""
    session = session or {}
    program = None
    if trial_request.program_id:
        program = trial_request.program.system_programs.filter(branch=trial_request.branch).first()
    interest = trial_request.program.title if trial_request.program_id else "Not sure — help choosing"
    return intake(
        name=trial_request.name,
        mobile=trial_request.mobile,
        branch=trial_request.branch,
        source=Lead.Source.SAQR if trial_request.source == "saqr" else Lead.Source.WEBSITE,
        program=program,
        interest=interest,
        language=trial_request.language,
        campaign=campaign_for(session.get("campaign")),
        referrer=referrer_for_code(session.get("ref")),
        trial_request=trial_request,
    )


# ---------------------------------------------------------------------------
# Working a lead (P5-2)
# ---------------------------------------------------------------------------
def _lock(lead):
    return Lead.objects.select_for_update().get(pk=lead.pk)


def _check_next(lead, next_action, next_due):
    if lead.is_open:
        if not (next_action or "").strip() or next_due is None:
            raise ValidationError("Set the next action and when it is due.")


@transaction.atomic
def log_contact(lead, user, kind, text, next_action, next_due) -> Lead:
    lead = _lock(lead)
    _need(user, "leads.manage", lead.branch_id, "You cannot work leads for this branch.")
    if kind not in Activity.CONTACT and kind != Activity.Kind.NOTE:
        raise ValidationError("Choose call, WhatsApp, visit or note.")
    if not (text or "").strip():
        raise ValidationError("Write what was said.")
    if kind in Activity.CONTACT and lead.owner_id is None:
        lead.owner = user  # the first person to contact the lead owns it (Playbook tie-breaker)
        _log(user, f"Owner: {user.full_name} (first contact).", Activity.Kind.OWNER, lead=lead)
    if kind in Activity.CONTACT and lead.stage == Lead.Stage.NEW:
        lead.stage = Lead.Stage.CONTACTED
    _check_next(lead, next_action, next_due)
    lead.next_action, lead.next_due, lead.updated_by = (next_action or "").strip()[:150], next_due, user
    lead.save()
    _log(user, text.strip(), kind, lead=lead)
    return lead


@transaction.atomic
def reassign(lead, user, new_owner, reason) -> Lead:
    lead = _lock(lead)
    _need(user, "marketing.approve", lead.branch_id, "Only the OM or the Marketing Lead reassigns a lead.")
    if not (reason or "").strip():
        raise ValidationError("Give the reason for reassigning.")
    if not has_perm(new_owner, "leads.manage", lead.branch_id):
        raise ValidationError("The new owner must be able to work leads at this branch.")
    old = lead.owner.full_name if lead.owner else "nobody"
    lead.owner, lead.updated_by = new_owner, user
    lead.save()
    _log(user, f"Owner: {old} → {new_owner.full_name}. {reason.strip()}", Activity.Kind.OWNER, lead=lead)
    if new_owner.mobile:
        transaction.on_commit(
            lambda: send_message(new_owner.mobile, f"Lead {lead.name} is now yours.", category="staff")
        )
    return lead


def _brief(lead, session) -> str:
    when = f"{session.date:%a %d/%m} {session.start:%H:%M}"
    parts = [f"Trial in your class {session.title_en} ({when}): {lead.name}"]
    if lead.interest:
        parts.append(lead.interest)
    first_note = lead.activities.filter(kind__in=Activity.CONTACT).order_by("at").first()
    if first_note is not None:
        parts.append(f"Notes: {first_note.text[:200]}")
    parts.append("Please give feedback on the class list after the class.")
    return " · ".join(parts)


@transaction.atomic
def book_trial(lead, session, user):
    """P5-4: name and phone only; the instructor gets a trial brief."""
    from apps.classes import services as classes

    lead = _lock(lead)
    _need(user, "leads.manage", lead.branch_id, "You cannot work leads for this branch.")
    if not lead.is_open:
        raise ValidationError("This lead is closed.")
    if session.branch_id != lead.branch_id:
        raise ValidationError("Book a class at the lead's branch (or move the lead first).")
    booking = classes.book(
        session,
        user,
        guest_name=lead.name,
        guest_mobile=lead.mobile,
        trial_request=lead.trial_request,
        source="trial",
        is_trial=True,
    )
    if lead.owner_id is None:
        lead.owner = user
        _log(user, f"Owner: {user.full_name} (booked the trial).", Activity.Kind.OWNER, lead=lead)
    lead.trial_booking, lead.stage = booking, Lead.Stage.TRIAL_BOOKED
    lead.next_action = "Follow up after the trial"
    lead.next_due = session.ends_at + datetime.timedelta(hours=FOLLOW_UP_HOURS)
    lead.updated_by = user
    lead.save()
    _log(user, f"Trial booked: {session}", Activity.Kind.BOOKING, lead=lead)
    if lead.trial_request_id:
        type(lead.trial_request).objects.filter(pk=lead.trial_request_id).update(status="booked")
    from apps.notifications.services import render

    title = session.title_ar if lead.language == "ar" and session.title_ar else session.title_en
    confirm = render(
        "trial_confirmed",
        lead.language,
        name=lead.name.split()[0],
        branch=lead.branch.name_ar if lead.language == "ar" else lead.branch.name,
        when=f"{session.date:%d/%m} {session.start:%H:%M}",
        cls=title,
    )
    transaction.on_commit(lambda: send_message(lead.mobile, confirm, kind="trial_confirmed"))
    text = _brief(lead, session)
    mobiles = [u.mobile for u in session.instructors.all() if u.mobile]
    transaction.on_commit(lambda: [send_message(m, text, category="staff", kind="trial_brief") for m in mobiles])
    return booking


def trial_attended(booking):
    """Called when a trial guest is checked in."""
    for lead in Lead.objects.filter(trial_booking=booking, stage=Lead.Stage.TRIAL_BOOKED):
        lead.stage = Lead.Stage.TRIAL_DONE
        lead.save(update_fields=["stage", "updated_at"])
        _log(None, "Came to the trial class.", lead=lead)


@transaction.atomic
def record_feedback(booking, user, score, note="") -> Lead | None:
    """The instructor's view of the trial (on the class list)."""
    session = booking.session
    if not (has_perm(user, "classes.checkin", session.branch_id) or has_perm(user, "leads.manage", session.branch_id)):
        raise PermissionDenied("Only the class instructor or the desk records trial feedback.")
    score = int(score)
    if not 1 <= score <= 5:
        raise ValidationError("Rate the trial from 1 to 5.")
    lead = Lead.objects.select_for_update().filter(trial_booking=booking).first()
    if lead is None:
        return None
    lead.trial_score, lead.trial_feedback, lead.updated_by = score, (note or "").strip()[:500], user
    if lead.stage == Lead.Stage.TRIAL_BOOKED:
        lead.stage = Lead.Stage.TRIAL_DONE
    lead.save()
    _log(user, f"Trial feedback {score}/5. {note}".strip(), Activity.Kind.FEEDBACK, lead=lead)
    if score >= 4:
        transaction.on_commit(lambda: request_review(lead.mobile, lead.branch, ReviewRequest.Reason.TRIAL, lead=lead))
    return lead


@transaction.atomic
def mark_lost(lead, user, reason, note="") -> Lead:
    lead = _lock(lead)
    _need(user, "leads.manage", lead.branch_id, "You cannot work leads for this branch.")
    if reason not in Lead.LostReason.values:
        raise ValidationError("Choose why the lead was lost.")
    if not lead.is_open:
        raise ValidationError("This lead is already closed.")
    lead.stage, lead.lost_reason, lead.closed_at = Lead.Stage.LOST, reason, timezone.now()
    lead.next_action, lead.next_due, lead.updated_by = "", None, user
    lead.save()
    _log(user, f"Lost: {lead.get_lost_reason_display()}. {note}".strip(), Activity.Kind.STAGE, lead=lead)
    return lead


@transaction.atomic
def reopen(lead, user, next_action, next_due) -> Lead:
    lead = _lock(lead)
    _need(user, "leads.manage", lead.branch_id, "You cannot work leads for this branch.")
    if lead.stage != Lead.Stage.LOST:
        raise ValidationError("Only a lost lead can be reopened.")
    lead.stage, lead.lost_reason, lead.closed_at = Lead.Stage.CONTACTED, "", None
    _check_next(lead, next_action, next_due)
    lead.next_action, lead.next_due, lead.updated_by = next_action.strip()[:150], next_due, user
    lead.save()
    _log(user, "Reopened.", Activity.Kind.STAGE, lead=lead)
    return lead


def _family_mobiles(member):
    mobiles = {member.mobile} if member.mobile else set()
    mobiles |= set(GuardianLink.objects.filter(member=member).values_list("guardian__mobile", flat=True))
    return {m for m in mobiles if m}


def link_new_member(member, sale) -> list[Lead]:
    """P5-5: a first membership sold to this member (or their family) converts the open lead."""
    mobiles = _family_mobiles(member)
    if not mobiles:
        return []
    since = timezone.now() - datetime.timedelta(days=MATCH_DAYS)
    leads = list(
        Lead.objects.select_for_update().filter(mobile__in=mobiles, stage__in=Lead.OPEN, created_at__gte=since)
    )
    for lead in leads:
        lead.stage, lead.member, lead.joined_at, lead.closed_at = (
            Lead.Stage.JOINED,
            member,
            timezone.now(),
            timezone.now(),
        )
        lead.next_action, lead.next_due = "", None
        lead.save()
        _log(sale.created_by, f"Joined — first membership {sale.reference}.", Activity.Kind.STAGE, lead=lead)
    return leads


def referrer_for(member):
    """The member who referred this new member (through their lead), for the Phase 1 referral reward."""
    lead = (
        Lead.objects.filter(mobile__in=_family_mobiles(member), referrer__isnull=False)
        .exclude(referrer=member)
        .order_by("-created_at")
        .first()
    )
    return lead.referrer if lead else None


# ---------------------------------------------------------------------------
# Group sales (P5-6)
# ---------------------------------------------------------------------------
@transaction.atomic
def create_deal(user, **data) -> GroupDeal:
    branch = data["branch"]
    _need(user, "leads.manage", branch.pk, "You cannot record group sales for this branch.")
    for field in ("organisation", "contact_name"):
        if not (data.get(field) or "").strip():
            raise ValidationError("Enter the organisation and the contact person.")
    data["mobile"] = normalize_kuwait_mobile(data.get("mobile", ""))
    deal = GroupDeal.objects.create(owner=user, created_by=user, updated_by=user, **data)
    _log(user, "Group enquiry recorded.", deal=deal)
    return deal


@transaction.atomic
def move_deal(deal, user, stage, note="", **fields) -> GroupDeal:
    deal = GroupDeal.objects.select_for_update().get(pk=deal.pk)
    _need(user, "leads.manage", deal.branch_id, "You cannot work group sales for this branch.")
    if deal.stage in (GroupDeal.Stage.DELIVERY, GroupDeal.Stage.LOST):
        raise ValidationError("This deal is closed.")
    if stage == GroupDeal.Stage.LOST:
        if not note.strip():
            raise ValidationError("Say why the deal was lost.")
        deal.lost_reason = note.strip()[:200]
    elif stage == GroupDeal.Stage.DELIVERY:
        if deal.confirmed_at is None:
            raise ValidationError("Operations must confirm the delivery first (receiving owner).")
    elif stage not in GroupDeal.ORDER:
        raise ValidationError("Unknown stage.")
    if stage == GroupDeal.Stage.PAID and not deal.value and not fields.get("value"):
        raise ValidationError("Enter the agreed value before marking it paid.")
    for key in ("value", "participants", "start_date", "details", "next_action", "next_due"):
        if fields.get(key) not in (None, ""):
            setattr(deal, key, fields[key])
    old = deal.get_stage_display()
    deal.stage, deal.updated_by = stage, user
    deal.save()
    _log(user, f"{old} → {deal.get_stage_display()}. {note}".strip(), Activity.Kind.STAGE, deal=deal)
    if stage == GroupDeal.Stage.PAID:
        text = f"Group deal {deal.organisation} is paid — confirm who in Operations receives it."
        transaction.on_commit(lambda: notify_perm("ops.manage", text, deal.branch_id, exclude=user))
    if stage == GroupDeal.Stage.DELIVERY:
        text = (
            f"Group delivery: {deal.organisation} ({deal.participants} people, from {deal.start_date}). {deal.details}"
        )
        transaction.on_commit(lambda: notify_perm("training.manage", text[:600], deal.branch_id))
    return deal


@transaction.atomic
def confirm_delivery(deal, user) -> GroupDeal:
    """The named receiving owner in Operations confirms before Training delivers (Playbook item 1)."""
    deal = GroupDeal.objects.select_for_update().get(pk=deal.pk)
    _need(user, "ops.manage", deal.branch_id, "Only Operations confirms who receives a group delivery.")
    if deal.stage != GroupDeal.Stage.PAID:
        raise ValidationError("Confirm once the registrations are paid.")
    deal.receiving_owner, deal.confirmed_at, deal.updated_by = user, timezone.now(), user
    deal.save()
    _log(user, f"Receiving owner: {user.full_name}.", Activity.Kind.OWNER, deal=deal)
    return deal


# ---------------------------------------------------------------------------
# Reports (M3 conversion, M13 campaigns and funnel)
# ---------------------------------------------------------------------------
STAGES_REACHED = {
    "contacted": ["contacted", "trial_booked", "trial_done", "joined"],
    "trial_booked": ["trial_booked", "trial_done", "joined"],
    "trial_done": ["trial_done", "joined"],
    "joined": ["joined"],
}


def funnel(qs) -> dict:
    """How far the leads in `qs` got: counts reaching each stage and the conversion rate."""
    total = qs.count()
    stages = Counter(qs.values_list("stage", flat=True))
    reached = {k: sum(stages.get(s, 0) for s in v) for k, v in STAGES_REACHED.items()}
    booked_ids = qs.filter(trial_booking__isnull=False).values_list("pk", flat=True)
    reached["trial_booked"] = max(reached["trial_booked"], len(booked_ids))
    return {
        "total": total,
        **reached,
        "lost": stages.get("lost", 0),
        "open": sum(stages.get(s, 0) for s in Lead.OPEN),
        "rate": round(reached["joined"] * 100 / total, 1) if total else None,
    }


def breakdown(qs, field) -> list[dict]:
    keys = qs.order_by().values_list(field, flat=True).distinct()
    rows = []
    for key in keys:
        f = funnel(qs.filter(**{field: key}))
        rows.append({"key": key, **f})
    return sorted(rows, key=lambda r: -r["total"])


def campaign_stats(campaign) -> dict:
    leads = campaign.leads.all()
    n, joined = leads.count(), leads.filter(stage=Lead.Stage.JOINED).count()
    return {
        "leads": n,
        "joined": joined,
        "cost_per_lead": (campaign.spend / n).quantize(D("0.001")) if n else None,
        "cost_per_join": (campaign.spend / joined).quantize(D("0.001")) if joined else None,
    }


def overdue_leads(user):
    return Lead.objects.filter(owner=user, stage__in=Lead.OPEN, next_due__lt=timezone.now())


# ---------------------------------------------------------------------------
# Referrals (P5-8) and reviews (P5-9)
# ---------------------------------------------------------------------------
def referral_code_for(member) -> ReferralCode:
    code, _ = ReferralCode.objects.get_or_create(member=member)
    return code


def request_review(mobile, branch, reason, member=None, lead=None) -> ReviewRequest | None:
    url = getattr(branch, "google_review_url", "")
    if not url or not mobile:
        return None
    recent = timezone.now() - datetime.timedelta(days=REVIEW_EVERY_DAYS)
    if ReviewRequest.objects.filter(mobile=mobile, sent_at__gte=recent).exists():
        return None
    lang = contact_language(member) if member else (lead.language if lead else "ar")
    if lang == "ar":
        text = f"شكراً لتدريبكم معنا في {branch.name_ar}! يسعدنا تقييمكم على جوجل: {url}"
    else:
        text = f"Thank you for training with us at {branch.name}! We'd love your Google review: {url}"
    send_message(mobile, text, category="service", kind="review_request", member=member)
    return ReviewRequest.objects.create(mobile=mobile, branch=branch, reason=reason, member=member, lead=lead)


def on_promotion(promotion_id):
    from apps.training.models import Promotion

    promotion = Promotion.objects.select_related("member", "branch").get(pk=promotion_id)
    if promotion.kind == Promotion.Kind.PLACEMENT:
        return None
    member = promotion.member
    return request_review(contact_mobile(member), promotion.branch, ReviewRequest.Reason.PROMOTION, member=member)


# ---------------------------------------------------------------------------
# WhatsApp broadcasts with opt-in (P5-10)
# ---------------------------------------------------------------------------
def opted_in(member) -> bool:
    latest = member.messaging_opt_ins.first()
    return bool(latest and latest.opted_in)


@transaction.atomic
def set_opt_in(member, user, yes: bool, source="desk") -> MessagingOptIn:
    if user is not None and not (
        has_perm(user, "members.update", member.branch_id) or has_perm(user, "marketing.manage")
    ):
        raise PermissionDenied("You cannot change this member's messaging choice.")
    return MessagingOptIn.objects.create(member=member, opted_in=bool(yes), source=source, recorded_by=user)


def audience(broadcast) -> list[tuple[str, str, Member]]:
    """(mobile, language, member) for every opted-in family matching the filters, one message per mobile."""
    from apps.classes.models import Enrollment

    members = Member.objects.filter(is_active=True).prefetch_related("messaging_opt_ins", "guardian_links__guardian")
    if broadcast.branch_id:
        members = members.filter(branch_id=broadcast.branch_id)
    if broadcast.program_id:
        today = timezone.localdate()
        ids = Enrollment.objects.filter(slot__program_id=broadcast.program_id).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        )
        members = members.filter(pk__in=ids.values_list("member_id", flat=True))
    seen, out = set(), []
    for m in members:
        if broadcast.ages == Broadcast.Ages.KIDS and not m.is_minor:
            continue
        if broadcast.ages == Broadcast.Ages.ADULTS and m.is_minor:
            continue
        if not opted_in(m):
            continue
        mobile = contact_mobile(m)
        if mobile and mobile not in seen:
            seen.add(mobile)
            out.append((mobile, contact_language(m), m))
    return out


@transaction.atomic
def save_broadcast(user, broadcast=None, **data) -> Broadcast:
    if not has_perm(user, "marketing.manage"):
        raise PermissionDenied("Only Marketing drafts broadcasts.")
    b = broadcast or Broadcast(created_by=user)
    if b.pk and b.status == Broadcast.Status.SENT:
        raise ValidationError("A sent broadcast can't be changed.")
    for key, value in data.items():
        setattr(b, key, value)
    if not b.title.strip() or not b.message_en.strip() or not b.message_ar.strip():
        raise ValidationError("Write the title and the message in both English and Arabic.")
    b.status, b.updated_by = Broadcast.Status.DRAFT, user
    b.save()
    return b


@transaction.atomic
def send_broadcast(broadcast, user) -> Broadcast:
    b = Broadcast.objects.select_for_update().get(pk=broadcast.pk)
    _need(user, "marketing.approve", b.branch_id, "Only the Marketing Lead approves and sends broadcasts.")
    if b.created_by_id == user.pk:
        raise PermissionDenied("Someone else must approve a broadcast you drafted.")
    if b.status != Broadcast.Status.DRAFT:
        raise ValidationError("Only a draft can be sent.")
    people = audience(b)
    if not people:
        raise ValidationError("Nobody who opted in matches this audience.")
    b.status, b.decided_by, b.sent_at, b.recipients = Broadcast.Status.SENT, user, timezone.now(), len(people)
    b.updated_by = user
    b.save()
    record_event(action="broadcast_sent", instance=b, changes={"recipients": len(people)})
    messages = [(mobile, b.message_ar if lang == "ar" else b.message_en) for mobile, lang, _ in people]
    transaction.on_commit(lambda: [send_message(m, t, category="marketing", kind="broadcast") for m, t in messages])
    return b


@transaction.atomic
def return_broadcast(broadcast, user, note) -> Broadcast:
    b = Broadcast.objects.select_for_update().get(pk=broadcast.pk)
    _need(user, "marketing.approve", b.branch_id, "Only the Marketing Lead approves broadcasts.")
    if not note.strip():
        raise ValidationError("Say what to change.")
    b.status, b.decided_by, b.decision_note, b.updated_by = Broadcast.Status.REJECTED, user, note.strip()[:255], user
    b.save()
    return b


# ---------------------------------------------------------------------------
# Consent withdrawn → photos back to review (P5-10)
# ---------------------------------------------------------------------------
def on_media_consent(sender, instance, created, **kwargs):
    if not created or instance.website_marketing:
        return
    from apps.website.models import AlbumPhoto

    previous = instance.member.media_consents.exclude(pk=instance.pk).first()
    if previous is None or not previous.website_marketing:
        return
    photos = AlbumPhoto.objects.filter(tagged_members=instance.member, reviewed=True)
    n = photos.update(reviewed=False)
    if n:
        text = f"Media consent withdrawn for a member: {n} gallery photo(s) hidden and waiting for review."
        transaction.on_commit(lambda: notify_perm("marketing.manage", text))
