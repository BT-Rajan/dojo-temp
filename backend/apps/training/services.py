"""
Training rules (M7, decisions P4-1 to P4-10): which art a member follows, eligibility for the next belt,
evaluations, test days, promotions and belt hand-over, and the monthly progress note.
"""

import datetime
from collections import Counter

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.classes.models import Attendance, ClassSession, ClassSlot, Enrollment
from apps.core.messaging import send_message
from apps.members.models import Member
from apps.members.services import contact_language, contact_mobile, display_name
from apps.rbac.services import has_perm, notify_perm

from .models import (
    PASS_SCORE,
    Art,
    Evaluation,
    EvaluationScore,
    MemberRank,
    ProgressNote,
    Promotion,
    Rank,
    SeminarCredit,
    Skill,
    SkillCheck,
    TestCandidate,
    TestDay,
)

EVALUATION_DUE_DAYS = 28  # P4-4
EVALUATION_OVERDUE_DAYS = 42
INSTRUCTOR_WINDOW_DAYS = 90  # P4-5
SEMINAR = ClassSession.Kind.SEMINAR


def _need(user, perm, branch_id, message):
    if not has_perm(user, perm, branch_id):
        raise PermissionDenied(message)


def _lang(member):
    return contact_language(member)


# ---------------------------------------------------------------------------
# Which art, which belt
# ---------------------------------------------------------------------------
def _art_sessions(art):
    return Q(session__program__disciplines__in=art.disciplines.all())


def arts_for(member: Member):
    """Arts followed through the programs of the member's regular classes, recent visits or an existing belt."""
    today = timezone.localdate()
    program_ids = set(
        Enrollment.objects.filter(member=member, start_date__lte=today)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .values_list("slot__program_id", flat=True)
    )
    program_ids |= set(
        Attendance.objects.filter(member=member, session__date__gte=today - datetime.timedelta(days=180))
        .exclude(session__program__isnull=True)
        .values_list("session__program_id", flat=True)
    )
    ranked = MemberRank.objects.filter(member=member).values_list("art_id", flat=True)
    return (
        Art.objects.filter(is_active=True)
        .filter(Q(disciplines__programs__in=program_ids) | Q(pk__in=ranked))
        .distinct()
        .order_by("name")
    )


def member_rank(member: Member, art: Art, create=True) -> MemberRank | None:
    mr = MemberRank.objects.filter(member=member, art=art).select_related("rank").first()
    if mr is None and create:
        first = art.first_rank()
        if first is None:
            return None
        mr, _ = MemberRank.objects.get_or_create(
            member=member, art=art, defaults={"rank": first, "since": member.joined_on or timezone.localdate()}
        )
    return mr


def classes_since(member, art, since) -> int:
    return (
        Attendance.objects.filter(member=member, session__date__gte=since)
        .filter(_art_sessions(art))
        .exclude(session__kind=SEMINAR)
        .values("session_id")
        .distinct()
        .count()
    )


def seminar_points(member, art) -> int:
    """Points from check-ins at seminars (the session's points, 1 if none set) plus points added by hand."""
    visits = (
        Attendance.objects.filter(member=member)
        .filter(Q(session__kind=SEMINAR) | Q(session__seminar_points__gt=0))
        .filter(_art_sessions(art))
        .values("session_id", "session__seminar_points")
        .distinct()
    )
    attended = sum(v["session__seminar_points"] or 1 for v in visits)
    added = SeminarCredit.objects.filter(member=member, art=art).aggregate(p=Sum("points"))["p"] or 0
    return attended + added


def evaluations_since(member, art, since):
    return Evaluation.objects.filter(member=member, art=art, date__gte=since).order_by("-date", "-id")


def skills_for(rank: Rank):
    return rank.skills.filter(is_active=True).select_related("track")


def skill_progress(member, rank) -> dict:
    skills = list(skills_for(rank))
    done = set(SkillCheck.objects.filter(member=member, skill__in=skills).values_list("skill_id", flat=True))
    return {"skills": skills, "done": done, "total": len(skills), "count": len(done)}


def eligibility(member, art, today=None) -> dict:
    """P4-3: classes, weeks, seminar total and evaluations since the last promotion."""
    today = today or timezone.localdate()
    mr = member_rank(member, art)
    if mr is None:
        return {"rank": None, "next": None, "eligible": False, "checks": []}
    nxt = mr.rank.next()
    if nxt is None:
        return {"rank": mr.rank, "next": None, "eligible": False, "checks": [], "top": True, "since": mr.since}
    classes = classes_since(member, art, mr.since)
    weeks = (today - mr.since).days // 7
    seminars = seminar_points(member, art)
    evals = list(evaluations_since(member, art, mr.since)[:10])
    ready = bool(evals) and evals[0].ready_for_test
    checks = [
        ("classes", "Classes since last belt", "الحصص منذ آخر حزام", classes, nxt.min_classes),
        ("weeks", "Weeks at this belt", "أسابيع على هذا الحزام", weeks, nxt.min_weeks),
        ("seminars", "Seminars attended (total)", "الندوات المحضورة (الإجمالي)", seminars, nxt.seminars_required),
        ("evaluations", "Evaluations since last belt", "التقييمات منذ آخر حزام", len(evals), nxt.min_evaluations),
    ]
    rows = [
        {"code": c, "en": en, "ar": ar, "have": have, "need": need, "ok": have >= need}
        for c, en, ar, have, need in checks
    ]
    rows.append(
        {
            "code": "ready",
            "en": "Latest evaluation says ready",
            "ar": "آخر تقييم: جاهز للاختبار",
            "have": ready,
            "need": True,
            "ok": ready,
        }
    )
    return {
        "rank": mr.rank,
        "next": nxt,
        "since": mr.since,
        "checks": rows,
        "eligible": all(r["ok"] for r in rows),
        "seminars": seminars,
        "classes": classes,
    }


def evaluation_due(member, art) -> dict:
    mr = member_rank(member, art)
    last = Evaluation.objects.filter(member=member, art=art).order_by("-date").first()
    base = max(last.date, mr.since) if last else mr.since
    due = base + datetime.timedelta(days=EVALUATION_DUE_DAYS)
    today = timezone.localdate()
    return {
        "last": last,
        "due": due,
        "overdue": today > base + datetime.timedelta(days=EVALUATION_OVERDUE_DAYS),
        "is_due": today >= due,
    }


def tournament(rank: Rank | None) -> list[tuple[str, str, str]]:
    """P4-10: what the member can compete in, from the belt."""
    if rank is None:
        return []
    rows = [(f"Kickboxing / Muay Thai: {rank.name} level", f"الكيك بوكسينغ / المواي تاي: مستوى {rank.name_ar}", "")]
    if rank.bjj_equivalent:
        rows.append((f"BJJ / Judo: {rank.bjj_equivalent}", f"الجوجيتسو / الجودو: {rank.bjj_equivalent}", ""))
    rows.append((f"{rank.art.name}: {rank.name}", f"{rank.art.name_ar}: {rank.name_ar}", ""))
    return rows


# ---------------------------------------------------------------------------
# Who may evaluate a member (P4-5)
# ---------------------------------------------------------------------------
def member_instructors(member, since=None):
    from django.contrib.auth import get_user_model

    today = timezone.localdate()
    since = since or today - datetime.timedelta(days=INSTRUCTOR_WINDOW_DAYS)
    slot_ids = (
        Enrollment.objects.filter(member=member)
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .values_list("slot_id", flat=True)
    )
    session_ids = Attendance.objects.filter(member=member, session__date__gte=since).values_list(
        "session_id", flat=True
    )
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(class_slots__in=ClassSlot.objects.filter(pk__in=slot_ids)) | Q(class_sessions__in=session_ids))
        .distinct()
    )


def can_evaluate(user, member) -> bool:
    if has_perm(user, "training.manage", member.branch_id):
        return True
    return has_perm(user, "training.teach", member.branch_id) and member_instructors(member).filter(pk=user.pk).exists()


def _need_evaluator(user, member):
    if not can_evaluate(user, member):
        raise PermissionDenied("Only this member's instructors or a Training / Track Lead can do this.")


# ---------------------------------------------------------------------------
# Evaluations and skills
# ---------------------------------------------------------------------------
@transaction.atomic
def record_evaluation(member, art, user, scores: dict, *, notes="", ready=False, track=None, date=None) -> Evaluation:
    """scores = {skill_id: 1–4}. A skill scored 3 or 4 is ticked off (P4-4)."""
    _need_evaluator(user, member)
    mr = member_rank(member, art)
    if mr is None:
        raise ValidationError("This art has no belts set up yet.")
    allowed = {s.pk: s for s in skills_for(mr.rank)}
    clean = {}
    for skill_id, value in scores.items():
        if value in ("", None):
            continue
        skill = allowed.get(int(skill_id))
        if skill is None:
            raise ValidationError("A score was given for a skill that isn't on this belt.")
        value = int(value)
        if not 1 <= value <= 4:
            raise ValidationError("Scores are 1 to 4.")
        clean[skill] = value
    if not clean and not notes.strip():
        raise ValidationError("Score at least one skill or write a note.")
    date = date or timezone.localdate()
    if date > timezone.localdate():
        raise ValidationError("An evaluation can't be dated in the future.")
    evaluation = Evaluation.objects.create(
        member=member,
        art=art,
        rank=mr.rank,
        track=track,
        date=date,
        instructor=user,
        notes=notes.strip(),
        ready_for_test=bool(ready),
        created_by=user,
        updated_by=user,
    )
    EvaluationScore.objects.bulk_create(
        [EvaluationScore(evaluation=evaluation, skill=s, score=v) for s, v in clean.items()]
    )
    for skill, value in clean.items():
        if value >= PASS_SCORE:
            SkillCheck.objects.get_or_create(
                member=member,
                skill=skill,
                defaults={"checked_by": user, "checked_on": date, "evaluation": evaluation},
            )
    return evaluation


@transaction.atomic
def set_skill(member, skill: Skill, user, done: bool):
    _need_evaluator(user, member)
    if done:
        SkillCheck.objects.get_or_create(member=member, skill=skill, defaults={"checked_by": user})
    else:
        SkillCheck.objects.filter(member=member, skill=skill).delete()


@transaction.atomic
def add_seminar_credit(member, art, user, points: int, note: str, date=None) -> SeminarCredit:
    _need(user, "training.manage", member.branch_id, "Only a Training or Track Lead adds seminar points.")
    if not note.strip():
        raise ValidationError("Say which seminar(s) these points are for.")
    if not 1 <= int(points) <= 20:
        raise ValidationError("Points must be between 1 and 20.")
    return SeminarCredit.objects.create(
        member=member,
        art=art,
        points=int(points),
        date=date or timezone.localdate(),
        note=note.strip()[:200],
        created_by=user,
        updated_by=user,
    )


# ---------------------------------------------------------------------------
# Belts: placement, promotion, hand-over (P4-7, P4-8)
# ---------------------------------------------------------------------------
@transaction.atomic
def place(member, art, rank: Rank, user, note: str, since=None) -> Promotion:
    _need(user, "training.manage", member.branch_id, "Only a Training or Track Lead sets a member's belt.")
    if rank.art_id != art.pk:
        raise ValidationError("Choose a belt of this art.")
    if not note.strip():
        raise ValidationError("Write how the belt was confirmed (e.g. certificate, previous academy, assessment).")
    if Promotion.objects.filter(member=member, art=art).exclude(kind=Promotion.Kind.PLACEMENT).exists():
        raise ValidationError("This member has been promoted in the system already — belts now change by promotion.")
    since = since or timezone.localdate()
    mr = member_rank(member, art)
    previous = mr.rank
    mr.rank, mr.since, mr.updated_by = rank, since, user
    mr.save()
    return Promotion.objects.create(
        member=member,
        art=art,
        from_rank=previous,
        to_rank=rank,
        date=since,
        kind=Promotion.Kind.PLACEMENT,
        branch=member.branch,
        note=note.strip()[:255],
        created_by=user,
        updated_by=user,
    )


def _promotion_message(promotion) -> str:
    member = promotion.member
    lang = _lang(member)
    if lang == "ar":
        return (
            f"مبروك! {display_name(member, 'ar')} نال {promotion.to_rank.name_ar} في {promotion.art.name_ar}. "
            "يُسلَّم الحزام في الاستقبال. — أكاديمية إيليت"
        )
    return (
        f"Congratulations! {display_name(member)} has been promoted to {promotion.to_rank.name} in "
        f"{promotion.art.name}. The belt is ready at the front desk. — Elite Academy"
    )


def _tell_family(promotion_id):
    promotion = Promotion.objects.select_related("member", "to_rank", "art").get(pk=promotion_id)
    mobile = contact_mobile(promotion.member)
    if mobile and send_message(
        mobile, _promotion_message(promotion), category="service", kind="promotion", member=promotion.member
    ):
        Promotion.objects.filter(pk=promotion_id).update(notified=True)


@transaction.atomic
def promote(member, art, to_rank: Rank, user, *, kind=Promotion.Kind.DIRECT, candidate=None, note="", branch=None):
    branch = branch or member.branch
    _need(user, "training.manage", branch.pk, "Only a Training or Track Lead confirms a promotion.")
    mr = MemberRank.objects.select_for_update().get(pk=member_rank(member, art).pk)
    if to_rank.art_id != art.pk or to_rank.order <= mr.rank.order:
        raise ValidationError("Promote to a higher belt of the same art.")
    if kind == Promotion.Kind.DIRECT and not note.strip():
        raise ValidationError("A promotion outside a test day needs a reason.")
    promotion = Promotion.objects.create(
        member=member,
        art=art,
        from_rank=mr.rank,
        to_rank=to_rank,
        kind=kind,
        candidate=candidate,
        branch=branch,
        note=note.strip()[:255],
        belt_status=Promotion.Belt.TO_ISSUE if to_rank.belt_product_id else Promotion.Belt.NONE,
        created_by=user,
        updated_by=user,
    )
    mr.rank, mr.since, mr.updated_by = to_rank, promotion.date, user
    mr.save()
    record_event(action="belt_promotion", instance=promotion, branch_id=branch.pk, changes={"to": to_rank.name})
    transaction.on_commit(lambda: _tell_family(promotion.pk))
    from apps.leads.services import on_promotion

    transaction.on_commit(lambda: on_promotion(promotion.pk))  # Google review request (P5-9)
    if promotion.belt_status == Promotion.Belt.TO_ISSUE:
        text = f"Belt to hand over at {branch.name}: {member} — {to_rank}."
        transaction.on_commit(lambda: notify_perm("sales.sell", text, branch.pk, exclude=user))
    return promotion


def belt_variants(promotion):
    from apps.shop.models import BranchStock

    if not promotion.to_rank.belt_product_id:
        return []
    return [
        s
        for s in BranchStock.objects.filter(
            branch=promotion.branch, variant__product_id=promotion.to_rank.belt_product_id, variant__is_active=True
        )
        .select_related("variant")
        .order_by("variant__sort_order")
    ]


@transaction.atomic
def issue_belt(promotion: Promotion, user, variant):
    """The front desk hands the belt over: a 0 KD free issue from this branch's stock (P4-7)."""
    from apps.sales.services import Cart, Item, sell

    promotion = Promotion.objects.select_for_update().get(pk=promotion.pk)
    if promotion.belt_status != Promotion.Belt.TO_ISSUE:
        raise ValidationError("This belt has already been handed over.")
    if variant.product_id != promotion.to_rank.belt_product_id:
        raise ValidationError("Choose a size of the belt for this promotion.")
    reason = f"Grading belt — {promotion.to_rank.name} ({promotion.date:%d/%m/%Y})"
    sale = sell(
        branch=promotion.branch,
        user=user,
        cart=Cart(items=[Item(variant=variant, free_issue=True, free_issue_reason=reason)]),
        member=promotion.member,
        note=reason,
    )
    promotion.sale, promotion.belt_status, promotion.updated_by = sale, Promotion.Belt.ISSUED, user
    promotion.save()
    MemberRank.objects.filter(member=promotion.member, art=promotion.art).update(belt_size=variant.size)
    return promotion


# ---------------------------------------------------------------------------
# Test days (P4-6)
# ---------------------------------------------------------------------------
def components(art) -> list[tuple[str, str, str]]:
    return [tuple(c) for c in (art.test_components or [["practical", "Practical", "العملي"]])]


@transaction.atomic
def create_test_day(art, branch, date, user, *, title="", examiners=()) -> TestDay:
    _need(user, "training.manage", branch.pk, "Only a Training or Track Lead sets up a test day.")
    if date < timezone.localdate():
        raise ValidationError("Choose today or a later date.")
    td = TestDay.objects.create(
        art=art, branch=branch, date=date, title=title.strip()[:120], created_by=user, updated_by=user
    )
    td.examiners.set(examiners)
    return td


def eligible_members(test_day: TestDay):
    """Members of this branch following the art whose next belt they are eligible for."""
    art = test_day.art
    members = (
        Member.objects.filter(branch=test_day.branch, is_active=True)
        .filter(
            Q(visits__session__program__disciplines__in=art.disciplines.all())
            | Q(enrollments__slot__program__disciplines__in=art.disciplines.all())
            | Q(ranks__art=art)
        )
        .exclude(tests__test_day=test_day)
        .distinct()
        .order_by("first_name", "last_name")
    )
    out = []
    for m in members:
        e = eligibility(m, art)
        if e["next"] is not None:
            out.append((m, e))
    return out


@transaction.atomic
def add_candidate(test_day: TestDay, member, user, override_reason="") -> TestCandidate:
    _need(user, "training.manage", test_day.branch_id, "Only a Training or Track Lead adds students to a test day.")
    if test_day.status != TestDay.Status.PLANNED:
        raise ValidationError("Results have been recorded for this test day.")
    e = eligibility(member, test_day.art)
    if e["next"] is None:
        raise ValidationError(f"{member} is already at the top belt.")
    if not e["eligible"] and not override_reason.strip():
        missing = ", ".join(r["en"] for r in e["checks"] if not r["ok"])
        raise ValidationError(f"{member} isn't eligible yet ({missing}). Give a reason to add them anyway.")
    if TestCandidate.objects.filter(test_day=test_day, member=member).exists():
        raise ValidationError(f"{member} is already on this test day.")
    candidate = TestCandidate.objects.create(
        test_day=test_day,
        member=member,
        from_rank=e["rank"],
        to_rank=e["next"],
        eligible=e["eligible"],
        override_reason=override_reason.strip()[:255],
        created_by=user,
        updated_by=user,
    )
    from apps.notifications.services import render

    lang = _lang(member)
    text = render(
        "test_day_invite",
        lang,
        member=display_name(member, lang),
        art=test_day.art.name_ar if lang == "ar" else test_day.art.name,
        branch=test_day.branch.name_ar if lang == "ar" else test_day.branch.name,
        date=f"{test_day.date:%d/%m/%Y}",
    )
    mobile = contact_mobile(member)
    if mobile:
        transaction.on_commit(
            lambda: send_message(mobile, text, category="service", kind="test_day_invite", member=member)
        )
    return candidate


def _can_examine(user, test_day):
    return has_perm(user, "training.manage", test_day.branch_id) or (
        has_perm(user, "training.teach", test_day.branch_id) and test_day.examiners.filter(pk=user.pk).exists()
    )


@transaction.atomic
def record_result(candidate: TestCandidate, user, results: dict, *, notes="", absent=False) -> TestCandidate:
    """results = {component: "pass" | "fail"}; the seminar check is worked out by the system."""
    candidate = TestCandidate.objects.select_for_update().select_related("test_day__art").get(pk=candidate.pk)
    td = candidate.test_day
    if not _can_examine(user, td):
        raise PermissionDenied("Only this test day's examiners or a Training / Track Lead record results.")
    if hasattr(candidate, "promotion"):
        raise ValidationError("This student has already been promoted.")
    candidate.seminars_ok = seminar_points(candidate.member, td.art) >= candidate.to_rank.seminars_required
    if absent:
        candidate.result, candidate.components = TestCandidate.Result.ABSENT, {}
    else:
        codes = [c for c, *_ in components(td.art)]
        clean = {}
        for code in codes:
            value = results.get(code, "")
            if value not in ("pass", "fail"):
                raise ValidationError("Record pass or not yet for every part of the test.")
            clean[code] = value
        candidate.components = clean
        passed = all(v == "pass" for v in clean.values()) and candidate.seminars_ok
        candidate.result = TestCandidate.Result.PASSED if passed else TestCandidate.Result.NOT_YET
    candidate.notes, candidate.recorded_by, candidate.updated_by = notes.strip(), user, user
    candidate.save()
    return candidate


@transaction.atomic
def promote_candidate(candidate: TestCandidate, user) -> Promotion:
    candidate = TestCandidate.objects.select_for_update().select_related("test_day", "member").get(pk=candidate.pk)
    if candidate.result != TestCandidate.Result.PASSED:
        raise ValidationError("Only a student who passed every part can be promoted.")
    if Promotion.objects.filter(candidate=candidate).exists():
        raise ValidationError("Already promoted.")
    mr = member_rank(candidate.member, candidate.test_day.art)
    if mr.rank_id != candidate.from_rank_id:
        raise ValidationError("The member's belt changed since they were added to this test day.")
    return promote(
        candidate.member,
        candidate.test_day.art,
        candidate.to_rank,
        user,
        kind=Promotion.Kind.TEST,
        candidate=candidate,
        branch=candidate.test_day.branch,
        note=f"Test day {candidate.test_day.date:%d/%m/%Y}",
    )


@transaction.atomic
def close_test_day(test_day: TestDay, user) -> TestDay:
    _need(user, "training.manage", test_day.branch_id, "Only a Training or Track Lead closes a test day.")
    if test_day.candidates.filter(result=TestCandidate.Result.PENDING).exists():
        raise ValidationError("Record a result (or absent) for every student first.")
    test_day.status, test_day.updated_by = TestDay.Status.DONE, user
    test_day.save()
    return test_day


# ---------------------------------------------------------------------------
# Monthly progress note (P4-9) and reminders (P4-4)
# ---------------------------------------------------------------------------
def _month_bounds(month):
    first = month.replace(day=1)
    return first, (first + datetime.timedelta(days=32)).replace(day=1)


def draft_note_text(member, art, month):
    first, nxt = _month_bounds(month)
    mr = member_rank(member, art)
    checked = SkillCheck.objects.filter(member=member, skill__rank__art=art, checked_on__gte=first, checked_on__lt=nxt)
    worked = [c.skill.name for c in checked.select_related("skill")]
    classes = (
        Attendance.objects.filter(member=member, session__date__gte=first, session__date__lt=nxt)
        .filter(_art_sessions(art))
        .exclude(session__kind=SEMINAR)
        .values("session_id")
        .distinct()
        .count()
    )
    progress = skill_progress(member, mr.rank)
    left = [s.name for s in progress["skills"] if s.pk not in progress["done"]][:5]
    worked_on = f"{classes} classes this month."
    if worked:
        worked_on += " New skills: " + ", ".join(worked) + "."
    e = eligibility(member, art)
    nxt_rank = e.get("next")
    next_steps = ""
    if left:
        next_steps = "Working on: " + ", ".join(left) + "."
    if nxt_rank is not None:
        need = [r["en"].lower() for r in e["checks"] if not r["ok"] and r["code"] != "ready"]
        next_steps += f" Next belt: {nxt_rank.name}" + (f" (still needed: {', '.join(need)})." if need else ".")
    return worked_on.strip(), next_steps.strip()


def draft_progress_notes(month=None) -> int:
    """On the 1st: a draft for each child who trained in an art last month, for their main instructor."""
    today = timezone.localdate()
    month = month or (today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    first, nxt = _month_bounds(month)
    made = 0
    for art in Art.objects.filter(is_active=True).prefetch_related("disciplines"):
        visits = (
            Attendance.objects.filter(session__date__gte=first, session__date__lt=nxt, member__isnull=False)
            .filter(_art_sessions(art))
            .select_related("member")
        )
        by_member = {}
        for v in visits.distinct():
            sessions = by_member.setdefault(v.member_id, (v.member, set()))[1]
            sessions.add(v.session_id)
        for member, sessions in by_member.values():
            if not member.is_minor or ProgressNote.objects.filter(member=member, art=art, month=first).exists():
                continue
            teachers = Counter(
                ClassSession.instructors.through.objects.filter(classsession_id__in=sessions).values_list(
                    "user_id", flat=True
                )
            )
            worked_on, next_steps = draft_note_text(member, art, first)
            ProgressNote.objects.create(
                member=member,
                art=art,
                month=first,
                instructor_id=teachers.most_common(1)[0][0] if teachers else None,
                worked_on=worked_on,
                next_steps=next_steps,
            )
            made += 1
    return made


@transaction.atomic
def send_progress_note(note: ProgressNote, user, worked_on: str, next_steps: str) -> ProgressNote:
    note = ProgressNote.objects.select_for_update().select_related("member", "art").get(pk=note.pk)
    _need_evaluator(user, note.member)
    if note.status == ProgressNote.Status.SENT:
        raise ValidationError("This note has already been sent.")
    if not worked_on.strip():
        raise ValidationError("Write what the student worked on.")
    note.worked_on, note.next_steps = worked_on.strip(), next_steps.strip()
    note.status, note.sent_at, note.instructor, note.updated_by = ProgressNote.Status.SENT, timezone.now(), user, user
    note.save()
    member = note.member
    mobile = contact_mobile(member)
    if _lang(member) == "ar":
        text = (
            f"تقرير {note.month:%m/%Y} — {display_name(member, 'ar')} ({note.art.name_ar}):\n"
            f"ما تدرّب عليه: {note.worked_on}\nالخطوة القادمة: {note.next_steps}\n— أكاديمية إيليت"
        )
    else:
        text = (
            f"{note.month:%B %Y} progress — {display_name(member)} ({note.art.name}):\n"
            f"Worked on: {note.worked_on}\nNext: {note.next_steps}\n— Elite Academy"
        )
    if mobile:
        transaction.on_commit(
            lambda: send_message(mobile, text, category="service", kind="progress_note", member=member)
        )
    return note


def evaluation_reminders(today=None) -> int:
    """Sundays: one message per instructor listing their students due or overdue for an evaluation."""
    today = today or timezone.localdate()
    if today.weekday() != 6:
        return 0
    due = Counter()
    for mr in MemberRank.objects.filter(member__is_active=True).select_related("member", "art"):
        info = evaluation_due(mr.member, mr.art)
        if info["is_due"]:
            for teacher in member_instructors(mr.member):
                if has_perm(teacher, "training.teach"):
                    due[teacher] += 1
    for teacher, n in due.items():
        if teacher.mobile:
            send_message(
                teacher.mobile,
                f"{n} of your students are due an evaluation — see Training in the desk.",
                category="staff",
                kind="evaluations_due",
            )
    return len(due)


def daily_jobs(today=None) -> dict:
    today = today or timezone.localdate()
    return {
        "evaluation_reminders": evaluation_reminders(today),
        "progress_notes_drafted": draft_progress_notes() if today.day == 1 else 0,
    }
