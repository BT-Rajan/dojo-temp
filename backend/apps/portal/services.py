"""
The member and parent portal (M15, decisions P6-1 to P6-6). Every function takes the signed-in user and reaches
members only through that user's own guardian or member profile.
"""

import datetime

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.audit.services import record_event
from apps.classes import services as classes
from apps.classes.models import Attendance, Booking, ClassSession
from apps.core.messaging import send_message
from apps.members.models import MediaConsent, Member, RulesAgreement
from apps.members.services import contact_language, contact_mobile, display_name
from apps.notifications.services import render
from apps.rbac.services import has_perm
from apps.sales import services as sales
from apps.sales.models import AccountRequest, Membership, Sale

from .models import RenewalPayment

BOOK_AHEAD_DAYS = 7  # P6-2


def family(user):
    if not user.is_authenticated or not has_perm(user, "portal.own_family"):
        return Member.objects.none()
    members = Member.objects.none()
    guardian = getattr(user, "guardian_profile", None)
    if guardian is not None:
        members = guardian.members.all()
    own = getattr(user, "member_profile", None)
    if own is not None:
        members = members | Member.objects.filter(pk=own.pk)
    return members.filter(is_active=True).select_related("branch").distinct()


def member_for(user, pk) -> Member:
    member = family(user).filter(pk=pk).first()
    if member is None:
        raise Http404
    return member


def family_mobile(user):
    guardian = getattr(user, "guardian_profile", None)
    if guardian is not None:
        return guardian.mobile
    own = getattr(user, "member_profile", None)
    return own.mobile if own else ""


# ---------------------------------------------------------------------------
# Classes (P6-2)
# ---------------------------------------------------------------------------
def upcoming(member, days=BOOK_AHEAD_DAYS):
    """Regular classes and bookings in the next days, and classes the membership lets them book."""
    today = timezone.localdate()
    end = today + datetime.timedelta(days=days)
    now = timezone.localtime()
    regular_slots = set(
        member.enrollments.filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).values_list("slot_id", flat=True)
    )
    booked = {
        b.session_id: b
        for b in Booking.objects.filter(member=member, session__date__range=(today, end)).exclude(status="cancelled")
    }
    rows = []
    sessions = (
        ClassSession.objects.filter(branch=member.branch, date__range=(today, end), status="scheduled")
        .select_related("program")
        .order_by("date", "start")
    )
    for s in sessions:
        if s.date == today and s.start <= now.time():
            continue
        if s.kind not in ("class", "seminar"):
            continue
        booking = booked.get(s.pk)
        regular = s.slot_id in regular_slots
        membership, warning = sales.membership_for_class(member, s.program_id, s.date)
        can_book = not regular and booking is None and membership is not None and warning == ""
        if regular or booking or can_book:
            rows.append({"s": s, "regular": regular, "booking": booking, "can_book": can_book})
    return rows


@transaction.atomic
def book(user, member, session) -> Booking:
    member = member_for(user, member.pk)
    today = timezone.localdate()
    if session.branch_id != member.branch_id:
        raise ValidationError("Book classes at your own branch.")
    if not today <= session.date <= today + datetime.timedelta(days=BOOK_AHEAD_DAYS):
        raise ValidationError(f"Classes can be booked up to {BOOK_AHEAD_DAYS} days ahead.")
    membership, warning = sales.membership_for_class(member, session.program_id, session.date)
    if membership is None or warning:
        raise ValidationError("The membership doesn't cover this class — please contact the branch.")
    booking = classes.book(session, user, member=member, source=Booking.Source.PORTAL, by_family=True)
    lang = contact_language(member)
    key = "waitlisted" if booking.status == Booking.Status.WAITLISTED else "booking_confirmed"
    text = render(
        key,
        lang,
        member=display_name(member, lang),
        cls=session.title_ar if lang == "ar" and session.title_ar else session.title_en,
        when=f"{session.date:%d/%m} {session.start:%H:%M}",
    )
    mobile = contact_mobile(member)
    if mobile:
        transaction.on_commit(lambda: send_message(mobile, text, kind=key, member=member))
    return booking


@transaction.atomic
def cancel(user, booking) -> Booking:
    if booking.member_id is None:
        raise Http404
    member_for(user, booking.member_id)
    return classes.cancel_booking(booking, user, by_family=True)


def attendance(member, limit=20):
    return Attendance.objects.filter(member=member).select_related("session").order_by("-checked_in_at")[:limit]


# ---------------------------------------------------------------------------
# Money (P6-3, P6-4)
# ---------------------------------------------------------------------------
def current_membership(member):
    return (
        Membership.objects.filter(member=member, pricing_option__kind="membership")
        .exclude(status="cancelled")
        .select_related("pricing_option", "branch")
        .order_by("-end_date")
        .first()
    )


def renewal_option(member):
    m = current_membership(member)
    if m is None:
        return None
    option = m.pricing_option
    if not option.is_active or option.approval != "approved" or option.branch_id != member.branch_id:
        return None
    return option


@transaction.atomic
def start_renewal(user, member, method="knet") -> RenewalPayment:
    member = member_for(user, member.pk)
    option = renewal_option(member)
    if option is None:
        raise ValidationError("This membership can't be renewed online — please contact the branch.")
    if method not in ("knet", "card"):
        raise ValidationError("Choose KNET or card.")
    return RenewalPayment.objects.create(
        member=member, pricing_option=option, amount=option.price, method=method, user=user
    )


@transaction.atomic
def complete_renewal(payment: RenewalPayment, paid: bool, gateway_reference: str) -> RenewalPayment:
    payment = (
        RenewalPayment.objects.select_for_update().select_related("member__branch", "pricing_option").get(pk=payment.pk)
    )
    if payment.status != RenewalPayment.Status.PENDING:
        return payment
    if not paid:
        payment.status = RenewalPayment.Status.FAILED
        payment.save(update_fields=["status"])
        return payment
    member = payment.member
    sale = sales.sell(
        branch=member.branch,
        user=payment.user,
        cart=sales.Cart(
            items=[sales.Item(pricing_option=payment.pricing_option)],
            payments=[sales.Pay(payment.method, payment.amount, gateway_reference or payment.reference)],
        ),
        member=member,
        receipt_channels=("whatsapp",),
        note=f"Online renewal {payment.reference}",
        online=True,
    )
    payment.status, payment.sale, payment.paid_at = RenewalPayment.Status.PAID, sale, timezone.now()
    payment.gateway_reference = gateway_reference[:80]
    payment.save(update_fields=["status", "sale", "paid_at", "gateway_reference"])
    record_event(action="online_renewal", instance=sale, branch_id=member.branch_id)
    new = Membership.objects.filter(sale_line__sale=sale).first()
    lang = contact_language(member)
    text = render(
        "renewal_paid",
        lang,
        member=display_name(member, lang),
        end=f"{new.end_date:%d/%m/%Y}" if new else "",
        receipt=sale.reference,
    )
    mobile = contact_mobile(member)
    if mobile:
        transaction.on_commit(lambda: send_message(mobile, text, kind="renewal_paid", member=member))
    return payment


def receipts(member, limit=20):
    return Sale.objects.filter(member=member).prefetch_related("lines", "payments").order_by("-created_at")[:limit]


@transaction.atomic
def request_freeze(user, member, start, weeks, reason) -> AccountRequest:
    member = member_for(user, member.pk)
    m = current_membership(member)
    if m is None:
        raise ValidationError("There is no membership to freeze.")
    return sales.request_change(
        kind=AccountRequest.Kind.FREEZE,
        user=user,
        reason=f"(Requested in the portal) {reason}",
        membership=m,
        freeze_start=start,
        freeze_weeks=weeks,
        by_family=True,
    )


# ---------------------------------------------------------------------------
# Details, consent, rules, messages (P6-6, P6-7)
# ---------------------------------------------------------------------------
def signer_name(user):
    guardian = getattr(user, "guardian_profile", None)
    if guardian is not None:
        return guardian.full_name
    own = getattr(user, "member_profile", None)
    return f"{own.first_name} {own.last_name}" if own else user.full_name


@transaction.atomic
def set_consent(user, member, internal: bool, social: bool, website: bool) -> MediaConsent:
    member = member_for(user, member.pk)
    consent = MediaConsent.objects.create(
        member=member,
        internal_records=internal,
        social_media=social,
        website_marketing=website,
        signed_by_name=signer_name(user),
        recorded_by=user,
        notes="Changed by the family in the portal",
    )
    record_event(action="consent_changed_in_portal", instance=consent)
    return consent


@transaction.atomic
def sign_rules(user, member, typed_name, agreed: bool) -> RulesAgreement:
    member = member_for(user, member.pk)
    if not agreed:
        raise ValidationError("Tick that you have read and agree to the academy rules.")
    expected = signer_name(user).strip().lower()
    if typed_name.strip().lower() != expected:
        raise ValidationError("Type your full name exactly as registered to sign.")
    return RulesAgreement.objects.create(
        member=member, signed_by_name=typed_name.strip(), signature=f"typed:{typed_name.strip()}", recorded_by=user
    )


def rules_signed(member) -> bool:
    return member.rules_agreements.filter(rules_version=RulesAgreement.CURRENT_VERSION).exists()


@transaction.atomic
def update_email(user, email):
    from django.core.validators import validate_email

    email = (email or "").strip()
    if email:
        validate_email(email)
    guardian = getattr(user, "guardian_profile", None)
    profile = guardian or getattr(user, "member_profile", None)
    if profile is None:
        raise PermissionDenied
    profile.email = email
    profile.save(update_fields=["email"])
    return profile


def set_messages(user, service_on: bool, broadcasts_on: bool):
    from apps.leads.services import set_opt_in
    from apps.notifications.services import set_service_messages

    mobile = family_mobile(user)
    if mobile:
        set_service_messages(mobile, service_on, user)
    for member in family(user):
        set_opt_in(member, None, broadcasts_on, source="portal")


def recent_messages(user, limit=15):
    from apps.notifications.models import MessageLog

    mobile = family_mobile(user)
    if not mobile:
        return []
    return MessageLog.objects.filter(to=mobile, status="sent").exclude(kind="sign_in_code")[:limit]
