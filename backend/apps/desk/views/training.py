"""Training and progression (M7): curriculum, students, progress cards, evaluations, test days, belts, notes."""

import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.members.models import Member
from apps.rbac.services import has_perm, users_with_perm
from apps.shop.models import Product, ProductVariant
from apps.training import services as tr
from apps.training.models import (
    SCORES,
    Art,
    Evaluation,
    MemberRank,
    ProgressNote,
    Promotion,
    Rank,
    Skill,
    SkillCheck,
    TestCandidate,
    TestDay,
    Track,
)

from ..access import L, can, desk
from ..lookup import visible_members
from .ops import _date

ANY = ["training.view", "training.teach", "training.manage"]


def _arts():
    return Art.objects.filter(is_active=True).order_by("name")


def _art(request):
    arts = list(_arts())
    wanted = request.GET.get("art") or request.POST.get("art")
    for a in arts:
        if str(a.pk) == str(wanted) or a.code == wanted:
            return a, arts
    return (next((a for a in arts if a.code == "kajukenbo"), arts[0] if arts else None)), arts


def _member(request, pk):
    member = get_object_or_404(visible_members(request.user).select_related("branch"), pk=pk)
    if not any(has_perm(request.user, p, member.branch_id) for p in ANY):
        raise Http404
    return member


# ---------------------------------------------------------------------------
# Curriculum (the track sheets)
# ---------------------------------------------------------------------------
@desk(any_of=ANY)
def curriculum(request):
    art, arts = _art(request)
    if art is None:
        return render(request, "desk/training/curriculum.html", {"arts": [], "art": None})
    editable = can(request, "training.manage")
    if request.method == "POST":
        if not editable:
            raise PermissionDenied
        p = request.POST
        if p.get("action") == "rank":
            rank = get_object_or_404(Rank, pk=p.get("rank"), art=art)
            for field in ("min_classes", "min_weeks", "min_evaluations", "seminars_required"):
                value = p.get(field, "")
                if value.isdigit():
                    setattr(rank, field, int(value))
            rank.belt_product = Product.objects.filter(pk=p.get("belt_product") or 0, category="belts").first()
            rank.updated_by = request.user
            rank.save()
        elif p.get("action") == "skill":
            skill = Skill.objects.filter(pk=p.get("skill") or 0, rank__art=art).first()
            if skill is None:
                skill = Skill(
                    rank=get_object_or_404(Rank, pk=p.get("rank"), art=art),
                    track=get_object_or_404(Track, pk=p.get("track"), art=art),
                )
            name = p.get("name", "").strip()
            if not name:
                messages.error(request, L("Enter the skill.", "أدخل المهارة."))
                return redirect(f"{request.path}?art={art.pk}")
            skill.name, skill.name_ar = name[:120], p.get("name_ar", "").strip()[:120]
            skill.category = (p.get("category", "").strip() or skill.category or "General")[:40]
            skill.is_active = p.get("is_active", "1") == "1"
            skill.save()
        messages.success(request, L("Curriculum saved.", "تم حفظ المنهج."))
        return redirect(f"{request.path}?art={art.pk}")
    tracks = list(art.tracks.all())
    track = next((t for t in tracks if str(t.pk) == request.GET.get("track")), None)
    ranks = []
    for rank in art.ranks.all():
        skills = rank.skills.select_related("track")
        if not editable:
            skills = skills.filter(is_active=True)
        if track is not None:
            skills = skills.filter(track=track)
        groups = {}
        for s in skills:
            groups.setdefault((s.track, s.category, s.category_ar), []).append(s)
        ranks.append((rank, sorted(groups.items(), key=lambda g: (g[0][0].order, min(s.order for s in g[1])))))
    return render(
        request,
        "desk/training/curriculum.html",
        {
            "art": art,
            "arts": arts,
            "tracks": tracks,
            "track": track,
            "ranks": ranks,
            "editable": editable,
            "belt_products": Product.objects.filter(category="belts", is_active=True) if editable else [],
        },
    )


# ---------------------------------------------------------------------------
# Students and progress cards
# ---------------------------------------------------------------------------
@desk(any_of=ANY)
def students(request):
    art, arts = _art(request)
    if art is None:
        raise Http404
    mine = request.GET.get("who", "mine" if not can(request, "training.manage") else "all") == "mine"
    today = timezone.localdate()
    recent = today - datetime.timedelta(days=90)
    discs = art.disciplines.all()
    qs = (
        visible_members(request.user)
        .filter(branch=request.branch, is_active=True)
        .filter(
            Q(enrollments__slot__program__disciplines__in=discs, enrollments__end_date__isnull=True)
            | Q(visits__session__program__disciplines__in=discs, visits__session__date__gte=recent)
            | Q(ranks__art=art)
        )
        .distinct()
        .order_by("first_name", "last_name")
    )
    if mine:
        qs = qs.filter(
            Q(enrollments__slot__instructors=request.user, enrollments__end_date__isnull=True)
            | Q(visits__session__instructors=request.user, visits__session__date__gte=recent)
        ).distinct()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(first_name_ar__icontains=q))
    show = request.GET.get("show", "")
    rows = []
    for m in qs[:200]:
        mr = tr.member_rank(m, art)
        if mr is None:
            continue
        e = tr.eligibility(m, art)
        due = tr.evaluation_due(m, art)
        if show == "due" and not due["is_due"]:
            continue
        if show == "eligible" and not e["eligible"]:
            continue
        rows.append({"m": m, "mr": mr, "e": e, "due": due})
    return render(
        request,
        "desk/training/students.html",
        {"art": art, "arts": arts, "rows": rows, "mine": mine, "q": q, "show": show},
    )


@desk(any_of=ANY)
def progress_card(request, pk, art_id):
    member = _member(request, pk)
    art = get_object_or_404(Art, pk=art_id)
    mr = tr.member_rank(member, art)
    if mr is None:
        raise Http404
    evaluator = tr.can_evaluate(request.user, member)
    manager = has_perm(request.user, "training.manage", member.branch_id)
    if request.method == "POST":
        p = request.POST
        action = p.get("action")
        if action == "skills":
            if not evaluator:
                raise PermissionDenied
            ticked = set(p.getlist("skill"))
            for skill in tr.skills_for(mr.rank):
                tr.set_skill(member, skill, request.user, str(skill.pk) in ticked)
            messages.success(request, L("Skills updated.", "تم تحديث المهارات."))
        elif action == "place":
            rank = get_object_or_404(Rank, pk=p.get("rank"), art=art)
            tr.place(member, art, rank, request.user, p.get("note", ""), _date(p.get("since")))
            messages.success(request, L("Belt set.", "تم تحديد الحزام."))
        elif action == "seminar":
            tr.add_seminar_credit(member, art, request.user, int(p.get("points") or 1), p.get("note", ""))
            messages.success(request, L("Seminar points added.", "أُضيفت نقاط الندوات."))
        elif action == "promote":
            rank = get_object_or_404(Rank, pk=p.get("rank"), art=art)
            tr.promote(member, art, rank, request.user, note=p.get("note", ""), branch=request.branch)
            messages.success(request, L("Promoted. The family has been told.", "تمت الترقية وإبلاغ العائلة."))
        return redirect("desk:progress_card", pk=pk, art_id=art.pk)
    progress = tr.skill_progress(member, mr.rank)
    groups = {}
    for s in progress["skills"]:
        groups.setdefault((s.track, s.category, s.category_ar), []).append(s)
    has_promotions = Promotion.objects.filter(member=member, art=art).exclude(kind="placement").exists()
    return render(
        request,
        "desk/training/card.html",
        {
            "member": member,
            "art": art,
            "mr": mr,
            "e": tr.eligibility(member, art),
            "due": tr.evaluation_due(member, art),
            "groups": sorted(groups.items(), key=lambda g: (g[0][0].order, min(s.order for s in g[1]))),
            "progress": progress,
            "tournament": tr.tournament(mr.rank),
            "evaluations": Evaluation.objects.filter(member=member, art=art).select_related("instructor", "rank")[:12],
            "promotions": Promotion.objects.filter(member=member, art=art).select_related("from_rank", "to_rank"),
            "seminars": tr.seminar_points(member, art),
            "credits": member.seminar_credits.filter(art=art)[:10],
            "evaluator": evaluator,
            "manager": manager,
            "can_place": manager and not has_promotions,
            "ranks": art.ranks.all(),
            "higher": art.ranks.filter(order__gt=mr.rank.order),
            "other_arts": tr.arts_for(member).exclude(pk=art.pk),
            "today": timezone.localdate(),
        },
    )


@desk(any_of=["training.teach", "training.manage"])
def evaluate(request, pk, art_id):
    member = _member(request, pk)
    art = get_object_or_404(Art, pk=art_id)
    if not tr.can_evaluate(request.user, member):
        raise PermissionDenied
    mr = tr.member_rank(member, art)
    tracks = list(art.tracks.all())
    track = next((t for t in tracks if str(t.pk) == (request.GET.get("track") or request.POST.get("track"))), None)
    skills = tr.skills_for(mr.rank)
    if track is not None:
        skills = skills.filter(track=track)
    if request.method == "POST":
        scores = {s.pk: request.POST.get(f"s_{s.pk}", "") for s in skills}
        tr.record_evaluation(
            member,
            art,
            request.user,
            scores,
            notes=request.POST.get("notes", ""),
            ready=request.POST.get("ready") == "1",
            track=track,
            date=_date(request.POST.get("date"), timezone.localdate()),
        )
        messages.success(request, L("Evaluation saved.", "تم حفظ التقييم."))
        return redirect("desk:progress_card", pk=pk, art_id=art.pk)
    done = set(SkillCheck.objects.filter(member=member, skill__in=skills).values_list("skill_id", flat=True))
    return render(
        request,
        "desk/training/evaluate.html",
        {
            "member": member,
            "art": art,
            "mr": mr,
            "skills": skills,
            "done": done,
            "scores": SCORES,
            "tracks": tracks,
            "track": track,
            "today": timezone.localdate(),
        },
    )


# ---------------------------------------------------------------------------
# Test days
# ---------------------------------------------------------------------------
@desk(any_of=ANY)
def test_days(request):
    if request.method == "POST":
        if not can(request, "training.manage"):
            raise PermissionDenied
        art = get_object_or_404(Art, pk=request.POST.get("art"))
        examiners = get_user_model().objects.filter(pk__in=request.POST.getlist("examiners"), is_active=True)
        td = tr.create_test_day(
            art,
            request.branch,
            _date(request.POST.get("date"), timezone.localdate()),
            request.user,
            title=request.POST.get("title", ""),
            examiners=examiners,
        )
        return redirect("desk:test_day", pk=td.pk)
    days = TestDay.objects.filter(branch=request.branch).select_related("art").prefetch_related("candidates")[:40]
    return render(
        request,
        "desk/training/test_days.html",
        {
            "days": days,
            "arts": _arts(),
            "coaches": users_with_perm("training.teach", request.branch.pk).order_by("full_name"),
            "can_create": can(request, "training.manage"),
            "today": timezone.localdate(),
        },
    )


@desk(any_of=ANY)
def test_day(request, pk):
    td = get_object_or_404(TestDay.objects.select_related("art", "branch"), pk=pk)
    if not any(has_perm(request.user, p, td.branch_id) for p in ANY):
        raise Http404
    manager = has_perm(request.user, "training.manage", td.branch_id)
    examiner = tr._can_examine(request.user, td)
    if request.method == "POST":
        p = request.POST
        action = p.get("action")
        if action == "add":
            for member in Member.objects.filter(pk__in=p.getlist("members"), branch=td.branch):
                tr.add_candidate(td, member, request.user)
            other = Member.objects.filter(pk=p.get("other") or 0, branch=td.branch).first()
            if other is not None:
                tr.add_candidate(td, other, request.user, p.get("reason", ""))
        elif action == "result":
            cand = get_object_or_404(TestCandidate, pk=p.get("candidate"), test_day=td)
            results = {code: p.get(f"c_{code}", "") for code, *_ in tr.components(td.art)}
            tr.record_result(cand, request.user, results, notes=p.get("notes", ""), absent=p.get("absent") == "1")
        elif action == "promote":
            cand = get_object_or_404(TestCandidate, pk=p.get("candidate"), test_day=td)
            tr.promote_candidate(cand, request.user)
            messages.success(request, L("Promoted. The family has been told.", "تمت الترقية وإبلاغ العائلة."))
        elif action == "close":
            tr.close_test_day(td, request.user)
        return redirect("desk:test_day", pk=pk)
    candidates = td.candidates.select_related("member", "from_rank", "to_rank").prefetch_related("promotion")
    rows = []
    for c in candidates:
        promoted = Promotion.objects.filter(candidate=c).exists()
        rows.append({"c": c, "seminars": tr.seminar_points(c.member, td.art), "promoted": promoted})
    eligible = tr.eligible_members(td) if manager and td.status == "planned" else []
    return render(
        request,
        "desk/training/test_day.html",
        {
            "td": td,
            "rows": rows,
            "components": tr.components(td.art),
            "eligible": [(m, e) for m, e in eligible if e["eligible"]],
            "not_eligible": [(m, e) for m, e in eligible if not e["eligible"]],
            "manager": manager,
            "examiner": examiner,
        },
    )


# ---------------------------------------------------------------------------
# Belts to hand over (front desk) and monthly progress notes
# ---------------------------------------------------------------------------
@desk("sales.sell")
def belts(request):
    if request.method == "POST":
        promotion = get_object_or_404(Promotion, pk=request.POST.get("promotion"), branch=request.branch)
        variant = get_object_or_404(ProductVariant, pk=request.POST.get("variant") or 0)
        tr.issue_belt(promotion, request.user, variant)
        messages.success(request, L("Belt handed over; stock updated.", "تم تسليم الحزام وتحديث المخزون."))
        return redirect("desk:belts")
    waiting = Promotion.objects.filter(branch=request.branch, belt_status="to_issue").select_related(
        "member", "to_rank", "art"
    )
    rows = []
    for p in waiting:
        mr = MemberRank.objects.filter(member=p.member, art=p.art).first()
        rows.append({"p": p, "stock": tr.belt_variants(p), "size": mr.belt_size if mr else ""})
    done = Promotion.objects.filter(branch=request.branch, belt_status="issued").select_related(
        "member", "to_rank", "sale"
    )[:20]
    return render(request, "desk/training/belts.html", {"rows": rows, "done": done})


@desk(any_of=["training.teach", "training.manage"])
def notes(request):
    manager = can(request, "training.manage")
    if request.method == "POST":
        note = get_object_or_404(ProgressNote, pk=request.POST.get("note"))
        if request.POST.get("action") == "save":
            if not tr.can_evaluate(request.user, note.member):
                raise PermissionDenied
            note.worked_on = request.POST.get("worked_on", "").strip()
            note.next_steps = request.POST.get("next_steps", "").strip()
            note.updated_by = request.user
            note.save()
            messages.success(request, L("Saved.", "تم الحفظ."))
        else:
            tr.send_progress_note(
                note, request.user, request.POST.get("worked_on", ""), request.POST.get("next_steps", "")
            )
            messages.success(request, L("Sent to the family.", "أُرسل إلى العائلة."))
        return redirect(request.get_full_path())
    status = request.GET.get("status", "draft")
    qs = ProgressNote.objects.filter(member__branch=request.branch, status=status).select_related(
        "member", "art", "instructor"
    )
    if not manager or request.GET.get("who") == "mine":
        qs = qs.filter(instructor=request.user)
    return render(request, "desk/training/notes.html", {"notes": qs[:60], "status": status, "manager": manager})
