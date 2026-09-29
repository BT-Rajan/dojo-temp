"""Phase 4 desk screens, driven as each role would use them (fictional seed data)."""

import pytest
from django.core.management import call_command
from django.test import Client

from apps.members.models import Member
from apps.training import services as tr
from apps.training.models import Art, Evaluation, MemberRank, ProgressNote, Promotion, TestCandidate, TestDay


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


def kaju():
    return Art.objects.get(code="kajukenbo")


def test_every_phase4_screen_renders_in_both_languages(data):
    art = kaju()
    mr = MemberRank.objects.filter(art=art, member__branch__code="PRM").first()
    td = TestDay.objects.filter(branch__code="PRM").first()
    screens = {
        "training": [
            "training/",
            "training/?who=all&show=due",
            "training/curriculum/",
            f"training/curriculum/?art={Art.objects.get(code='taekwondo').pk}",
            f"training/students/{mr.member_id}/{art.pk}/",
            f"training/students/{mr.member_id}/{art.pk}/evaluate/",
            "training/test-days/",
            f"training/test-days/{td.pk}/",
            "training/progress-notes/",
            "training/progress-notes/?status=sent",
        ],
        "coach.prm": ["training/", "training/curriculum/?track=1", "training/progress-notes/"],
        "admin.prm": ["training/belts/", "training/?who=all", f"training/students/{mr.member_id}/{art.pk}/"],
        "ops": ["training/?who=all", "training/test-days/"],
    }
    for who, paths in screens.items():
        client = desk(who)
        for path in paths:
            for lang in ("en", "ar"):
                response = client.get(url(path, lang))
                assert response.status_code == 200, (who, path, lang, response.status_code)
    # The member record shows the belt.
    page = desk("admin.prm").get(url(f"members/{mr.member_id}/")).content.decode()
    assert f"/desk/training/students/{mr.member_id}/{art.pk}/" in page


def test_who_can_do_what(data):
    art = kaju()
    mr = MemberRank.objects.filter(art=art, member__branch__code="PRM").first()
    admin = desk("admin.prm")
    assert admin.get(url(f"training/students/{mr.member_id}/{art.pk}/evaluate/")).status_code == 403
    assert admin.get(url("training/progress-notes/")).status_code == 403
    assert desk("accounts").get(url("training/")).status_code == 403
    assert desk("coach.prm").get(url("training/belts/")).status_code == 403
    # A branch admin can't open another branch's member.
    bed = MemberRank.objects.filter(art=art, member__branch__code="BED").first()
    assert admin.get(url(f"training/students/{bed.member_id}/{art.pk}/")).status_code == 404
    # A coach can't create a test day or edit the curriculum.
    coach = desk("coach.prm")
    coach.post(url("training/test-days/"), {"art": art.pk, "date": "2099-01-01"})
    assert not TestDay.objects.filter(date="2099-01-01").exists()
    skill = art.ranks.first().skills.first()
    r = coach.post(
        url(f"training/curriculum/?art={art.pk}"), {"art": art.pk, "action": "skill", "skill": skill.pk, "name": "X"}
    )
    assert r.status_code == 403


def test_a_training_day_at_the_desk(data):
    art, lead = kaju(), desk("training")
    member = Member.objects.filter(ranks__art=art, branch__code="PRM").first()
    mr = tr.member_rank(member, art)
    skills = list(tr.skills_for(mr.rank))
    # Evaluate
    post = {f"s_{skills[0].pk}": "4", "notes": "Sharp jab", "ready": "1"}
    assert lead.post(url(f"training/students/{member.pk}/{art.pk}/evaluate/"), post).status_code == 302
    ev = Evaluation.objects.filter(member=member).order_by("-pk").first()
    assert ev.notes == "Sharp jab" and ev.ready_for_test
    # Tick skills on the card
    lead.post(
        url(f"training/students/{member.pk}/{art.pk}/"), {"action": "skills", "skill": [s.pk for s in skills[:2]]}
    )
    assert member.skill_checks.filter(skill__in=skills[:2]).count() == 2
    # Curriculum edit by the lead
    lead.post(
        url(f"training/curriculum/?art={art.pk}"),
        {"art": art.pk, "action": "rank", "rank": mr.rank.pk, "min_classes": "30", "min_weeks": "10"},
    )
    mr.rank.refresh_from_db()
    assert mr.rank.min_classes == 30
    # Test day: create, add with a reason, record, promote
    import datetime

    day = datetime.date.today() + datetime.timedelta(days=3)
    lead.post(url("training/test-days/"), {"art": art.pk, "date": day.isoformat(), "title": "Desk test"})
    td = TestDay.objects.get(title="Desk test")
    lead.post(url(f"training/test-days/{td.pk}/"), {"action": "add", "other": member.pk, "reason": "Lead's call"})
    cand = TestCandidate.objects.get(test_day=td, member=member)
    tr.add_seminar_credit(member, art, cand.test_day.created_by, 20, "Enough seminars (test)")
    result = {"action": "result", "candidate": cand.pk, "c_kickboxing": "pass", "c_jiujitsu": "pass"}
    result["c_self_defence"] = "pass"
    lead.post(url(f"training/test-days/{td.pk}/"), result)
    assert TestCandidate.objects.get(pk=cand.pk).result == "passed"
    lead.post(url(f"training/test-days/{td.pk}/"), {"action": "promote", "candidate": cand.pk})
    promotion = Promotion.objects.get(candidate=cand)
    assert tr.member_rank(member, art).rank == cand.to_rank
    # The front desk hands over the belt
    stock = [s for s in tr.belt_variants(promotion) if s.available > 0]
    r = desk("admin.prm").post(url("training/belts/"), {"promotion": promotion.pk, "variant": stock[0].variant_id})
    assert r.status_code == 302 and Promotion.objects.get(pk=promotion.pk).belt_status == "issued"


def test_progress_notes_at_the_desk(data):
    note = ProgressNote.objects.filter(status="draft", instructor__isnull=False).first()
    if note is None:
        pytest.skip("no draft note in this seed")
    who = note.instructor.email.split("@")[0]
    client = desk(who)
    client.post(
        url("training/progress-notes/"),
        {"note": note.pk, "action": "save", "worked_on": "Edited", "next_steps": "Kicks"},
    )
    assert ProgressNote.objects.get(pk=note.pk).worked_on == "Edited"
    client.post(
        url("training/progress-notes/"),
        {"note": note.pk, "action": "send", "worked_on": "Edited", "next_steps": "Kicks"},
    )
    assert ProgressNote.objects.get(pk=note.pk).status == "sent"
