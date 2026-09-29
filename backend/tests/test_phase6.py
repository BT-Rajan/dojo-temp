"""Phase 6 rules: messaging categories and preferences, templates, portal booking, renewal, freeze, consent, rules."""

import datetime
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import RequestFactory
from django.utils import timezone

from apps.classes.models import Booking, ClassSession
from apps.core.messaging import OUTBOX_KEY, send_message
from apps.members.models import Guardian, GuardianLink, Member
from apps.notifications import services as ns
from apps.notifications.models import MessageLog
from apps.organization.models import PricingOption, Program
from apps.portal import services as ps
from apps.portal.models import RenewalPayment
from apps.rbac.models import Role, RoleAssignment
from apps.sales import services as sal
from apps.sales.models import AccountRequest, Membership
from apps.shop.payments import TestGateway

D = Decimal
TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


def outbox():
    return cache.get(OUTBOX_KEY, [])


@pytest.fixture
def s(branches, make_user):
    prm = branches["PRM"]
    program = Program.objects.create(branch=prm, name="Kids", name_ar="أطفال")
    monthly = PricingOption.objects.create(
        branch=prm, name="Monthly", kind="membership", price=D("85"), duration_days=30, approval="approved"
    )
    monthly.programs.add(program)
    desk = make_user("branch_admin", branch=prm)
    parent_user = make_user()
    RoleAssignment.objects.create(user=parent_user, role=Role.objects.get(code="guardian"), reason="test")
    guardian = Guardian.objects.create(full_name="Test Parent", mobile="+96560006666", user=parent_user)
    child = Member.objects.create(
        branch=prm, first_name="Salem", last_name="Phasevi", date_of_birth=datetime.date(2016, 5, 10), gender="male"
    )
    GuardianLink.objects.create(member=child, guardian=guardian, relationship="father", is_primary=True)
    other = Member.objects.create(
        branch=prm, first_name="Other", last_name="Family", date_of_birth=datetime.date(2015, 1, 1), gender="male"
    )
    sal.sell(
        branch=prm,
        user=desk,
        cart=sal.Cart(items=[sal.Item(pricing_option=monthly)], payments=[sal.Pay("cash", D("85"))]),
        member=child,
    )
    return {"prm": prm, "program": program, "monthly": monthly, "desk": desk, "parent": parent_user,
            "guardian": guardian, "child": child, "other": other}  # fmt: skip


def session(s, days=1, capacity=20, start=datetime.time(17, 0)):
    return ClassSession.objects.create(
        branch=s["prm"],
        program=s["program"],
        title_en="Kids",
        date=TODAY + datetime.timedelta(days=days),
        start=start,
        end=(datetime.datetime.combine(TODAY, start) + datetime.timedelta(hours=1)).time(),
        capacity=capacity,
    )


# ---------------------------------------------------------------------------
# M17 messaging
# ---------------------------------------------------------------------------
def test_every_message_is_logged_and_service_messages_respect_the_family(s):
    assert send_message("+96560006666", "Receipt", kind="receipt")
    ns.set_service_messages("+96560006666", False)
    assert not send_message("+96560006666", "Reminder", category="service", kind="renewal_reminder")
    assert send_message("+96560006666", "Class moved", kind="class_change")  # essential always goes
    logs = list(MessageLog.objects.order_by("id").values_list("kind", "status"))
    assert ("renewal_reminder", "skipped") in logs and ("class_change", "sent") in logs
    assert outbox()[0]["text"] == "Class moved"
    with pytest.raises(ValueError):
        send_message("+96560006666", "x", category="spam")
    # Staff alerts are logged too.
    from apps.rbac.services import notify_perm

    s["desk"].mobile = "+96550001234"
    s["desk"].save()
    notify_perm("sales.sell", "Cash-up waiting", s["prm"].pk)
    assert MessageLog.objects.filter(category="staff", to="+96550001234").exists()


def test_wording_overrides_keep_placeholders(s, make_user):
    mk = make_user("marketing_lead")
    with pytest.raises(PermissionDenied):
        ns.save_template(s["desk"], "order_ready", "x", "y")
    with pytest.raises(ValidationError):
        ns.save_template(mk, "order_ready", "Ready!", "جاهز!")  # placeholders dropped
    ns.save_template(mk, "order_ready", "{reference} is waiting at {branch}.", "{reference} بانتظارك في {branch}.")
    assert ns.render("order_ready", "en", reference="EA-1", branch="Promenade") == "EA-1 is waiting at Promenade."
    ns.reset_template(mk, "order_ready")
    assert "ready for pick-up" in ns.render("order_ready", "en", reference="EA-1", branch="Promenade")


def test_online_order_ready_message(s):
    from apps.inventory.services import set_opening
    from apps.shop.models import Product, ProductVariant, fulfil_order, mark_ready, place_order

    p = Product.objects.create(name_en="Gloves", slug="gl6", category="gloves", price=D("10"))
    v = ProductVariant.objects.create(product=p, size="10 oz")
    set_opening(v, s["prm"], 2)
    order = place_order(
        cart_lines=[(v.pk, 1)],
        customer={"customer_name": "Buyer", "mobile": "+96560007777", "email": "", "pickup_branch": s["prm"]},
        fulfilment="pickup",
        payment_method="knet",
        delivery_fee=D("0"),
        language="en",
    )
    with pytest.raises(ValueError):
        mark_ready(order, s["desk"])  # not paid
    order.mark_paid("T1")
    mark_ready(order, s["desk"])
    assert outbox()[0]["to"] == "+96560007777" and "ready for pick-up" in outbox()[0]["text"]
    fulfil_order(order, s["desk"])


# ---------------------------------------------------------------------------
# M15 portal
# ---------------------------------------------------------------------------
def test_the_portal_only_reaches_the_signed_in_family(s):
    assert list(ps.family(s["parent"])) == [s["child"]]
    with pytest.raises(Http404):
        ps.member_for(s["parent"], s["other"].pk)
    assert list(ps.family(s["desk"])) == []  # staff aren't a family


def test_booking_and_cancelling_from_the_portal(s):
    sess = session(s)
    rows = ps.upcoming(s["child"])
    assert any(r["s"] == sess and r["can_book"] for r in rows)
    b = ps.book(s["parent"], s["child"], sess)
    assert b.status == "booked" and b.source == "portal"
    assert "booked" in outbox()[0]["text"].lower() or "حجز" in outbox()[0]["text"]
    with pytest.raises(ValidationError):
        ps.book(s["parent"], s["child"], sess)  # already booked
    with pytest.raises(Http404):
        ps.book(s["parent"], s["other"], sess)
    with pytest.raises(ValidationError):
        ps.book(s["parent"], s["child"], session(s, days=9))  # more than 7 days ahead
    # A class the membership doesn't cover.
    other_prog = Program.objects.create(branch=s["prm"], name="Adults", name_ar="كبار")
    adults = session(s, days=2)
    adults.program = other_prog
    adults.save()
    with pytest.raises(ValidationError):
        ps.book(s["parent"], s["child"], adults)
    # A full class → waiting list.
    full = session(s, days=3, capacity=0)
    assert ps.book(s["parent"], s["child"], full).status == "waitlisted"
    # Late cancellation is only recorded.
    soon = timezone.localtime() + datetime.timedelta(minutes=90)
    late = session(s, days=0, start=soon.time().replace(second=0, microsecond=0))
    if late.date == soon.date():
        b2 = ps.book(s["parent"], s["child"], late)
        assert ps.cancel(s["parent"], b2).late_cancellation
    b = ps.cancel(s["parent"], Booking.objects.get(pk=b.pk))
    assert b.status == "cancelled"


def _return(payment, outcome):
    rf = RequestFactory()
    return rf.get("/", {"outcome": outcome, "sig": TestGateway.signature(payment.reference, outcome)})


def test_online_renewal_extends_the_membership_and_sends_the_receipt(s):
    current = Membership.objects.get(member=s["child"])
    payment = ps.start_renewal(s["parent"], s["child"], "knet")
    assert payment.amount == D("85") and payment.status == "pending"
    paid, ref = TestGateway().verify(payment, _return(payment, "approve"))
    payment = ps.complete_renewal(payment, paid, ref)
    assert payment.status == "paid" and payment.sale.total == D("85")
    new = Membership.objects.filter(member=s["child"]).order_by("-end_date").first()
    assert new != current and new.start_date == current.end_date + datetime.timedelta(days=1)
    assert payment.sale.payments.get().method == "knet"
    assert any("renewed" in m["text"] or "تجديد" in m["text"] for m in outbox())
    assert ps.complete_renewal(payment, True, ref).sale == payment.sale  # idempotent
    # A declined payment changes nothing.
    declined = ps.start_renewal(s["parent"], s["child"], "card")
    ok, ref = TestGateway().verify(declined, _return(declined, "decline"))
    declined = ps.complete_renewal(declined, ok, ref)
    assert declined.status == "failed" and declined.sale is None
    assert RenewalPayment.objects.filter(status="paid").count() == 1
    # A forged return is not a payment.
    forged = ps.start_renewal(s["parent"], s["child"], "knet")
    assert TestGateway().verify(forged, RequestFactory().get("/", {"outcome": "approve", "sig": "x"})) == (False, "")
    with pytest.raises(Http404):
        ps.start_renewal(s["parent"], s["other"])


def test_freeze_request_goes_to_the_om(s):
    req = ps.request_freeze(s["parent"], s["child"], TODAY + datetime.timedelta(days=3), 2, "Travel")
    assert req.kind == "freeze" and req.status == "pending" and "portal" in req.reason
    with pytest.raises(ValidationError):
        ps.request_freeze(s["parent"], s["child"], TODAY + datetime.timedelta(days=3), 2, "Again")
    with pytest.raises(PermissionDenied):
        sal.request_change(
            kind=AccountRequest.Kind.REFUND,
            user=s["parent"],
            reason="x",
            membership=req.membership,
            by_family=True,
        )


def test_consent_rules_details_and_message_choices(s):
    c = ps.set_consent(s["parent"], s["child"], True, False, False)
    assert c.signed_by_name == "Test Parent" and not c.website_marketing
    assert not ps.rules_signed(s["child"])
    with pytest.raises(ValidationError):
        ps.sign_rules(s["parent"], s["child"], "Someone Else", True)
    with pytest.raises(ValidationError):
        ps.sign_rules(s["parent"], s["child"], "Test Parent", False)
    ps.sign_rules(s["parent"], s["child"], "test parent", True)
    assert ps.rules_signed(s["child"])
    ps.update_email(s["parent"], "parent@example.test")
    s["guardian"].refresh_from_db()
    assert s["guardian"].email == "parent@example.test"
    with pytest.raises(ValidationError):
        ps.update_email(s["parent"], "not-an-email")
    ps.set_messages(s["parent"], service_on=False, broadcasts_on=True)
    assert not ns.service_messages_on("+96560006666")
    from apps.leads.services import opted_in

    assert opted_in(s["child"])
    send_message("+96560006666", "Hello", kind="receipt")
    assert [m.text for m in ps.recent_messages(s["parent"])][:1] == ["Hello"]
