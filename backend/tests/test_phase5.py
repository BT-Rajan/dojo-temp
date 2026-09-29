"""Phase 5 rules: leads, trials, group sales, campaigns, referrals, reviews, broadcasts, knowledge base, assistants."""

import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import override_settings
from django.utils import timezone

from apps.assistant import services as ai
from apps.assistant.models import Article, Conversation
from apps.classes.models import ClassSession
from apps.core.messaging import OUTBOX_KEY
from apps.leads import services as ls
from apps.leads.models import Broadcast, Campaign, GroupDeal, Lead, ReviewRequest
from apps.members.models import Guardian, GuardianLink, MediaConsent, Member
from apps.organization.models import PricingOption, Program
from apps.sales import services as sal
from apps.website.models import TrialRequest

D = Decimal
TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


@pytest.fixture
def s(branches, make_user):
    prm, bed = branches["PRM"], branches["BED"]
    prm.google_review_url = "https://example.test/review/prm"
    prm.save()
    program = Program.objects.create(branch=prm, name="Kids 8-12", name_ar="أطفال")
    monthly = PricingOption.objects.create(
        branch=prm, name="Monthly", kind="membership", price=D("85"), duration_days=30, approval="approved"
    )
    monthly.programs.add(program)
    users = {
        "desk": make_user("branch_admin", branch=prm),
        "desk2": make_user("branch_admin", branch=prm),
        "bed_desk": make_user("branch_admin", branch=bed),
        "coach": make_user("instructor", branch=prm),
        "om": make_user("operations_manager"),
        "mk": make_user("marketing_lead"),
        "content": make_user("marketing_staff"),
        "acct": make_user("accountant"),
    }
    users["coach"].mobile = "+96550007777"
    users["coach"].save()
    return {"prm": prm, "bed": bed, "program": program, "monthly": monthly, **users}


def outbox():
    return cache.get(OUTBOX_KEY, [])


def session(s, days=1):
    sess = ClassSession.objects.create(
        branch=s["prm"],
        program=s["program"],
        title_en="Kids",
        date=TODAY + datetime.timedelta(days=days),
        start=datetime.time(17, 0),
        end=datetime.time(18, 0),
    )
    sess.instructors.set([s["coach"]])
    return sess


def web_lead(s, mobile="60001111", name="Test Parent"):
    tr = TrialRequest.objects.create(name=name, mobile="+965" + mobile, branch=s["prm"], source="website")
    return ls.intake_from_trial_request(tr, {"campaign": "autumn", "ref": ""})


# ---------------------------------------------------------------------------
# M3 leads and trials
# ---------------------------------------------------------------------------
def test_one_lead_per_enquiry_and_the_first_contact_owns_it(s):
    camp = Campaign.objects.create(name="Autumn", code="autumn", channel="instagram", start=TODAY, spend=D("50"))
    lead = web_lead(s)
    assert lead.stage == "new" and lead.owner is None and lead.campaign == camp and lead.source == "website"
    assert lead.next_due <= timezone.now() + datetime.timedelta(hours=2, minutes=1)
    again = ls.intake(name="Test Parent", mobile="60001111", branch=s["prm"], source="saqr")
    assert again == lead and Lead.objects.count() == 1  # same mobile, still open → same lead
    with pytest.raises(PermissionDenied):
        ls.log_contact(lead, s["bed_desk"], "call", "hi", "x", timezone.now())
    with pytest.raises(ValidationError):
        ls.log_contact(lead, s["desk"], "call", "Talked", "", None)  # next action required
    due = timezone.now() + datetime.timedelta(days=1)
    lead = ls.log_contact(lead, s["desk"], "call", "Talked to the father", "Book a trial", due)
    assert lead.owner == s["desk"] and lead.stage == "contacted"
    lead = ls.log_contact(lead, s["desk2"], "whatsapp", "Sent the timetable", "Book a trial", due)
    assert lead.owner == s["desk"]  # the first contact keeps it
    with pytest.raises(PermissionDenied):
        ls.reassign(lead, s["desk2"], s["desk2"], "Shift change")
    with pytest.raises(ValidationError):
        ls.reassign(lead, s["mk"], s["desk2"], " ")
    lead = ls.reassign(lead, s["mk"], s["desk2"], "Desk 1 on leave")
    assert lead.owner == s["desk2"]
    # A walk-in recorded at the desk is owned by whoever records it.
    walk = ls.intake(name="Walk In", mobile="60002222", branch=s["prm"], source="walk_in", user=s["desk"])
    assert walk.owner == s["desk"] and walk.stage == "contacted"


def test_trial_booking_brief_feedback_review_and_joining(s):
    lead = web_lead(s)
    sess = session(s)
    booking = ls.book_trial(lead, sess, s["desk"])
    lead.refresh_from_db()
    assert lead.stage == "trial_booked" and lead.owner == s["desk"] and lead.trial_booking == booking
    assert lead.next_due == sess.ends_at + datetime.timedelta(hours=24)
    assert any(m["to"] == "+96550007777" and "Trial" in m["text"] for m in outbox())
    assert TrialRequest.objects.get(pk=lead.trial_request_id).status == "booked"
    # Checked in → trial done; the instructor gives 5/5 → review request (once per 90 days).
    from apps.classes import services as classes

    booking.session.date = TODAY
    booking.session.start, booking.session.end = datetime.time(0, 0), datetime.time(23, 59)
    booking.session.save()
    classes.check_in_guest(booking, s["desk"])
    assert Lead.objects.get(pk=lead.pk).stage == "trial_done"
    with pytest.raises(PermissionDenied):
        ls.record_feedback(booking, s["acct"], 5)
    with pytest.raises(ValidationError):
        ls.record_feedback(booking, s["coach"], 6)
    ls.record_feedback(booking, s["coach"], 5, "Natural")
    assert ReviewRequest.objects.filter(mobile=lead.mobile, reason="trial").count() == 1
    ls.request_review(lead.mobile, s["prm"], "trial", lead=lead)
    assert ReviewRequest.objects.count() == 1  # not again within 90 days
    # Joining: first membership sold to a child whose guardian has the lead's mobile.
    child = Member.objects.create(
        branch=s["prm"], first_name="Salem", last_name="Phasev", date_of_birth=datetime.date(2016, 5, 10), gender="male"
    )
    g = Guardian.objects.create(full_name="Test Parent", mobile=lead.mobile)
    GuardianLink.objects.create(member=child, guardian=g, relationship="father", is_primary=True)
    sal.sell(
        branch=s["prm"],
        user=s["desk"],
        cart=sal.Cart(items=[sal.Item(pricing_option=s["monthly"])], payments=[sal.Pay("cash", D("85"))]),
        member=child,
    )
    lead.refresh_from_db()
    assert lead.stage == "joined" and lead.member == child and lead.joined_at


def test_lost_and_reopen(s):
    lead = web_lead(s)
    with pytest.raises(ValidationError):
        ls.mark_lost(lead, s["desk"], "because")
    lead = ls.mark_lost(lead, s["desk"], "timing", "Evenings only")
    assert lead.stage == "lost" and lead.next_due is None
    with pytest.raises(ValidationError):
        ls.book_trial(lead, session(s), s["desk"])
    lead = ls.reopen(lead, s["desk"], "Offer the new evening class", timezone.now() + datetime.timedelta(days=2))
    assert lead.stage == "contacted"
    # A new enquiry after the lead was lost creates a new lead.
    lead = ls.mark_lost(lead, s["desk"], "price")
    new = ls.intake(name="Test Parent", mobile="60001111", branch=s["prm"], source="phone", user=s["desk"])
    assert new.pk != lead.pk


def test_referral_code_credits_the_referrer(s):
    referrer = Member.objects.create(
        branch=s["prm"], first_name="Ref", last_name="Erer", date_of_birth=datetime.date(1990, 1, 1), gender="male"
    )
    code = ls.referral_code_for(referrer)
    assert ls.referral_code_for(referrer) == code
    tr = TrialRequest.objects.create(name="Friend", mobile="+96560003333", branch=s["prm"])
    lead = ls.intake_from_trial_request(tr, {"ref": code.code.lower()})
    assert lead.referrer == referrer
    friend = Member.objects.create(
        branch=s["prm"],
        first_name="Friend",
        last_name="New",
        date_of_birth=datetime.date(1991, 1, 1),
        gender="male",
        mobile="+96560003333",
    )
    assert ls.referrer_for(friend) == referrer


# ---------------------------------------------------------------------------
# Group sales
# ---------------------------------------------------------------------------
def test_group_deal_needs_operations_confirmation_before_delivery(s):
    deal = ls.create_deal(
        s["desk"],
        organisation="Test School",
        kind="school",
        contact_name="Coordinator",
        mobile="60004444",
        branch=s["prm"],
    )
    with pytest.raises(ValidationError):
        ls.move_deal(deal, s["desk"], "lost")  # reason needed
    with pytest.raises(ValidationError):
        ls.move_deal(deal, s["desk"], "paid")  # value needed
    deal = ls.move_deal(deal, s["desk"], "paid", "Paid", value=D("500"), participants=10)
    with pytest.raises(ValidationError):
        ls.move_deal(deal, s["desk"], "delivery")  # Operations hasn't confirmed
    with pytest.raises(PermissionDenied):
        ls.confirm_delivery(deal, s["desk"])
    deal = ls.confirm_delivery(deal, s["om"])
    assert deal.receiving_owner == s["om"]
    deal = ls.move_deal(deal, s["desk"], "delivery")
    assert deal.stage == "delivery"
    with pytest.raises(ValidationError):
        ls.move_deal(deal, s["desk"], "meeting")  # closed


# ---------------------------------------------------------------------------
# M13 campaigns, funnel, broadcasts, consent
# ---------------------------------------------------------------------------
def test_campaign_cost_per_lead_and_join_and_the_funnel(s):
    camp = Campaign.objects.create(name="Autumn", code="autumn", channel="instagram", start=TODAY, spend=D("90"))
    for i in range(3):
        web_lead(s, mobile=f"6000500{i}", name=f"P{i}")
    Lead.objects.filter(mobile="+96560005000").update(stage="joined")
    Lead.objects.filter(mobile="+96560005001").update(stage="lost")
    stats = ls.campaign_stats(camp)
    assert stats == {"leads": 3, "joined": 1, "cost_per_lead": D("30.000"), "cost_per_join": D("90.000")}
    f = ls.funnel(Lead.objects.all())
    assert (f["total"], f["joined"], f["lost"], f["open"], f["rate"]) == (3, 1, 1, 1, 33.3)
    rows = ls.breakdown(Lead.objects.all(), "source")
    assert [(r["key"], r["total"]) for r in rows] == [("website", 3)]  # one row per source


def _member(s, first, mobile, dob=datetime.date(1990, 1, 1)):
    return Member.objects.create(
        branch=s["prm"], first_name=first, last_name="Bc", date_of_birth=dob, gender="female", mobile=mobile
    )


def test_broadcasts_go_only_to_opted_in_families_after_approval(s):
    yes = _member(s, "Yes", "+96560006001")
    no = _member(s, "No", "+96560006002")
    _member(s, "Silent", "+96560006003")
    ls.set_opt_in(yes, s["desk"], True)
    ls.set_opt_in(no, s["desk"], True)
    ls.set_opt_in(no, s["desk"], False)  # the latest choice counts
    with pytest.raises(PermissionDenied):
        ls.save_broadcast(s["desk"], title="x", message_en="x", message_ar="x")
    with pytest.raises(ValidationError):
        ls.save_broadcast(s["content"], title="Test", message_en="Hello", message_ar="")
    b = ls.save_broadcast(s["content"], title="Test", message_en="Hello", message_ar="مرحبا", branch=s["prm"])
    assert [m for m, _, _ in ls.audience(b)] == ["+96560006001"]
    with pytest.raises(PermissionDenied):
        ls.send_broadcast(b, s["content"])  # marketing staff can't approve
    mine = ls.save_broadcast(s["mk"], title="Mine", message_en="Hi", message_ar="هلا")
    with pytest.raises(PermissionDenied):
        ls.send_broadcast(mine, s["mk"])  # not your own draft
    b = ls.send_broadcast(b, s["mk"])
    assert b.status == "sent" and b.recipients == 1 and outbox()[0]["to"] == "+96560006001"
    with pytest.raises(ValidationError):
        ls.send_broadcast(b, s["mk"])
    ls.return_broadcast(mine, s["om"], "Add the date")
    assert Broadcast.objects.get(pk=mine.pk).status == "rejected"


def test_consent_withdrawn_sends_photos_back_to_review(s):
    from django.core.management import call_command
    from wagtail.images.models import Image
    from wagtail.images.tests.utils import get_test_image_file

    from apps.website.models import AlbumPage, AlbumPhoto

    call_command("seed_website", verbosity=0)
    m = _member(s, "Photo", "+96560007001")
    MediaConsent.objects.create(member=m, website_marketing=True, signed_by_name="Adult")
    album = AlbumPage.objects.get(slug="album-1")
    photo = AlbumPhoto.objects.create(
        album=album, image=Image.objects.create(title="t", file=get_test_image_file()), reviewed=True
    )
    AlbumPhoto.tagged_members.through.objects.create(albumphoto=photo, member=m)  # as the CMS saves it
    assert photo.is_public
    MediaConsent.objects.create(member=m, website_marketing=False, signed_by_name="Adult")
    photo.refresh_from_db()
    assert not photo.reviewed and not photo.is_public


# ---------------------------------------------------------------------------
# M16 knowledge base and assistants
# ---------------------------------------------------------------------------
def _article(s, audience="public", status="published", title="Trial terms", body="Wear sports clothes."):
    return ai.save_article(
        s["mk"], title_en=title, body_en=body, audience=audience, status=status, keywords="trial, first class"
    )


def test_knowledge_base_versions_and_search(s):
    with pytest.raises(PermissionDenied):
        _article({**s, "mk": s["desk"]})
    a = _article(s)
    a = ai.save_article(s["mk"], a, body_en="Wear sports clothes and bring water.")
    assert a.version == 2 and a.versions.count() == 2
    a = ai.restore_version(a, a.versions.get(version=1), s["mk"])
    assert a.version == 3 and a.body_en == "Wear sports clothes."
    _article(s, audience="staff", title="How to transfer stock", body="Transfers → Send stock.")
    _article(s, status="draft", title="Trial secret draft", body="trial")
    assert [x.title_en for x in ai.search_articles("what to wear at the trial")] == ["Trial terms"]
    assert ai.search_articles("transfer stock") == []  # staff articles are not public
    assert ai.search_articles("transfer stock", ("public", "staff"))[0].title_en == "How to transfer stock"


def test_saqr_without_ai_uses_rules_and_hands_off(s):
    reply = ai.saqr_message("visitor-a", "How much does it cost?", "en")
    assert reply["text"] and not reply.get("handoff")
    reply = ai.saqr_message("visitor-a", "I want a refund", "en")
    conv = Conversation.objects.get(channel="saqr")
    assert reply["handoff"] and conv.handed_off_at and conv.messages.count() == 4
    assert conv.session_hash and conv.session_hash != "visitor-a"
    with pytest.raises(PermissionDenied):
        ai.take_handoff(conv, s["acct"])
    ai.take_handoff(conv, s["desk"])
    with pytest.raises(ValidationError):
        ai.take_handoff(conv, s["desk2"])
    with pytest.raises(ValidationError):
        ai.review_conversation(conv, s["desk"], False, "")
    ai.review_conversation(conv, s["desk"], False, "Price was wrong")
    assert ai.reviews_this_shift(s["desk"]) == 1


class FakeClient:
    """Stands in for the AI provider: first asks for a tool, then answers."""

    calls = []

    def __init__(self, *a, **k):
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        FakeClient.calls.append(kwargs)
        step = len([m for m in kwargs["messages"] if m["role"] == "assistant"])
        script = FakeClient.script
        if step < len(script) - 1:
            name, args = script[step]
            block = SimpleNamespace(type="tool_use", name=name, input=args, id=f"t{step}")
            return SimpleNamespace(stop_reason="tool_use", content=[block])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=script[-1])])


@override_settings(AI_ENABLED=True, ANTHROPIC_API_KEY="test-key", AI_MODEL="claude-opus-5-5")
def test_saqr_with_ai_books_a_trial_through_a_tool(s, monkeypatch):
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    FakeClient.calls = []
    FakeClient.script = [
        ("book_trial", {"name": "Test Mother", "mobile": "60008888", "branch": "PRM", "interest": "Son, 7"}),
        "Done! The branch will confirm your son's trial time on WhatsApp.",
    ]
    reply = ai.saqr_message("visitor-ai", "Book a trial for my son, I'm Test Mother 60008888, Promenade", "en")
    assert reply["text"].startswith("Done!")
    lead = Lead.objects.get(mobile="+96560008888")
    assert lead.source == "saqr" and lead.chat.channel == "saqr" and lead.trial_request.source == "saqr"
    call = FakeClient.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["fallbacks"] == "default"
    assert {t["name"] for t in call["tools"]} >= {"get_prices", "book_trial", "hand_over"}
    assert all(t["strict"] for t in call["tools"])
    assert Conversation.objects.get(channel="saqr").messages.filter(engine="ai").exists()


@override_settings(AI_ENABLED=True, ANTHROPIC_API_KEY="test-key")
def test_ai_failure_falls_back_to_rules(s, monkeypatch):
    import anthropic

    class Broken(FakeClient):
        def create(self, **kwargs):
            raise anthropic.APIConnectionError(request=None)

    monkeypatch.setattr(anthropic, "Anthropic", Broken)
    reply = ai.saqr_message("visitor-b", "Where are you?", "en")
    assert reply["text"]
    assert Conversation.objects.get().messages.filter(engine="rules").exists()


def test_staff_assistant_only_answers_what_the_user_can_see(s):
    from apps.rbac.services import has_perm

    _article(s, audience="staff", title="How to transfer stock", body="Transfers → Send stock.")
    conv, reply = ai.staff_ask(s["desk"], s["prm"], "How do I transfer stock?", "en")
    assert "Send stock" in reply.text and "Article: How to transfer stock" in reply.sources
    assert has_perm(s["desk"], "reports.branch", s["prm"].pk)
    conv, reply = ai.staff_ask(s["desk"], s["prm"], "KNET sales this week", "en", conv)
    assert "KNET" in reply.text and reply.sources
    _, reply = ai.staff_ask(s["desk"], s["prm"], "active members at Bedaya", "en")
    assert "can't see" in reply.text  # Promenade desk, Bedaya data
    _, reply = ai.staff_ask(s["coach"], s["prm"], "sales last week", "en")
    assert "can't see" in reply.text
    assert conv.messages.count() == 4


@override_settings(AI_ENABLED=True, ANTHROPIC_API_KEY="test-key")
def test_staff_assistant_tools_keep_the_permission_check_with_ai(s, monkeypatch):
    import anthropic

    monkeypatch.setattr(anthropic, "Anthropic", FakeClient)
    FakeClient.calls = []
    FakeClient.script = [("sales_summary", {"branch": "BED", "period": "this_week"}), "You can't see Bedaya's sales."]
    _, reply = ai.staff_ask(s["desk"], s["prm"], "Bedaya sales?", "en")
    last = FakeClient.calls[-1]["messages"][-1]["content"][0]
    assert last["is_error"] and "can't see" in last["content"]
    assert reply.engine == "ai"


def test_old_saqr_chats_are_purged_unless_they_became_a_lead(s):
    ai.saqr_message("old-1", "hi", "en")
    ai.saqr_message("old-2", "hi", "en")
    kept = Conversation.objects.order_by("pk").last()
    ls.intake(name="Kept", mobile="60009999", branch=s["prm"], source="saqr", chat=kept)
    Conversation.objects.update(last_at=timezone.now() - datetime.timedelta(days=100))
    assert ai.purge_old_conversations() == 1
    assert list(Conversation.objects.all()) == [kept]
    assert Article.objects.count() == 0 and GroupDeal.objects.count() == 0
