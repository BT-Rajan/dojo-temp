"""Phase 7 rules: cascade, dual line, handoffs, meetings, lead reports, escalations, procedures and RPT-01."""

import datetime

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.core.messaging import OUTBOX_KEY
from apps.management import quarterly as qbr
from apps.management import services as ms
from apps.management.models import ActionItem, Announcement, Escalation, Handoff, QuarterlyReport, Recipient
from apps.notifications.models import MessageLog
from apps.staff.models import StaffProfile

TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


@pytest.fixture
def org(make_user):
    """CEO → OM and Training Lead; the OM leads a desk admin and a support coach who also coaches under Training."""
    people = {
        "ceo": make_user("ceo"),
        "om": make_user("operations_manager"),
        "tl": make_user("training_lead"),
        "it": make_user("it_admin"),
        "admin": make_user("branch_admin"),
        "support": make_user("operations_support", "instructor"),
        "coach": make_user("instructor"),
    }
    for i, u in enumerate(people.values()):
        u.mobile = f"+9655000{i:04d}"
        u.save()
    prof = {k: StaffProfile.objects.create(user=u, job_title=k, employment_type="full_time") for k, u in people.items()}
    for k in ("om", "tl", "it"):
        prof[k].reports_to = prof["ceo"]
    prof["admin"].reports_to = prof["om"]
    prof["support"].reports_to, prof["support"].second_lead = prof["om"], prof["tl"]
    prof["coach"].reports_to = prof["tl"]
    for p in prof.values():
        p.save()
    return people


def test_working_days_skip_friday_and_saturday():
    thursday = datetime.date(2026, 10, 1)
    assert ms.add_working_days(thursday, 1) == datetime.date(2026, 10, 4)  # Sunday
    assert ms.add_working_days(thursday, 2) == datetime.date(2026, 10, 5)


def test_cascade_is_forwarded_unchanged_and_the_other_lead_is_copied(org):
    with pytest.raises(PermissionDenied):
        ms.post_announcement(org["coach"], "x", "y", [org["om"]])
    post = ms.post_announcement(org["ceo"], "New timetable", "Details here.", [org["om"], org["tl"], org["it"]])
    assert post.recipients.count() == 3 and post.confirm_by == ms.add_working_days(TODAY, 2)
    assert MessageLog.objects.filter(category="staff", to=org["om"].mobile).exists()
    assert not ms.needs_forward(org["it"], post)  # nobody reports to IT
    assert ms.needs_forward(org["om"], post)
    fwd = ms.forward(org["om"], post)
    assert (fwd.title, fwd.body, fwd.root) == (post.title, post.body, post)
    assert set(fwd.recipients.values_list("user_id", flat=True)) == {org["admin"].pk, org["support"].pk}
    assert Recipient.objects.get(announcement=post, user=org["om"]).confirmed_at is not None
    with pytest.raises(ValidationError):
        ms.forward(org["om"], post)  # once only
    # The Training Lead forwards to the coach; the support coach already has it, so no duplicate.
    fwd2 = ms.forward(org["tl"], post)
    assert list(fwd2.recipients.values_list("user_id", flat=True)) == [org["coach"].pk]
    c = ms.cascade(post)
    assert c["total"] == 6 and c["confirmed"] == 2
    assert not c["forwards_pending"]


def test_instruction_to_someone_with_two_leads_is_visible_to_both(org):
    post = ms.post_announcement(org["tl"], "Coaching schedule", "Saturday kids class moves.", [org["support"]])
    copy = Recipient.objects.get(announcement=post, user=org["om"])
    assert copy.is_copy
    assert ms.can_see(org["om"], post)
    assert not ms.can_see(org["admin"], post)


def test_late_confirmations_are_reminded(org):
    post = ms.post_announcement(org["ceo"], "T", "B", [org["tl"]])
    Announcement.objects.filter(pk=post.pk).update(confirm_by=TODAY - datetime.timedelta(days=1))
    assert ms.remind_announcements() == 1
    assert ms.remind_announcements() == 0  # once a day


def test_handoffs_need_confirmation_and_it_needs_a_committed_date(org):
    h = ms.send_handoff(org["tl"], kind="stories", receiver=org["om"], subject="Stories", detail="Three stories")
    assert h.reference.startswith(f"HO-{TODAY:%Y}-") and h.status == "sent"
    with pytest.raises(PermissionDenied):
        ms.confirm_handoff(org["tl"], h)  # only the receiver
    ms.confirm_handoff(org["om"], h)
    with pytest.raises(ValidationError):
        ms.send_handoff(org["om"], kind="it_request", subject="Printer", detail="Broken")  # why missing
    it = ms.send_handoff(org["admin"], kind="it_request", subject="Printer", detail="Broken", why="Receipts")
    assert it.receiver == org["it"]  # routed to Systems & IT
    with pytest.raises(ValidationError):
        ms.confirm_handoff(org["it"], it)  # no timeline
    ms.confirm_handoff(org["it"], it, committed_date=TODAY + datetime.timedelta(days=5))
    ms.complete_handoff(org["it"], it, "Replaced")
    assert Handoff.objects.get(pk=it.pk).status == "done"
    with pytest.raises(PermissionDenied):
        ms.send_handoff(org["om"], kind="it_notice", receiver=org["tl"], subject="x", detail="y", go_live=TODAY)
    up = ms.send_handoff(org["om"], kind="update", subject="Urgent", detail="Water leak")
    assert up.receiver == org["ceo"]
    assert list(ms.visible_handoffs(org["coach"])) == []


def test_meeting_minutes_and_action_items(org):
    with pytest.raises(PermissionDenied):
        ms.create_meeting(org["tl"], TODAY)
    m = ms.create_meeting(org["om"], TODAY)
    assert {a.user_id for a in m.attendees.all()} == {org["ceo"].pk, org["om"].pk, org["tl"].pk, org["it"].pk}
    with pytest.raises(ValidationError):
        ms.save_minutes(org["om"], m, present_ids=set(), agenda=[], decisions=[], actions=[("Do it", None, None)])
    with pytest.raises(ValidationError):
        ms.publish_meeting(org["om"], m)  # nobody present, no agenda
    ms.save_minutes(
        org["om"],
        m,
        present_ids={org["ceo"].pk, org["tl"].pk},
        agenda=[("Month", "Good", org["om"])],
        decisions=[("Open a class", org["om"])],
        actions=[("Draft timetable", org["tl"], TODAY + datetime.timedelta(days=3))],
    )
    ms.publish_meeting(org["om"], m)
    with pytest.raises(ValidationError):
        ms.save_minutes(org["om"], m, present_ids=set(), agenda=[], decisions=[], actions=[])
    ms.acknowledge_minutes(org["ceo"], m)
    m.refresh_from_db()
    assert m.reviewed_by == org["ceo"]
    item = ActionItem.objects.get(meeting=m)
    with pytest.raises(PermissionDenied):
        ms.update_action(org["coach"], item, "done")
    with pytest.raises(ValidationError):
        ms.update_action(org["tl"], item, "dropped")  # needs a reason
    assert ms.update_action(org["tl"], item, "done").done_at is not None
    assert m in ms.visible_meetings(org["tl"]) and m not in ms.visible_meetings(org["coach"])
    later = ms.create_meeting(org["om"], TODAY + datetime.timedelta(days=30))
    assert list(ms.carried_actions(later)) == []


def test_monthly_lead_report_is_prefilled_frozen_and_acknowledged(org):
    last = ms.previous_month(TODAY)
    with pytest.raises(PermissionDenied):
        ms.save_lead_report(org["coach"], last)
    r = ms.save_lead_report(org["om"], last, "", "")
    assert r.function == "operations"
    with pytest.raises(ValidationError):
        ms.submit_lead_report(org["om"], r)  # summary needed
    r = ms.save_lead_report(org["om"], last, "Good month", "")
    ms.submit_lead_report(org["om"], r)
    r.refresh_from_db()
    assert r.status == "submitted" and any(row["en"] == "New leads" for row in r.data["rows"])
    with pytest.raises(ValidationError):
        ms.save_lead_report(org["om"], last, "Changed")
    with pytest.raises(PermissionDenied):
        ms.acknowledge_lead_report(org["tl"], r)
    assert ms.acknowledge_lead_report(org["ceo"], r).status == "acknowledged"
    for who, fn in (("tl", "training"), ("it", "it")):
        assert ms.report_figures(fn, last)
        assert ms.function_of(org[who]) == fn


def test_escalation_24_hour_rule_and_direct_route(org):
    e = ms.raise_escalation(org["coach"], kind="safety", description="Loose mat", needs_ceo=True)
    assert e.lead == org["tl"] and e.ceo_due_at is not None
    with pytest.raises(PermissionDenied):
        ms.name_owner(org["admin"], e, org["om"])
    ms.name_owner(org["tl"], e, org["om"])
    with pytest.raises(ValidationError):
        ms.close_escalation(org["om"], e, "Fixed")  # CEO not told yet
    Escalation.objects.filter(pk=e.pk).update(ceo_due_at=timezone.now() - datetime.timedelta(minutes=1))
    assert ms.auto_escalate() == 1
    e.refresh_from_db()
    assert e.ceo_auto and e.ceo_informed_at
    ms.close_escalation(org["om"], e, "Mat replaced")
    # Straight to the CEO: the OM (log keeper) doesn't see it, the CEO does.
    d = ms.raise_escalation(org["admin"], kind="conduct", description="About my lead", direct_to_ceo=True)
    assert d.ceo_informed_at is not None
    assert d not in ms.visible_escalations(org["om"])
    assert d in ms.visible_escalations(org["ceo"]) and d in ms.visible_escalations(org["admin"])
    assert e not in ms.visible_escalations(org["admin"])


def test_procedure_versions_are_approved_by_someone_else_and_read_confirmed(org):
    with pytest.raises(PermissionDenied):
        ms.save_procedure(org["coach"], code="EA-X-01", title="X", owner=org["om"])
    p = ms.save_procedure(
        org["om"], code="ea-ops-proc-01", title="Operations", owner=org["om"], audience=["instructor"]
    )
    assert p.code == "EA-OPS-PROC-01"
    v = ms.add_version(org["om"], p, version="1.0", effective_date=TODAY, changes="First")
    with pytest.raises(ValidationError):
        ms.add_version(org["om"], p, version="1.1", effective_date=TODAY, changes="Second")  # one waiting already
    with pytest.raises(PermissionDenied):
        ms.approve_version(org["om"], v)
    ms.approve_version(org["ceo"], v)
    assert p.current == v
    assert v in ms.pending_reads(org["coach"]) and v not in ms.pending_reads(org["admin"])  # audience
    ms.confirm_read(org["coach"], v)
    assert v not in ms.pending_reads(org["coach"])
    status = ms.read_status(v)
    assert {r.user_id for r in status["read"]} == {org["coach"].pk}
    assert org["support"] in status["missing"]


def test_org_chart_and_directory(org):
    chart = ms.org_chart()
    roots = [n["p"].user for n in chart["roots"]]
    assert roots == [org["ceo"]]
    assert any(p.user == org["support"] for p in chart["dotted"])
    assert ms.team_of(org["tl"]) == sorted([org["coach"], org["support"]], key=lambda u: u.full_name)
    assert len(ms.directory()) == 7


def test_quarterly_report_workflow(org, branches):
    start = qbr.last_finished_quarter(TODAY)
    with pytest.raises(PermissionDenied):
        qbr.open_report(org["tl"], start)
    with pytest.raises(ValidationError):
        qbr.open_report(org["om"], qbr.quarter_start(TODAY))  # quarter not over
    r = qbr.open_report(org["om"], start)
    assert r.reference.startswith("RPT-01-") and r.due_date == qbr.quarter_end(start) + datetime.timedelta(days=15)
    with pytest.raises(ValidationError):
        qbr.submit(org["om"], r)  # sections 1 and 2 missing
    qbr.save_text(org["om"], r, summary="Quiet quarter", strategy="Camps", comments={"5": "Room at PRM"})
    data = qbr.build(start)
    assert data["cols"] == ["PRM", "BED", "ALL"]
    if data["income"]["unverified"]:
        with pytest.raises(ValidationError):
            qbr.submit(org["om"], r)  # the difference must be explained
        qbr.save_text(
            org["om"], r, summary="Quiet quarter", strategy="Camps", comments={}, difference_note="Weeks not verified"
        )
    qbr.submit(org["om"], r)
    r.refresh_from_db()
    assert r.status == "submitted" and r.data["label"] == qbr.label(start)
    with pytest.raises(PermissionDenied):
        qbr.approve(org["tl"], r)
    qbr.return_report(org["ceo"], r, "Add the camp numbers")
    r.refresh_from_db()
    assert r.status == "returned"
    qbr.submit(org["om"], r)
    qbr.approve(org["ceo"], QuarterlyReport.objects.get(pk=r.pk))
    assert QuarterlyReport.objects.get(pk=r.pk).status == "approved"
    doc = qbr.document(qbr.figures(QuarterlyReport.objects.get(pk=r.pk)), r, "ar")
    assert sum(1 for b in doc["blocks"] if b[0] == "section") == 11


def test_quarterly_reminders(org):
    start = qbr.last_finished_quarter(TODAY)
    day1 = qbr.quarter_end(start) + datetime.timedelta(days=1)
    assert qbr.remind_quarterly(day1) >= 1
    assert qbr.remind_quarterly(day1 + datetime.timedelta(days=2)) == 0


def test_messages_go_to_staff_whatsapp(org):
    from django.core.cache import cache

    cache.delete(OUTBOX_KEY)
    ms.send_handoff(org["om"], kind="bookings", receiver=org["tl"], subject="Bookings", detail="New slots")
    assert cache.get(OUTBOX_KEY)[0]["to"] == org["tl"].mobile


def test_reporting_lines_cannot_loop(org):
    om = StaffProfile.objects.get(user=org["om"])
    admin = StaffProfile.objects.get(user=org["admin"])
    with pytest.raises(PermissionDenied):
        ms.set_reporting_line(org["coach"], admin, om)
    with pytest.raises(ValidationError):
        ms.set_reporting_line(org["om"], om, admin)  # the admin already reports to the OM
    ms.set_reporting_line(org["om"], admin, om, StaffProfile.objects.get(user=org["tl"]))
    admin.refresh_from_db()
    assert admin.second_lead.user == org["tl"]
