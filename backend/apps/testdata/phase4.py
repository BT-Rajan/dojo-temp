"""
Phase 4 test data (fictional): the curriculum, Kajukenbo belts in stock, belts placed for existing students,
evaluations with skills ticked off, seminar points, one seminar session with check-ins, a test day last week
with promotions (one belt handed over, one waiting at the desk), a test day planned for next week and the
monthly progress notes.

Never loaded in production (seed_kuwait refuses to run there).
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.classes.models import Attendance, ClassSession
from apps.inventory.services import set_opening
from apps.members.models import Member
from apps.organization.models import Program
from apps.shop.models import Product, ProductVariant
from apps.training import services as tr
from apps.training.curriculum import load_curriculum
from apps.training.models import (
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
    Track,
)

TEST_DOMAIN = "test.elite.local"
BELT_SIZES = ["1", "2", "3", "4"]


def reset_phase4():
    """Runs first: promotions point at sales, which Phase 1's reset removes."""
    for model in (
        ProgressNote,
        Promotion,
        TestCandidate,
        TestDay,
        EvaluationScore,
        Evaluation,
        SkillCheck,
        SeminarCredit,
        MemberRank,
        Skill,
        Rank,
        Track,
        Art,
    ):
        model.objects.all().delete()
    ClassSession.objects.filter(kind=ClassSession.Kind.SEMINAR, title_en__endswith="(test)").delete()


class Phase4Data:
    def __init__(self, seed):
        self.rng, self.today, self.branches = seed.rng, seed.today, seed.branches
        self.users = {u.email.split("@")[0]: u for u in get_user_model().objects.filter(email__endswith=TEST_DOMAIN)}
        self.lead = self.users["training"]

    def load(self):
        load_curriculum()
        self.art = Art.objects.get(code="kajukenbo")
        self._belts_in_stock()
        self._students()
        self._seminar()
        self._test_days()
        self._notes()

    # ------------------------------------------------------------------
    def _belts_in_stock(self):
        for rank in self.art.ranks.exclude(order=0):
            product, created = Product.objects.get_or_create(
                slug=f"kajukenbo-belt-{rank.belt}",
                defaults={
                    "name_en": f"Kajukenbo {rank.name}",
                    "name_ar": f"كاجوكينبو {rank.name_ar}",
                    "category": "belts",
                    "price": Decimal("4.000"),
                    "sell_online": False,
                },
            )
            if created:
                for i, size in enumerate(BELT_SIZES):
                    variant = ProductVariant.objects.create(
                        product=product, size=size, sort_order=i, cost=Decimal("1.200"), reorder_level=2, max_level=8
                    )
                    for branch in self.branches.values():
                        set_opening(variant, branch, self.rng.randint(2, 5), note="Opening balance (test data)")
            Rank.objects.filter(pk=rank.pk).update(belt_product=product)

    def _members(self, branch, n):
        out = []
        for m in Member.objects.filter(branch=branch, is_active=True).order_by("pk"):
            if self.art in tr.arts_for(m):
                out.append(m)
            if len(out) >= n:
                break
        return out

    def _students(self):
        """Placement from paper records, then two evaluations each; some ready for their next belt."""
        ranks = list(self.art.ranks.order_by("order"))
        self.ready = {}
        for code, branch in self.branches.items():
            coach = self.users["coach.prm" if code == "PRM" else "coach.bed1"]
            members = self._members(branch, 10)
            for i, member in enumerate(members):
                rank = ranks[min(i % 4, len(ranks) - 2)]
                since = self.today - datetime.timedelta(days=self.rng.randint(110, 220))
                tr.place(member, self.art, rank, self.lead, "Placement from the paper belt records (test)", since)
                MemberRank.objects.filter(member=member, art=self.art).update(belt_size=self.rng.choice(BELT_SIZES))
                skills = list(tr.skills_for(rank))
                nxt = rank.next()
                if nxt and nxt.seminars_required:
                    SeminarCredit.objects.create(
                        member=member,
                        art=self.art,
                        points=nxt.seminars_required,
                        date=since,
                        note="Seminars before the system (test)",
                        created_by=self.lead,
                    )
                ready = i % 3 == 0
                for n, days_ago in enumerate((52, 18)):
                    date = self.today - datetime.timedelta(days=days_ago + self.rng.randint(0, 5))
                    ev = Evaluation.objects.create(
                        member=member,
                        art=self.art,
                        rank=rank,
                        date=date,
                        instructor=coach,
                        notes="Good focus; keep the guard up (test)." if n else "Settling in well (test).",
                        ready_for_test=ready and n == 1,
                        created_by=coach,
                    )
                    for skill in skills:
                        score = self.rng.choice([2, 3, 3, 4]) if n else self.rng.choice([1, 2, 2, 3])
                        EvaluationScore.objects.create(evaluation=ev, skill=skill, score=score)
                        if score >= 3:
                            SkillCheck.objects.get_or_create(
                                member=member,
                                skill=skill,
                                defaults={"checked_by": coach, "checked_on": date, "evaluation": ev},
                            )
                if ready:
                    self.ready.setdefault(code, []).append(member)

    def _seminar(self):
        """Last month's Self-Defence & Traditional seminar at Promenade, with check-ins (counts as points)."""
        program = Program.objects.filter(branch=self.branches["PRM"], disciplines__code="kajukenbo").first()
        if program is None:
            return
        day = (self.today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        while day.weekday() != 5:  # first Saturday
            day += datetime.timedelta(days=1)
        session = ClassSession.objects.create(
            kind=ClassSession.Kind.SEMINAR,
            branch=self.branches["PRM"],
            program=program,
            title_en="Self-Defence & Traditional seminar (test)",
            title_ar="ندوة الدفاع عن النفس والتقليدي (تجريبي)",
            date=day,
            start=datetime.time(16, 0),
            end=datetime.time(18, 30),
            capacity=30,
            seminar_points=1,
        )
        session.instructors.set([self.lead])
        when = timezone.make_aware(datetime.datetime.combine(day, datetime.time(16, 5)))
        for member in self._members(self.branches["PRM"], 6):
            Attendance.objects.create(session=session, member=member, method="desk", checked_in_at=when)

    def _test_days(self):
        prm, bed = self.branches["PRM"], self.branches["BED"]
        examiner = self.users["striking"]
        past = TestDay.objects.create(
            art=self.art,
            branch=prm,
            date=self.today - datetime.timedelta(days=6),
            title="Autumn grading (test)",
            created_by=self.lead,
        )
        past.examiners.set([examiner, self.users["grappling"]])
        promoted = []
        for member in self.ready.get("PRM", [])[:3]:
            cand = tr.add_candidate(past, member, self.lead, "Test data")
            results = {code: "pass" for code, *_ in tr.components(self.art)}
            cand = tr.record_result(cand, examiner, results, notes="Sharp combinations (test).")
            if cand.result == "passed":
                promoted.append(tr.promote_candidate(cand, self.lead))
        if promoted:
            first = promoted[0]
            stock = [s for s in tr.belt_variants(first) if s.available > 0]
            if stock:
                tr.issue_belt(first, self.users["admin.prm"], stock[0].variant)
        TestDay.objects.filter(pk=past.pk).update(status=TestDay.Status.DONE)
        upcoming = tr.create_test_day(
            self.art, bed, self.today + datetime.timedelta(days=8), self.lead, title="Bedaya grading (test)"
        )
        upcoming.examiners.set([self.users["coach.bed1"], self.users["grappling"]])
        for member in self.ready.get("BED", [])[:2]:
            tr.add_candidate(upcoming, member, self.lead, "Strong evaluations; class count nearly there (test)")

    def _notes(self):
        tr.draft_progress_notes()
        note = ProgressNote.objects.filter(status="draft").order_by("pk").first()
        if note is not None and note.instructor is not None:
            tr.send_progress_note(note, note.instructor, note.worked_on, note.next_steps or "Keep training (test).")
