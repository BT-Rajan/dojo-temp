"""Phase 5 desk screens and the website hooks, driven as each role would use them (fictional seed data)."""

import datetime

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from apps.assistant.models import Article, Conversation
from apps.classes.models import ClassSession
from apps.leads.models import Broadcast, Campaign, GroupDeal, Lead
from apps.members.models import Member


@pytest.fixture
def data(db):
    call_command("seed_kuwait", families=4, adults=3, verbosity=0)


def desk(who):
    from django.contrib.auth import get_user_model

    client = Client()
    client.force_login(get_user_model().objects.get(email=f"{who}@test.elite.local"))
    return client


def url(path, lang="en"):
    return f"/{lang}/desk/{path}"


def test_every_phase5_screen_renders_in_both_languages(data):
    lead = Lead.objects.filter(branch__code="PRM").first()
    deal = GroupDeal.objects.first()
    conv = Conversation.objects.filter(channel="saqr").first()
    article = Article.objects.first()
    member = Member.objects.filter(branch__code="PRM").first()
    screens = {
        "admin.prm": [
            "leads/",
            "leads/?show=overdue",
            "leads/?show=joined",
            f"leads/{lead.pk}/",
            "leads/report/",
            "leads/report/?branch=all&days=90",
            "group-sales/",
            f"group-sales/{deal.pk}/",
            "saqr/",
            "saqr/?show=all",
            f"saqr/{conv.pk}/",
            "assistant/",
            f"members/{member.pk}/",
            f"members/{member.pk}/referral-card/",
        ],
        "marketing": ["marketing/campaigns/", "marketing/broadcasts/", "knowledge-base/", "leads/"],
        "ops": ["knowledge-base/", f"knowledge-base/{article.pk}/", "knowledge-base/new/", f"group-sales/{deal.pk}/"],
        "coach.prm": ["assistant/"],
    }
    for who, paths in screens.items():
        client = desk(who)
        for path in paths:
            for lang in ("en", "ar"):
                response = client.get(url(path, lang))
                assert response.status_code == 200, (who, path, lang, response.status_code)
    assert desk("admin.prm").get(url("trials/")).status_code == 302  # old page → leads


def test_who_can_see_what(data):
    coach = desk("coach.prm")
    for path in ["leads/", "group-sales/", "saqr/", "knowledge-base/", "marketing/campaigns/"]:
        assert coach.get(url(path)).status_code == 403, path
    admin = desk("admin.prm")
    for path in ["marketing/campaigns/", "marketing/broadcasts/", "knowledge-base/"]:
        assert admin.get(url(path)).status_code == 403, path
    bed_lead = Lead.objects.filter(branch__code="BED").first()
    assert admin.get(url(f"leads/{bed_lead.pk}/")).status_code == 404
    assert desk("parent").get(url("assistant/")).status_code in (302, 403)


def test_a_lead_from_first_call_to_trial_at_the_desk(data):
    admin = desk("admin.prm")
    admin.post(url("leads/"), {"name": "Desk Walk-in", "mobile": "60009001", "source": "walk_in", "interest": "Son, 9"})
    lead = Lead.objects.get(mobile="+96560009001")
    assert lead.owner.email == "admin.prm@test.elite.local" and lead.stage == "contacted"
    due = (timezone.localtime() + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    admin.post(
        url(f"leads/{lead.pk}/"),
        {"action": "contact", "kind": "whatsapp", "text": "Sent times", "next_action": "Book", "next_due": due},
    )
    assert lead.activities.filter(kind="whatsapp").exists()
    session = next(
        s
        for s in ClassSession.objects.filter(
            branch__code="PRM", date__gte=timezone.localdate(), status="scheduled"
        ).order_by("date", "start")
        if not s.is_over
    )
    admin.post(url(f"leads/{lead.pk}/"), {"action": "book", "session": session.pk})
    lead.refresh_from_db()
    assert lead.stage == "trial_booked" and lead.trial_booking.session == session
    # The class list shows the trial; feedback from there.
    page = admin.get(url(f"classes/{session.pk}/")).content.decode()
    assert "Desk Walk-in" in page
    admin.post(url(f"classes/trial/{lead.trial_booking_id}/feedback/"), {"score": "4", "note": "Good"})
    lead.refresh_from_db()
    assert lead.trial_score == 4 and lead.stage == "trial_done"
    admin.post(url(f"leads/{lead.pk}/"), {"action": "lost", "reason": "timing", "note": "Evenings"})
    assert Lead.objects.get(pk=lead.pk).stage == "lost"


def test_group_deal_marketing_and_knowledge_base_at_the_desk(data):
    deal = GroupDeal.objects.get(stage="proposal")
    admin = desk("admin.prm")
    admin.post(url(f"group-sales/{deal.pk}/"), {"stage": "paid", "value": "800", "participants": "20"})
    assert GroupDeal.objects.get(pk=deal.pk).stage == "paid"
    admin.post(url(f"group-sales/{deal.pk}/"), {"stage": "delivery"})
    assert GroupDeal.objects.get(pk=deal.pk).stage == "paid"  # Operations must confirm first
    desk("ops").post(url(f"group-sales/{deal.pk}/"), {"action": "confirm"})
    admin.post(url(f"group-sales/{deal.pk}/"), {"stage": "delivery"})
    assert GroupDeal.objects.get(pk=deal.pk).stage == "delivery"
    mk = desk("marketing")
    mk.post(
        url("marketing/campaigns/"),
        {"name": "Desk campaign", "code": "desk-test", "channel": "google", "spend": "40"},
    )
    assert Campaign.objects.filter(code="desk-test").exists()
    content = desk("content")
    content.post(
        url("marketing/broadcasts/"),
        {"title": "Desk broadcast", "message_en": "Hello", "message_ar": "مرحبا", "ages": "all"},
    )
    b = Broadcast.objects.get(title="Desk broadcast")
    mk.post(url("marketing/broadcasts/"), {"broadcast": b.pk, "action": "send"})
    assert Broadcast.objects.get(pk=b.pk).status == "sent"
    ops = desk("ops")
    ops.post(
        url("knowledge-base/new/"),
        {"title_en": "Desk article", "body_en": "Body", "audience": "staff", "status": "published"},
    )
    a = Article.objects.get(title_en="Desk article")
    ops.post(url(f"knowledge-base/{a.pk}/"), {"title_en": "Desk article", "body_en": "Body 2", "audience": "staff"})
    v1 = a.versions.get(version=1)
    ops.post(url(f"knowledge-base/{a.pk}/"), {"restore": v1.pk})
    assert Article.objects.get(pk=a.pk).body_en == "Body" and a.versions.count() == 3


def test_saqr_queue_and_the_staff_assistant(data):
    conv = Conversation.objects.filter(channel="saqr", handed_off_at__isnull=False).first()
    admin = desk("admin.prm")
    admin.post(url(f"saqr/{conv.pk}/"), {"action": "take"})
    assert Conversation.objects.get(pk=conv.pk).taken_by.email == "admin.prm@test.elite.local"
    admin.post(url(f"saqr/{conv.pk}/"), {"action": "review", "ok": "0", "note": "Should mention the OM"})
    assert Conversation.objects.get(pk=conv.pk).review_ok is False
    r = admin.post(url(f"saqr/{conv.pk}/"), {"action": "lead", "name": "Chat Parent", "mobile": "60009002"})
    lead = Lead.objects.get(mobile="+96560009002")
    assert r.status_code == 302 and lead.chat == conv
    admin.post(url("assistant/"), {"question": "How do I transfer stock to Bedaya?"})
    page = admin.get(url("assistant/")).content.decode()
    assert "Send stock" in page and "Article:" in page


def test_website_trial_form_creates_a_lead_with_the_campaign(data):
    call_command("seed_website", verbosity=0)
    Campaign.objects.create(name="Web", code="web-test", channel="google", start=timezone.localdate())
    client = Client()
    client.get("/en/?c=web-test")
    client.post("/en/book-a-trial/", {"form": "trial", "name": "Web Parent", "mobile": "60009003", "branch": "PRM"})
    lead = Lead.objects.filter(mobile="+96560009003").first()
    assert lead is not None and lead.source == "website" and lead.campaign.code == "web-test"
