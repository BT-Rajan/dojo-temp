"""Phase 7 pages: the management screens and the Quarterly Business Report (fictional seed data)."""

import pytest
from django.core.management import call_command
from django.test import Client

from apps.management.models import (
    Announcement,
    Escalation,
    Handoff,
    LeadReport,
    Meeting,
    Procedure,
    QuarterlyReport,
    Recipient,
)


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


@pytest.fixture
def data(db):
    call_command("seed_kuwait", families=3, adults=2, verbosity=0)


def login(who):
    from django.contrib.auth import get_user_model

    client = Client()
    client.force_login(get_user_model().objects.get(email=f"{who}@test.elite.local"))
    return client


def test_every_management_page_renders_in_both_languages(data):
    pages = [
        "management/",
        "management/announcements/",
        "management/handoffs/?show=all",
        "management/handoffs/new/",
        "management/meetings/",
        "management/monthly-reports/",
        "management/escalations/",
        "management/escalations/new/",
        "management/procedures/",
        "management/directory/",
        "management/quarterly/",
        "management/quarterly/so-far/",
        "tasks/",
    ]
    pages += [f"management/announcements/{a.pk}/" for a in Announcement.objects.all()]
    pages += [f"management/handoffs/{h.pk}/" for h in Handoff.objects.all()]
    pages += [f"management/meetings/{m.pk}/" for m in Meeting.objects.all()]
    pages += [f"management/monthly-reports/{r.pk}/" for r in LeadReport.objects.all()]
    pages += [f"management/escalations/{e.pk}/" for e in Escalation.objects.all()]
    pages += [f"management/procedures/{p.pk}/" for p in Procedure.objects.all()]
    pages += [f"management/quarterly/{q.pk}/" for q in QuarterlyReport.objects.all()]
    ceo = login("ceo")
    for lang in ("en", "ar"):
        for page in pages:
            r = ceo.get(f"/{lang}/desk/{page}")
            assert r.status_code == 200, (lang, page, r.status_code)


def test_access_rules_on_the_pages(data):
    coach = login("coach.prm")
    assert coach.get("/en/desk/management/").status_code == 200
    assert coach.get("/en/desk/management/quarterly/").status_code == 403
    assert coach.get("/en/desk/management/monthly-reports/").status_code == 403
    assert coach.get("/en/desk/management/announcements/new/").status_code == 403
    for h in Handoff.objects.all():
        assert coach.get(f"/en/desk/management/handoffs/{h.pk}/").status_code == 404
    assert login("parent").get("/en/desk/management/").status_code == 403


def test_confirm_and_forward_from_the_page(data):
    r = Recipient.objects.filter(is_copy=False, confirmed_at__isnull=True, announcement__root__isnull=True).first()
    who = r.user.email.split("@")[0]
    client = login(who)
    client.post(f"/en/desk/management/announcements/{r.announcement_id}/", {"action": "confirm"})
    r.refresh_from_db()
    assert r.confirmed_at is not None
    tasks = login("ceo").get("/en/desk/tasks/").content.decode()
    assert "Approve the Quarterly Business Report" not in tasks  # still a draft


def test_quarterly_report_page_submit_and_export(data):
    report = QuarterlyReport.objects.get()
    om = login("ops")
    r = om.post(
        f"/en/desk/management/quarterly/{report.pk}/",
        {"action": "submit", "summary": "S", "strategy": "T", "difference_note": "Weeks not verified yet"},
    )
    assert r.status_code == 302
    report.refresh_from_db()
    assert report.status == "submitted" and report.data
    for fmt in ("pdf", "xlsx"):
        resp = om.get(f"/en/desk/management/quarterly/{report.pk}/?format={fmt}")
        assert resp.status_code == 200 and resp["Content-Disposition"].startswith("attachment")
    assert "Approve the Quarterly Business Report" in login("ceo").get("/en/desk/tasks/").content.decode()
    login("ceo").post(f"/en/desk/management/quarterly/{report.pk}/", {"action": "approve"})
    assert QuarterlyReport.objects.get(pk=report.pk).status == "approved"


def test_raise_an_escalation_and_send_a_handoff_from_the_pages(data):
    admin = login("admin.bed")
    admin.post("/en/desk/management/escalations/new/", {"kind": "safety", "description": "Wet floor", "needs_ceo": "1"})
    e = Escalation.objects.filter(description="Wet floor").get()
    assert e.needs_ceo and e.lead is not None
    admin.post(
        "/en/desk/management/handoffs/new/",
        {"kind": "it_request", "subject": "Scanner", "detail": "QR scanner broken", "why": "Check-in is slow"},
    )
    assert Handoff.objects.filter(subject="Scanner", receiver__email="it@test.elite.local").exists()
