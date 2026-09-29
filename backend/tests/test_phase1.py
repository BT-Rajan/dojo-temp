"""Phase 1 rules: prices, timetable, bookings, check-in, class changes, sales, requests, cash-up, renewals."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.classes import services as cls
from apps.classes.models import Attendance, Booking, ClassChange, ClassSession, ClassSlot, Enrollment
from apps.core.messaging import OUTBOX_KEY
from apps.members.models import Guardian, GuardianLink, Member
from apps.organization import services as org
from apps.organization.models import PricingOption, Program
from apps.renewals import services as ren
from apps.renewals.models import FollowUp, InstructorHandoff
from apps.sales import services as sal
from apps.sales.models import CashUp, Discount, Membership, ReferralCredit, SaleLine
from apps.shop.models import BranchStock, Product, ProductVariant

TODAY = timezone.localdate()
D = Decimal


@pytest.fixture
def setup(branches, make_user):
    for b in branches.values():
        b.open_days = [0, 1, 2, 3, 4, 5] if b.code == "BED" else [0, 1, 2, 3, 4]
        b.save()
    prm = branches["PRM"]
    program = Program.objects.create(branch=prm, name="Elite Program 5-7", name_ar="برنامج")
    monthly = PricingOption.objects.create(
        branch=prm, name="Monthly", kind="membership", price=D("85"), duration_days=30, approval="approved"
    )
    package = PricingOption.objects.create(
        branch=prm,
        name="10x4",
        kind="membership",
        price=D("60"),
        total_sessions=2,
        package_weeks=4,
        approval="approved",
    )
    trial = PricingOption.objects.create(
        branch=prm, name="Trial", kind="trial", price=D("10"), duration_days=1, approval="approved"
    )
    users = {
        "om": make_user("operations_manager"),
        "ceo": make_user("ceo"),
        "desk": make_user("branch_admin", branch=prm),
        "desk2": make_user("branch_admin", branch=prm),
        "coach": make_user("instructor"),
        "tl": make_user("training_lead"),
        "bed_desk": make_user("branch_admin", branch=branches["BED"]),
    }
    return {
        "prm": prm,
        "bed": branches["BED"],
        "program": program,
        "monthly": monthly,
        "package": package,
        "trial": trial,
        **users,
    }


def member(branch, first="Fahad", dob=datetime.date(2016, 5, 10)):
    return Member.objects.create(
        branch=branch, first_name=first, last_name="Test", date_of_birth=dob, gender="male", mobile=""
    )


def sell_option(s, m, option, user=None, **kw):
    cart = sal.Cart(
        items=[sal.Item(pricing_option=option, **kw)], payments=[sal.Pay("cash", option.price)] if option.price else []
    )
    return sal.sell(branch=s["prm"], user=user or s["desk"], cart=cart, member=m)


def slot_today(s, capacity=2, start=None, end=None):
    now = timezone.localtime()
    start = start or (now + datetime.timedelta(minutes=30)).time().replace(second=0, microsecond=0)
    end = end or (now + datetime.timedelta(minutes=90)).time().replace(second=0, microsecond=0)
    if end <= start:  # near midnight: keep the test simple
        start, end = datetime.time(22, 0), datetime.time(23, 30)
    s["prm"].open_days = list(range(7))
    s["prm"].save()
    slot = ClassSlot.objects.create(
        branch=s["prm"],
        program=s["program"],
        title_en="Kajukenbo",
        ages_en="Kids",
        age_group="kids",
        weekday=cls.kuwait_weekday(TODAY),
        start=start,
        end=end,
        capacity=capacity,
        valid_from=TODAY,
    )
    slot.instructors.add(s["coach"])
    cls.generate_sessions(days=1)
    return slot, ClassSession.objects.get(slot=slot, date=TODAY)


# --------------------------------------------------------------------------- M1
def test_price_change_needs_someone_elses_approval_then_goes_live(setup):
    s = setup
    change = org.request_price_change(s["monthly"], D("90"), TODAY, "New season", s["om"])
    with pytest.raises(PermissionDenied):
        org.decide_price_change(change, True, s["om"])  # own request
    with pytest.raises(PermissionDenied):
        org.decide_price_change(change, True, s["desk"])  # not an approver
    s["monthly"].refresh_from_db()
    assert s["monthly"].price == D("85")
    org.decide_price_change(change, True, s["ceo"])
    s["monthly"].refresh_from_db()
    assert s["monthly"].price == D("90")


def test_new_pricing_option_is_not_sellable_until_approved(setup):
    s = setup
    option = PricingOption.objects.create(
        branch=s["prm"], name="3 months", kind="membership", price=D("230"), duration_days=90, created_by=s["desk"]
    )
    m = member(s["prm"])
    with pytest.raises(ValidationError):
        sell_option(s, m, option)
    org.decide_pricing_option(option, True, s["om"])
    assert sell_option(s, m, option).total == D("230")


def test_price_cannot_be_edited_directly_through_the_api(setup, client_for):
    response = client_for(setup["om"]).patch(
        f"/api/v1/pricing-options/{setup['monthly'].pk}/",
        {"price": "1.000", "version": setup["monthly"].version},
        format="json",
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- M4
def test_sessions_follow_the_timetable_and_closed_days(setup):
    s = setup
    for weekday in range(7):
        ClassSlot.objects.create(
            branch=s["prm"],
            program=s["program"],
            title_en="K",
            ages_en="Kids",
            age_group="kids",
            weekday=weekday,
            start=datetime.time(16, 30),
            end=datetime.time(17, 30),
            valid_from=TODAY,
        )
    first = cls.generate_sessions(days=7)
    assert first == 5  # Promenade is closed Thursday and Friday
    assert cls.generate_sessions(days=7) == 0  # safe to run again


def test_booking_waitlist_and_promotion(setup):
    s = setup
    _, session = slot_today(s, capacity=1)
    a, b = member(s["prm"], "Ali"), member(s["prm"], "Omar")
    first = cls.book(session, s["desk"], member=a)
    second = cls.book(session, s["desk"], member=b)
    assert (first.status, second.status) == (Booking.Status.BOOKED, Booking.Status.WAITLISTED)
    with pytest.raises(ValidationError):
        cls.book(session, s["desk"], member=a)  # no double booking
    cancelled = cls.cancel_booking(first, s["desk"])
    assert cancelled.late_cancellation  # less than 2 hours before: recorded, no penalty
    second.refresh_from_db()
    assert second.status == Booking.Status.BOOKED


def test_regulars_take_places_and_trial_guests_book_with_name_and_phone(setup):
    s = setup
    slot, session = slot_today(s, capacity=1)
    Enrollment.objects.create(member=member(s["prm"], "Regular"), slot=slot)
    guest = cls.book(session, s["desk"], guest_name="Sara", guest_mobile="55512345")
    assert guest.is_trial and guest.status == Booking.Status.WAITLISTED and guest.guest_mobile == "+96555512345"


def test_check_in_warns_but_allows_and_uses_package_sessions(setup):
    s = setup
    _, session = slot_today(s)
    m = member(s["prm"])
    visit, created, warning = cls.check_in(m, session, s["desk"])
    assert created and warning == "no_membership" and visit.walk_in
    again = cls.check_in(m, session, s["coach"], Attendance.Method.COACH)
    assert again[1] is False  # the coach and the desk don't double-count

    m2 = member(s["prm"], "Omar")
    sell_option(s, m2, s["package"])
    cls.check_in(m2, session, s["desk"], Attendance.Method.QR)
    membership = Membership.objects.get(member=m2)
    assert membership.sessions_used == 1


def test_no_shows_are_recorded(setup):
    s = setup
    _, session = slot_today(s)
    booking = cls.book(session, s["desk"], member=member(s["prm"]))
    assert cls.mark_no_shows(now=session.ends_at + datetime.timedelta(minutes=1)) == 1
    booking.refresh_from_db()
    assert booking.status == Booking.Status.NO_SHOW


def test_class_change_is_approved_by_someone_else_and_members_are_told(setup, settings):
    s = setup
    slot, session = slot_today(s)
    guardian = Guardian.objects.create(full_name="Parent", mobile="+96550001111")
    child = member(s["prm"], "Yousef")
    GuardianLink.objects.create(guardian=guardian, member=child, relationship="father", is_primary=True)
    Enrollment.objects.create(member=child, slot=slot)
    cls.book(session, s["desk"], guest_name="Trial Mum", guest_mobile="55512345")
    change = cls.request_change(session, s["coach"], kind="cancel", reason="Coach unwell")
    assert change.urgent  # less than 2 hours before the class
    with pytest.raises(PermissionDenied):
        cls.decide_change(change, True, s["coach"])
    from django.core.cache import cache

    cache.delete(OUTBOX_KEY)
    change = cls.decide_change(change, True, s["tl"])
    session.refresh_from_db()
    assert session.is_cancelled and change.notified_count == 2 and change.status == ClassChange.Status.APPROVED


# --------------------------------------------------------------------------- M5
def test_receipts_numbered_per_branch_and_categories(setup):
    s = setup
    m = member(s["prm"])
    first = sell_option(s, m, s["monthly"])
    second = sell_option(s, m, s["monthly"])
    assert (first.number, second.number) == (1, 2) and second.reference == "PRM-000002"
    assert first.lines.get().category == SaleLine.Category.NEW
    assert second.lines.get().category == SaleLine.Category.RENEW
    memberships = list(Membership.objects.filter(member=m).order_by("start_date"))
    assert memberships[1].start_date == memberships[0].end_date + datetime.timedelta(days=1)  # early renewal


def test_trial_pass_without_profile_and_payment_rules(setup):
    s = setup
    cart = sal.Cart(items=[sal.Item(pricing_option=s["trial"])], payments=[sal.Pay("knet", D("10"))])
    with pytest.raises(ValidationError):
        sal.sell(branch=s["prm"], user=s["desk"], cart=cart, customer_name="Sara")  # KNET needs a reference
    cart.payments = [sal.Pay("cash", D("5"))]
    with pytest.raises(ValidationError):
        sal.sell(branch=s["prm"], user=s["desk"], cart=cart, customer_name="Sara")  # must pay in full
    cart.payments = [sal.Pay("knet", D("10"), "T123")]
    sale = sal.sell(branch=s["prm"], user=s["desk"], cart=cart, customer_name="Sara", customer_mobile="55512345")
    assert sale.lines.get().category == SaleLine.Category.TRIAL


def test_equipment_only_from_own_branch_stock_and_free_issue(setup):
    s = setup
    product = Product.objects.create(slug="belt", name_en="Belt", category="uniforms", price=D("3"))
    variant = ProductVariant.objects.create(product=product, size="M", stock=0)
    BranchStock.objects.create(variant=variant, branch=s["bed"], quantity=5)
    cart = sal.Cart(items=[sal.Item(variant=variant)], payments=[sal.Pay("cash", D("3"))])
    with pytest.raises(ValidationError):
        sal.sell(branch=s["prm"], user=s["desk"], cart=cart, customer_name="X")  # Bedaya stock, Promenade desk
    BranchStock.objects.create(variant=variant, branch=s["prm"], quantity=1)
    free = sal.Cart(items=[sal.Item(variant=variant, free_issue=True, free_issue_reason="Grading belt")])
    sale = sal.sell(branch=s["prm"], user=s["desk"], cart=free, member=member(s["prm"]))
    assert sale.total == 0 and BranchStock.objects.get(variant=variant, branch=s["prm"]).quantity == 0


def test_family_discount_needs_a_sibling_and_referral_credit(setup):
    s = setup
    family = Discount.objects.create(name="Sibling", kind="family", percent=D("10"))
    Discount.objects.create(name="Referral", kind="referral", amount=D("5"))
    only_child = member(s["prm"])
    cart = sal.Cart(
        items=[sal.Item(pricing_option=s["monthly"], discount=family)], payments=[sal.Pay("cash", D("76.5"))]
    )
    with pytest.raises(ValidationError):
        sal.sell(branch=s["prm"], user=s["desk"], cart=cart, member=only_child)
    guardian = Guardian.objects.create(full_name="Parent", mobile="+96550002222")
    sibling = member(s["prm"], "Sister")
    for kid in (only_child, sibling):
        GuardianLink.objects.create(guardian=guardian, member=kid, relationship="mother")
    assert sal.sell(branch=s["prm"], user=s["desk"], cart=cart, member=only_child).total == D("76.500")

    friend = member(s["prm"], "Friend")
    sal.sell(
        branch=s["prm"],
        user=s["desk"],
        member=friend,
        referred_by=sibling,
        cart=sal.Cart(items=[sal.Item(pricing_option=s["monthly"])], payments=[sal.Pay("cash", D("85"))]),
    )
    assert ReferralCredit.objects.get(referrer=sibling).amount == D("5")
    renewal = sal.sell(
        branch=s["prm"],
        user=s["desk"],
        member=sibling,
        cart=sal.Cart(items=[sal.Item(pricing_option=s["monthly"])], payments=[sal.Pay("cash", D("80"))]),
    )
    assert renewal.total == D("80.000")


def test_freeze_rules_and_approval(setup):
    s = setup
    m = member(s["prm"])
    sell_option(s, m, s["monthly"])
    membership = Membership.objects.get(member=m)
    end = membership.end_date
    with pytest.raises(ValidationError):
        sal.request_change(
            kind="freeze", user=s["desk"], reason="Travel", membership=membership, freeze_start=TODAY, freeze_weeks=5
        )
    req = sal.request_change(
        kind="freeze", user=s["desk"], reason="Travel", membership=membership, freeze_start=TODAY, freeze_weeks=2
    )
    with pytest.raises(PermissionDenied):
        sal.decide_request(req, True, s["desk2"])  # admins cannot approve
    sal.decide_request(req, True, s["om"])
    membership.refresh_from_db()
    assert membership.end_date == end + datetime.timedelta(weeks=2) and membership.freeze_used
    assert sal.member_status(m).code == "frozen"
    with pytest.raises(ValidationError):
        sal.request_change(
            kind="freeze", user=s["desk"], reason="Again", membership=membership, freeze_start=TODAY, freeze_weeks=1
        )  # once per membership


def test_refund_makes_a_negative_receipt_and_counts_in_cash_up(setup):
    s = setup
    m = member(s["prm"])
    sell_option(s, m, s["monthly"])
    membership = Membership.objects.get(member=m)
    req = sal.request_change(
        kind="refund",
        user=s["desk"],
        reason="Moving abroad",
        membership=membership,
        refund_amount=D("40"),
        refund_method="cash",
    )
    sal.decide_request(req, True, s["om"])
    req.refresh_from_db()
    assert req.refund_sale.total == D("-40") and req.refund_sale.number == 2
    membership.refresh_from_db()
    assert membership.status == Membership.Status.REFUNDED
    cash_up = sal.open_cash_up(s["prm"], TODAY, s["desk"])
    assert cash_up.expected_cash == D("45")


def test_cash_up_needs_reason_above_one_kd_and_other_person_verifies(setup):
    s = setup
    sell_option(s, member(s["prm"]), s["monthly"])
    cash_up = sal.open_cash_up(s["prm"], TODAY, s["desk"])
    with pytest.raises(ValidationError):
        sal.submit_cash_up(cash_up, s["desk"], counted_cash=D("83"), terminal_knet=D("0"), terminal_card=D("0"))
    cash_up = sal.submit_cash_up(
        cash_up,
        s["desk"],
        counted_cash=D("83"),
        terminal_knet=D("0"),
        terminal_card=D("0"),
        reason="Change given twice",
    )
    assert cash_up.cash_difference == D("-2")
    with pytest.raises(PermissionDenied):
        sal.verify_cash_up(cash_up, s["desk"])
    assert sal.verify_cash_up(cash_up, s["om"]).status == CashUp.Status.VERIFIED


def test_member_status_is_calculated(setup):
    s = setup
    m = member(s["prm"])
    assert sal.member_status(m).code == "lead"
    sell_option(s, m, s["monthly"])
    assert sal.member_status(m).code == "active"
    Membership.objects.filter(member=m).update(end_date=TODAY + datetime.timedelta(days=3))
    assert sal.member_status(m).code == "expiring"
    Membership.objects.filter(member=m).update(end_date=TODAY - datetime.timedelta(days=1))
    assert sal.member_status(m).code == "expired"
    m.is_active = False
    assert sal.member_status(m).code == "former"


# --------------------------------------------------------------------------- M6
def test_renewals_list_outcomes_and_instructor_handoff(setup):
    s = setup
    slot, _ = slot_today(s)
    expiring, expired, renewed, trial_only = (member(s["prm"], n) for n in ("Exp", "Old", "Ren", "Tri"))
    for m in (expiring, expired, renewed):
        sell_option(s, m, s["monthly"])
    sell_option(s, trial_only, s["trial"])
    Membership.objects.filter(member=expiring).update(end_date=TODAY + datetime.timedelta(days=3))
    Membership.objects.filter(member=expired).update(end_date=TODAY - datetime.timedelta(days=10))
    Membership.objects.filter(member=renewed).update(end_date=TODAY + datetime.timedelta(days=2))
    sell_option(s, renewed, s["monthly"])  # already renewed: skipped
    Enrollment.objects.create(member=expired, slot=slot)

    rows = ren.follow_up_list(s["prm"])
    assert [r.member.first_name for r in rows] == ["Exp", "Old"]

    old = Membership.objects.get(member=expired)
    for _ in range(3):
        ren.record_follow_up(old, s["desk"], outcome="N")
    handoff = InstructorHandoff.objects.get(membership=old)
    assert handoff.instructor == s["coach"]
    ren.record_follow_up(old, s["desk"], outcome="L", leaving_reason="Moved to another area")
    assert [r.member.first_name for r in ren.follow_up_list(s["prm"])] == ["Exp"]
    assert FollowUp.objects.filter(membership=old, outcome="N").count() == 3


def test_reminders_sent_once_at_five_and_one_days(setup):
    s = setup
    guardian = Guardian.objects.create(full_name="Parent", mobile="+96550003333")
    m = member(s["prm"])
    GuardianLink.objects.create(guardian=guardian, member=m, relationship="father", is_primary=True)
    sell_option(s, m, s["monthly"])
    Membership.objects.filter(member=m).update(end_date=TODAY + datetime.timedelta(days=5))
    assert ren.send_reminders() == 1
    assert ren.send_reminders() == 0


def test_at_risk_members_without_visits(setup):
    s = setup
    m = member(s["prm"])
    sell_option(s, m, s["monthly"], start_date=TODAY - datetime.timedelta(days=20))
    assert [row[0] for row in ren.at_risk(s["prm"])] == [m]


# --------------------------------------------------------------------------- API
def test_api_check_in_and_booking_use_the_same_rules(setup, client_for):
    s = setup
    _, session = slot_today(s, capacity=1)
    m = member(s["prm"])
    desk = client_for(s["desk"])
    r = desk.post("/api/v1/check-ins/", {"member": m.pk, "session": session.pk}, format="json")
    assert r.status_code == 201 and r.data["warning"] == "no_membership"
    booked = desk.post(
        "/api/v1/bookings/", {"session": session.pk, "guest_name": "Sara", "guest_mobile": "55512345"}, format="json"
    )
    assert booked.status_code == 201 and booked.data["status"] == "booked"
    coach = client_for(s["coach"])
    assert coach.post("/api/v1/bookings/", {"session": session.pk, "member": m.pk}, format="json").status_code == 403
    assert desk.get(f"/api/v1/class-sessions/{session.pk}/roster/").status_code == 200
    assert client_for(s["bed_desk"]).get("/api/v1/sales/").data["count"] == 0  # other branch's sales are hidden
