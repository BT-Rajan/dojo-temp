"""Phase 4 rules: curriculum, eligibility, evaluations, test days, promotions, belts and progress notes."""

import datetime
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.classes.models import Attendance, ClassSession
from apps.core.messaging import OUTBOX_KEY
from apps.inventory.services import set_opening
from apps.members.models import Guardian, GuardianLink, Member
from apps.organization.models import Discipline, Program
from apps.shop.models import BranchStock, Product, ProductVariant
from apps.training import services as tr
from apps.training.curriculum import SKILLS, load_curriculum
from apps.training.models import Art, MemberRank, ProgressNote, Rank, Skill, SkillCheck

D = Decimal
TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


@pytest.fixture
def s(branches, make_user):
    for code, name, track in [
        ("kajukenbo", "Kajukenbo", "mixed"),
        ("kickboxing", "Kickboxing", "striking"),
        ("jiujitsu", "Jiu-Jitsu", "grappling"),
        ("taekwondo", "Taekwondo", "striking"),
    ]:
        Discipline.objects.create(code=code, name=name, name_ar=name, track=track)
    load_curriculum()
    prm = branches["PRM"]
    program = Program.objects.create(branch=prm, name="Elite Program 8-12", name_ar="برنامج")
    program.disciplines.set(Discipline.objects.filter(code__in=["kajukenbo", "kickboxing", "jiujitsu"]))
    users = {
        "lead": make_user("training_lead"),
        "coach": make_user("instructor", branch=prm),
        "other_coach": make_user("instructor", branch=prm),
        "desk": make_user("branch_admin", branch=prm),
    }
    member = Member.objects.create(
        branch=prm,
        first_name="Salem",
        last_name="Phaseiv",
        date_of_birth=datetime.date(2016, 5, 10),
        gender="male",
        joined_on=TODAY - datetime.timedelta(days=200),
    )
    g = Guardian.objects.create(full_name="Parent Phaseiv", mobile="+96560004444")
    GuardianLink.objects.create(member=member, guardian=g, relationship="father", is_primary=True)
    art = Art.objects.get(code="kajukenbo")
    return {"prm": prm, "program": program, "member": member, "art": art, **users}


def session(s, day, kind="class", points=0, coach=None):
    sess = ClassSession.objects.create(
        branch=s["prm"],
        program=s["program"],
        kind=kind,
        title_en="Kajukenbo",
        date=day,
        start=datetime.time(17, 0),
        end=datetime.time(18, 0),
        seminar_points=points,
    )
    sess.instructors.set([coach or s["coach"]])
    return sess


def attend(s, member, day, **kw):
    Attendance.objects.create(session=session(s, day, **kw), member=member, method="desk")


def outbox():
    return cache.get(OUTBOX_KEY, [])


def rank(s, order):
    return Rank.objects.get(art=s["art"], order=order)


# ---------------------------------------------------------------------------
# Curriculum
# ---------------------------------------------------------------------------
def test_curriculum_loads_the_workbook_once_and_keeps_edits(s):
    art = s["art"]
    assert [r.belt for r in art.ranks.all()] == [
        "white",
        "yellow",
        "purple",
        "blue",
        "green",
        "brown",
        "brownblack",
        "black",
    ]
    assert Skill.objects.filter(rank__art=art).count() == sum(len(v) for v in SKILLS.values())
    yellow = rank(s, 1)
    assert (yellow.stripe, yellow.seminars_required, yellow.min_classes, yellow.min_weeks) == (
        "1 × White stripe",
        2,
        24,
        12,
    )
    assert rank(s, 7).final_exam and rank(s, 7).seminars_required == 12
    jab = Skill.objects.get(rank=rank(s, 0), track__code="kickboxing", name="Jab")
    assert jab.category == "Strikes" and jab.category_ar
    jab.name = "Jab (edited)"
    jab.save()
    assert load_curriculum() == {"arts": 0, "ranks": 0, "skills": 0}
    assert Skill.objects.filter(name="Jab (edited)").exists()
    assert Art.objects.get(code="taekwondo").ranks.count() == 6
    # A member follows Kajukenbo through a program's disciplines.
    attend(s, s["member"], TODAY - datetime.timedelta(days=3))
    assert list(tr.arts_for(s["member"])) == [s["art"]]


# ---------------------------------------------------------------------------
# Eligibility and evaluations
# ---------------------------------------------------------------------------
def test_eligibility_counts_classes_weeks_seminars_and_evaluations(s):
    member, art = s["member"], s["art"]
    mr = tr.member_rank(member, art)
    assert mr.rank.order == 0 and mr.since == member.joined_on
    e = tr.eligibility(member, art)
    assert e["next"] == rank(s, 1) and not e["eligible"]
    for i in range(24):
        attend(s, member, TODAY - datetime.timedelta(days=i * 3 + 1))
    attend(s, member, TODAY - datetime.timedelta(days=40), kind="seminar")  # 1 point (none set)
    attend(s, member, TODAY - datetime.timedelta(days=10), kind="seminar", points=0)
    e = tr.eligibility(member, art)
    checks = {c["code"]: c for c in e["checks"]}
    assert checks["classes"]["have"] == 24 and checks["classes"]["ok"]
    assert checks["weeks"]["ok"] and checks["seminars"]["have"] == 2 and checks["seminars"]["ok"]
    assert not checks["evaluations"]["ok"] and not checks["ready"]["ok"]
    skills = list(tr.skills_for(mr.rank))
    tr.record_evaluation(member, art, s["coach"], {skills[0].pk: 4, skills[1].pk: 2}, notes="Good start")
    assert SkillCheck.objects.filter(member=member, skill=skills[0]).exists()
    assert not SkillCheck.objects.filter(member=member, skill=skills[1]).exists()
    tr.record_evaluation(member, art, s["coach"], {skills[1].pk: 3}, ready=True)
    assert tr.eligibility(member, art)["eligible"]
    assert tr.evaluation_due(member, art)["due"] == TODAY + datetime.timedelta(days=28)
    # Seminars at the member's other academy are added by a lead, with a note.
    with pytest.raises(PermissionDenied):
        tr.add_seminar_credit(member, art, s["coach"], 2, "Earlier seminars")
    with pytest.raises(ValidationError):
        tr.add_seminar_credit(member, art, s["lead"], 2, " ")
    tr.add_seminar_credit(member, art, s["lead"], 2, "Seminars in 2025")
    assert tr.seminar_points(member, art) == 4


def test_only_the_members_instructors_or_leads_evaluate(s):
    member, art = s["member"], s["art"]
    skill = tr.skills_for(tr.member_rank(member, art).rank).first()
    with pytest.raises(PermissionDenied):
        tr.record_evaluation(member, art, s["coach"], {skill.pk: 3})  # hasn't taught this member
    with pytest.raises(PermissionDenied):
        tr.record_evaluation(member, art, s["desk"], {skill.pk: 3})
    attend(s, member, TODAY - datetime.timedelta(days=5))
    assert tr.can_evaluate(s["coach"], member) and not tr.can_evaluate(s["other_coach"], member)
    assert tr.can_evaluate(s["lead"], member)
    with pytest.raises(ValidationError):
        tr.record_evaluation(member, art, s["coach"], {skill.pk: 5})
    with pytest.raises(ValidationError):
        tr.record_evaluation(member, art, s["coach"], {})
    other = Skill.objects.filter(rank__art=art, rank__order=3).first()
    with pytest.raises(ValidationError):
        tr.record_evaluation(member, art, s["coach"], {other.pk: 3})  # not this belt's skill
    with pytest.raises(ValidationError):
        tr.record_evaluation(member, art, s["coach"], {skill.pk: 3}, date=TODAY + datetime.timedelta(days=1))


# ---------------------------------------------------------------------------
# Placement, promotion, belts
# ---------------------------------------------------------------------------
def _belt_stock(s, to_rank, qty=2):
    product = Product.objects.create(
        name_en=f"Kajukenbo {to_rank.name}",
        slug=f"belt-{to_rank.belt}",
        category="belts",
        price=D("4"),
        sell_online=False,
    )
    variant = ProductVariant.objects.create(product=product, size="2", cost=D("1.2"))
    set_opening(variant, s["prm"], qty)
    Rank.objects.filter(pk=to_rank.pk).update(belt_product=product)
    return variant


def test_placement_then_promotion_tells_the_family_and_the_desk_hands_over_the_belt(s):
    member, art = s["member"], s["art"]
    with pytest.raises(ValidationError):
        tr.place(member, art, rank(s, 2), s["lead"], " ")
    with pytest.raises(PermissionDenied):
        tr.place(member, art, rank(s, 2), s["coach"], "Certificate")
    tr.place(member, art, rank(s, 2), s["lead"], "Purple belt certificate from another academy")
    assert tr.member_rank(member, art).rank == rank(s, 2)
    variant = _belt_stock(s, rank(s, 3))
    with pytest.raises(ValidationError):
        tr.promote(member, art, rank(s, 1), s["lead"], note="x")  # not higher
    with pytest.raises(ValidationError):
        tr.promote(member, art, rank(s, 3), s["lead"])  # reason needed outside a test day
    promotion = tr.promote(member, art, rank(s, 3), s["lead"], note="Outstanding at the open mat")
    promotion.refresh_from_db()
    assert promotion.belt_status == "to_issue" and promotion.notified
    assert "الحزام الأزرق" in outbox()[0]["text"] and outbox()[0]["to"] == "+96560004444"
    with pytest.raises(ValidationError):
        tr.place(member, art, rank(s, 1), s["lead"], "Correction")  # after a promotion belts change by promotion
    # The desk hands over the belt: 0 KD free issue from branch stock.
    with pytest.raises(PermissionDenied):
        tr.issue_belt(promotion, s["coach"], variant)
    promotion = tr.issue_belt(promotion, s["desk"], variant)
    line = promotion.sale.lines.get()
    assert promotion.belt_status == "issued" and line.free_issue and line.line_total == 0
    assert BranchStock.objects.get(variant=variant, branch=s["prm"]).quantity == 1
    assert MemberRank.objects.get(member=member, art=art).belt_size == "2"
    with pytest.raises(ValidationError):
        tr.issue_belt(promotion, s["desk"], variant)


# ---------------------------------------------------------------------------
# Test days
# ---------------------------------------------------------------------------
def test_test_day_eligibility_results_and_promotion(s):
    member, art = s["member"], s["art"]
    attend(s, member, TODAY - datetime.timedelta(days=2))
    with pytest.raises(PermissionDenied):
        tr.create_test_day(art, s["prm"], TODAY, s["coach"])
    with pytest.raises(ValidationError):
        tr.create_test_day(art, s["prm"], TODAY - datetime.timedelta(days=1), s["lead"])
    td = tr.create_test_day(art, s["prm"], TODAY, s["lead"], examiners=[s["other_coach"]])
    assert [m for m, e in tr.eligible_members(td)] == [member]
    with pytest.raises(ValidationError):
        tr.add_candidate(td, member, s["lead"])  # not eligible, no reason
    cand = tr.add_candidate(td, member, s["lead"], "Strong evaluations")
    assert not cand.eligible and cand.to_rank == rank(s, 1)
    with pytest.raises(ValidationError):
        tr.add_candidate(td, member, s["lead"], "again")
    with pytest.raises(PermissionDenied):
        tr.record_result(cand, s["coach"], {})  # not an examiner
    with pytest.raises(ValidationError):
        tr.record_result(cand, s["other_coach"], {"kickboxing": "pass"})  # every component
    all_pass = {"kickboxing": "pass", "jiujitsu": "pass", "self_defence": "pass"}
    cand = tr.record_result(cand, s["other_coach"], all_pass)
    assert cand.result == "not_yet" and not cand.seminars_ok  # 0 of 2 seminar points
    with pytest.raises(ValidationError):
        tr.promote_candidate(cand, s["lead"])
    tr.add_seminar_credit(member, art, s["lead"], 2, "Seminars before the system")
    cand = tr.record_result(cand, s["other_coach"], all_pass)
    assert cand.result == "passed"
    with pytest.raises(PermissionDenied):
        tr.promote_candidate(cand, s["other_coach"])
    promotion = tr.promote_candidate(cand, s["lead"])
    assert promotion.kind == "test" and tr.member_rank(member, art).rank == rank(s, 1)
    assert promotion.belt_status == "none"  # no belt linked in stock
    with pytest.raises(ValidationError):
        tr.promote_candidate(cand, s["lead"])
    with pytest.raises(ValidationError):
        tr.record_result(cand, s["other_coach"], all_pass)  # already promoted
    tr.close_test_day(td, s["lead"])
    assert td.status == "done"


def test_a_test_day_closes_only_when_every_result_is_in(s):
    attend(s, s["member"], TODAY - datetime.timedelta(days=2))
    td = tr.create_test_day(s["art"], s["prm"], TODAY, s["lead"])
    cand = tr.add_candidate(td, s["member"], s["lead"], "Try")
    with pytest.raises(ValidationError):
        tr.close_test_day(td, s["lead"])
    tr.record_result(cand, s["lead"], {}, absent=True)
    tr.close_test_day(td, s["lead"])
    with pytest.raises(ValidationError):
        tr.add_candidate(td, s["member"], s["lead"], "late")


def test_tournament_eligibility_follows_the_belt(s):
    rows = tr.tournament(rank(s, 4))
    assert any("Green belt" in en for en, *_ in rows)
    assert any("BJJ Blue (progressing)" in en for en, *_ in rows)


# ---------------------------------------------------------------------------
# Progress notes and reminders
# ---------------------------------------------------------------------------
def test_monthly_progress_notes_are_drafted_and_sent_to_the_guardian(s):
    member, art = s["member"], s["art"]
    last_month = (TODAY.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    for d in (2, 9, 16):
        attend(s, member, last_month + datetime.timedelta(days=d))
    skill = tr.skills_for(tr.member_rank(member, art).rank).first()
    SkillCheck.objects.create(member=member, skill=skill, checked_on=last_month + datetime.timedelta(days=9))
    adult = Member.objects.create(
        branch=s["prm"], first_name="Adult", last_name="Phaseiv", date_of_birth=datetime.date(1990, 1, 1), gender="male"
    )
    attend(s, adult, last_month + datetime.timedelta(days=3))
    assert tr.draft_progress_notes() == 1  # children only
    assert tr.draft_progress_notes() == 0
    note = ProgressNote.objects.get()
    assert note.instructor == s["coach"] and "3 classes" in note.worked_on and skill.name in note.worked_on
    with pytest.raises(PermissionDenied):
        tr.send_progress_note(note, s["other_coach"], "x", "y")
    with pytest.raises(ValidationError):
        tr.send_progress_note(note, s["coach"], " ", "y")
    tr.send_progress_note(note, s["coach"], "Great month", "Round kick")
    note.refresh_from_db()
    assert note.status == "sent" and outbox()[0]["to"] == "+96560004444"
    with pytest.raises(ValidationError):
        tr.send_progress_note(note, s["coach"], "again", "")


def test_evaluation_reminders_go_to_instructors_on_sundays(s):
    member, art = s["member"], s["art"]
    s["coach"].mobile = "+96550001111"
    s["coach"].save()
    attend(s, member, TODAY - datetime.timedelta(days=2))
    tr.member_rank(member, art)  # joined 200 days ago, never evaluated → due
    sunday = TODAY + datetime.timedelta(days=(6 - TODAY.weekday()) % 7)
    monday = sunday + datetime.timedelta(days=1)
    assert tr.evaluation_reminders(monday) == 0
    assert tr.evaluation_reminders(sunday) == 1
    assert outbox()[0]["to"] == "+96550001111"
