"""Phase 6 pages: the family portal on the website and the desk's message screens (fictional seed data)."""

import pytest
from django.core.management import call_command
from django.test import Client

from apps.members.models import Member
from apps.notifications.models import MessageLog
from apps.portal import services as ps
from apps.portal.models import RenewalPayment
from apps.sales.models import Membership
from apps.shop.payments import TestGateway


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


@pytest.fixture
def data(db):
    call_command("seed_kuwait", families=4, adults=3, verbosity=0)
    call_command("seed_website", verbosity=0)


def login(who):
    from django.contrib.auth import get_user_model

    client = Client()
    client.force_login(get_user_model().objects.get(email=f"{who}@test.elite.local"))
    return client


def parent_and_children():
    from django.contrib.auth import get_user_model

    parent = get_user_model().objects.get(email="parent@test.elite.local")
    return parent, list(ps.family(parent))


def test_portal_pages_render_for_the_family_in_both_languages(data):
    parent, children = parent_and_children()
    client = login("parent")
    for lang in ("en", "ar"):
        assert client.get(f"/{lang}/my/").status_code == 200
        for child in children:
            r = client.get(f"/{lang}/my/{child.pk}/")
            assert r.status_code == 200, (lang, child)
    stranger = Member.objects.exclude(pk__in=[c.pk for c in children]).first()
    assert client.get(f"/en/my/{stranger.pk}/").status_code == 404
    assert Client().get(f"/en/my/{children[0].pk}/").status_code == 302  # signed out → portal sign-in
    assert login("admin.prm").get("/en/my/").status_code == 302  # staff aren't a family


def test_renewal_round_trip_through_the_test_payment_page(data):
    parent, children = parent_and_children()
    child = next(c for c in children if ps.renewal_option(c) is not None)
    client = login("parent")
    before = Membership.objects.filter(member=child).count()
    r = client.post(f"/en/my/{child.pk}/renew/", {"method": "knet"})
    assert r.status_code == 302 and "/pay/test/" in r["Location"]
    payment = RenewalPayment.objects.filter(member=child, status="pending").latest("created_at")
    assert client.get(r["Location"]).status_code == 200  # the stand-in bank page
    sig = TestGateway.signature(payment.reference, "approve")
    back = client.get(f"/en/my/renewal/{payment.reference}/?outcome=approve&sig={sig}")
    assert back.status_code == 302
    payment.refresh_from_db()
    assert payment.status == "paid" and Membership.objects.filter(member=child).count() == before + 1
    # Someone else's payment reference is not found.
    assert login("admin.prm").get(f"/en/my/renewal/{payment.reference}/").status_code in (302, 404)


def test_booking_consent_and_account_from_the_pages(data):
    parent, children = parent_and_children()
    client = login("parent")
    child = children[0]
    client.post(f"/en/my/{child.pk}/", {"action": "consent", "internal": "1"})
    assert not child.media_consents.first().website_marketing
    client.post("/en/my/", {"email": "new@example.test", "service": "", "broadcasts": "1"})
    from apps.notifications.services import service_messages_on

    assert not service_messages_on(ps.family_mobile(parent))
    page = client.get("/en/my/").content.decode()
    assert "new@example.test" in page


def test_desk_message_screens_and_order_ready(data):
    assert MessageLog.objects.exists()
    ops = login("ops")
    for lang in ("en", "ar"):
        assert ops.get(f"/{lang}/desk/messages/").status_code == 200
        assert ops.get(f"/{lang}/desk/messages/wording/").status_code == 200
    mk = login("marketing")
    mk.post(
        "/en/desk/messages/wording/",
        {"key": "trial_confirmed", "action": "save", "text_en": "Hi {name}", "text_ar": "أهلاً {name}"},
    )
    from apps.notifications.models import MessageTemplate

    assert not MessageTemplate.objects.filter(key="trial_confirmed").exists()  # placeholders missing → refused
    assert login("coach.prm").get("/en/desk/messages/").status_code == 403
    from apps.shop.models import Order

    order = Order.objects.filter(status="paid").first()
    branch_code = order.items.first().branch.code
    who = login("admin.bed" if branch_code == "BED" else "admin.prm")
    who.post(f"/en/desk/online-orders/{order.pk}/fulfil/", {"action": "ready"})
    assert Order.objects.get(pk=order.pk).status == "ready"
    assert MessageLog.objects.filter(kind__in=["order_ready", "order_sent"], to=order.mobile).exists()
