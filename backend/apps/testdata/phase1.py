"""
Phase 1 test data (fictional): rooms, the weekly timetable, four weeks of class history, regular
places, memberships in every state, bookings and a waiting list, discounts, branch stock, and one
of each approval so the Operations Manager's inbox can be demonstrated.
"""

import datetime
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.classes.models import Attendance, Booking, ClassChange, ClassSession, ClassSlot, Enrollment
from apps.classes.services import generate_sessions
from apps.members.models import Member
from apps.organization.models import PriceChange, PricingOption, Program, Room
from apps.renewals.models import FollowUp, InstructorHandoff, ReminderSent
from apps.sales.models import (
    AccountRequest,
    CashUp,
    Discount,
    Freeze,
    Membership,
    Payment,
    ReceiptCounter,
    ReferralCredit,
    Sale,
    SaleLine,
)
from apps.shop.models import BranchStock

TEST_DOMAIN = "test.elite.local"
PACKAGE = re.compile(r"(\d+)\s*(?:x|sessions x)\s*(\d+)", re.IGNORECASE)

# branch, weekday (0=Sat), start, program, title EN, title AR, ages EN, ages AR, age group, focus, coach, capacity
SLOTS = [
    (
        "PRM",
        0,
        "16:30",
        "Elite Program 5-7",
        "Kajukenbo",
        "كاجوكينبو",
        "Kids 5–7",
        "أطفال 5–7",
        "kids",
        "striking",
        "coach.prm",
        16,
    ),
    (
        "PRM",
        1,
        "16:30",
        "Elite Program 5-7",
        "Jiu-Jitsu",
        "جوجيتسو",
        "Kids 5–7",
        "أطفال 5–7",
        "kids",
        "grappling",
        "grappling",
        16,
    ),
    (
        "PRM",
        2,
        "16:30",
        "Elite Program 5-7",
        "Kickboxing",
        "كيك بوكسينغ",
        "Kids 5–7",
        "أطفال 5–7",
        "kids",
        "striking",
        "striking",
        16,
    ),
    (
        "PRM",
        3,
        "16:30",
        "Elite Program 5-7",
        "Jiu-Jitsu",
        "جوجيتسو",
        "Kids 5–7",
        "أطفال 5–7",
        "kids",
        "grappling",
        "grappling",
        16,
    ),
    (
        "PRM",
        4,
        "16:30",
        "Elite Program 5-7",
        "Kajukenbo",
        "كاجوكينبو",
        "Kids 5–7",
        "أطفال 5–7",
        "kids",
        "striking",
        "coach.prm",
        16,
    ),
    (
        "PRM",
        0,
        "17:30",
        "Elite Program 8-12",
        "Kickboxing",
        "كيك بوكسينغ",
        "Kids 8–12",
        "أطفال 8–12",
        "kids",
        "striking",
        "striking",
        18,
    ),
    (
        "PRM",
        1,
        "17:30",
        "Elite Program 8-12",
        "Jiu-Jitsu",
        "جوجيتسو",
        "Kids 8–12",
        "أطفال 8–12",
        "kids",
        "grappling",
        "grappling",
        18,
    ),
    (
        "PRM",
        2,
        "17:30",
        "Elite Program 8-12",
        "Kajukenbo",
        "كاجوكينبو",
        "Kids 8–12",
        "أطفال 8–12",
        "kids",
        "striking",
        "coach.prm",
        18,
    ),
    (
        "PRM",
        3,
        "17:30",
        "Elite Program 8-12",
        "Jiu-Jitsu",
        "جوجيتسو",
        "Kids 8–12",
        "أطفال 8–12",
        "kids",
        "grappling",
        "grappling",
        18,
    ),
    (
        "PRM",
        0,
        "18:30",
        "Jiu-Jitsu 13+",
        "Jiu-Jitsu",
        "جوجيتسو",
        "Teens 13+",
        "ناشئين 13+",
        "teens",
        "grappling",
        "grappling",
        20,
    ),
    (
        "PRM",
        2,
        "18:30",
        "Jiu-Jitsu 13+",
        "Jiu-Jitsu",
        "جوجيتسو",
        "Teens 13+",
        "ناشئين 13+",
        "teens",
        "grappling",
        "grappling",
        20,
    ),
    (
        "PRM",
        1,
        "19:30",
        "Striking",
        "Striking · Adults",
        "ضربات · كبار",
        "Adults",
        "كبار",
        "adults",
        "striking",
        "striking",
        20,
    ),
    (
        "BED",
        0,
        "16:30",
        "Taekwondo Boys",
        "Taekwondo",
        "تايكوندو",
        "Boys 6–13",
        "أولاد 6–13",
        "kids",
        "",
        "coach.free",
        18,
    ),
    (
        "BED",
        2,
        "16:30",
        "Taekwondo Boys",
        "Taekwondo",
        "تايكوندو",
        "Boys 6–13",
        "أولاد 6–13",
        "kids",
        "",
        "coach.free",
        18,
    ),
    (
        "BED",
        4,
        "16:30",
        "Taekwondo Boys",
        "Taekwondo",
        "تايكوندو",
        "Boys 6–13",
        "أولاد 6–13",
        "kids",
        "",
        "coach.free",
        18,
    ),
    (
        "BED",
        0,
        "17:30",
        "Kyokushin Karate",
        "Kyokushin",
        "كيوكوشن",
        "Boys 6–13",
        "أولاد 6–13",
        "kids",
        "",
        "coach.bed1",
        18,
    ),
    (
        "BED",
        2,
        "17:30",
        "Shin-Kyokushin Junior",
        "Shin-Kyokushin",
        "شين كيوكوشن",
        "Boys 6–13",
        "أولاد 6–13",
        "kids",
        "",
        "coach.bed1",
        18,
    ),
    ("BED", 1, "17:30", "Kajukenbo", "Kajukenbo", "كاجوكينبو", "Boys 6–13", "أولاد 6–13", "kids", "", "training", 18),
    ("BED", 3, "17:30", "Kajukenbo", "Kajukenbo", "كاجوكينبو", "Boys 6–13", "أولاد 6–13", "kids", "", "training", 18),
    ("BED", 5, "17:30", "Kickboxing", "Kickboxing", "كيك بوكسينغ", "Adults", "كبار", "adults", "", "striking", 20),
    (
        "BED",
        1,
        "19:30",
        "Ladies' Class",
        "Kickboxing · Ladies",
        "كيك بوكسينغ · سيدات",
        "Girls 6+, women",
        "بنات وسيدات",
        "ladies",
        "",
        "coach.bed2",
        16,
    ),
    (
        "BED",
        3,
        "19:30",
        "Ladies' Class",
        "Kajukenbo · Ladies",
        "كاجوكينبو · سيدات",
        "Girls 6+, women",
        "بنات وسيدات",
        "ladies",
        "",
        "coach.bed2",
        16,
    ),
    (
        "BED",
        5,
        "19:30",
        "Ladies' Class",
        "Kickboxing · Ladies",
        "كيك بوكسينغ · سيدات",
        "Girls 6+, women",
        "بنات وسيدات",
        "ladies",
        "",
        "coach.bed2",
        16,
    ),
]


def reset_phase1():
    for model in (
        Attendance,
        Booking,
        Enrollment,
        ClassChange,
        FollowUp,
        InstructorHandoff,
        ReminderSent,
        Freeze,
        AccountRequest,
        ReferralCredit,
        Payment,
        SaleLine,
        Membership,
        Sale,
        ReceiptCounter,
        CashUp,
        Discount,
        PriceChange,
        BranchStock,
    ):
        model.objects.all().delete()
    ClassSession.objects.all().delete()
    ClassSlot.objects.all().delete()
    Room.objects.all().delete()


class Phase1Data:
    def __init__(self, seed):
        self.rng, self.today, self.branches = seed.rng, seed.today, seed.branches
        self.users = {u.email.split("@")[0]: u for u in get_user_model().objects.filter(email__endswith=TEST_DOMAIN)}

    def load(self):
        self._pricing()
        self._timetable()
        self._memberships_and_places()
        self._history()
        self._bookings()
        self._discounts_and_approvals()

    # ------------------------------------------------------------------
    def _pricing(self):
        for option in PricingOption.objects.all():
            match = PACKAGE.search(option.name)
            if option.kind == "membership" and match:
                option.total_sessions, option.package_weeks = int(match.group(1)), int(match.group(2))
                option.duration_days = None
            option.approval = PricingOption.Approval.APPROVED
            option.all_access = option.name == "Elite Promenade"
            option.save()

    def _timetable(self):
        self.rooms = {}
        for code, branch in self.branches.items():
            self.rooms[code], _ = Room.objects.get_or_create(
                branch=branch, name="Main mat", defaults={"name_ar": "البساط الرئيسي", "capacity": 24}
            )
        self.slots = []
        start_from = self.today - datetime.timedelta(days=28)
        for code, day, start, program, t_en, t_ar, a_en, a_ar, group, focus, coach, cap in SLOTS:
            h, m = (int(x) for x in start.split(":"))
            slot = ClassSlot.objects.create(
                branch=self.branches[code],
                program=Program.objects.get(branch=self.branches[code], name=program),
                room=self.rooms[code],
                title_en=t_en,
                title_ar=t_ar,
                ages_en=a_en,
                ages_ar=a_ar,
                age_group=group,
                focus=focus,
                weekday=day,
                start=datetime.time(h, m),
                end=datetime.time(h + 1, m),
                capacity=cap,
                valid_from=start_from,
                is_sample=True,
            )
            if coach in self.users:
                slot.instructors.add(self.users[coach])
            self.slots.append(slot)
        generate_sessions(start=start_from, days=28 + 28)

    def _slot_for(self, member):
        age = member.age
        options = [s for s in self.slots if s.branch_id == member.branch_id]
        if member.gender == "female" and member.branch.code == "BED":
            fit = [s for s in options if s.age_group == "ladies"]
        elif age >= 18:
            fit = [s for s in options if s.age_group == "adults"]
        elif age >= 13:
            fit = [s for s in options if s.age_group in ("teens", "adults")]
        else:
            fit = [
                s
                for s in options
                if s.age_group == "kids"
                and (s.program.age_min is None or s.program.age_min <= age)
                and (s.program.age_max is None or age <= s.program.age_max)
            ]
            fit = fit or [s for s in options if s.age_group == "kids"]
        return fit

    def _memberships_and_places(self):
        rng, today = self.rng, self.today
        admin = {code: self.users.get(f"admin.{code.lower()}") for code in self.branches}
        options = {
            code: [o for o in PricingOption.objects.filter(branch=b, kind="membership")]
            for code, b in self.branches.items()
        }
        self.regulars = []
        for member in Member.objects.filter(is_active=True).select_related("branch"):
            code = member.branch.code
            state = rng.choices(["active", "expiring", "expired", "old", "none"], weights=[62, 8, 12, 5, 13])[0]
            fit = self._slot_for(member)
            if state != "none" and options[code]:
                option = rng.choice(options[code])
                days = option.validity_days or 30
                end = {
                    "active": today + datetime.timedelta(days=rng.randint(6, days)),
                    "expiring": today + datetime.timedelta(days=rng.randint(0, 5)),
                    "expired": today - datetime.timedelta(days=rng.randint(1, 30)),
                    "old": today - datetime.timedelta(days=rng.randint(45, 200)),
                }[state]
                Membership.objects.create(
                    member=member,
                    branch=member.branch,
                    pricing_option=option,
                    start_date=end - datetime.timedelta(days=days - 1),
                    end_date=end,
                    sessions_total=option.total_sessions,
                    sessions_used=rng.randint(0, (option.total_sessions or 1) - 1) if option.total_sessions else 0,
                    created_by=admin[code],
                    updated_by=admin[code],
                )
            if state in ("active", "expiring", "expired") and fit:
                for slot in rng.sample(fit, k=min(len(fit), rng.choice([1, 2, 2, 3]))):
                    Enrollment.objects.create(member=member, slot=slot, start_date=today - datetime.timedelta(days=60))
                self.regulars.append(member)

    def _history(self):
        """Four weeks of check-ins for regulars (about three in four turn up)."""
        rng, now = self.rng, timezone.now()
        enrolled = {}
        for e in Enrollment.objects.all():
            enrolled.setdefault(e.slot_id, []).append(e.member_id)
        visits = []
        for session in ClassSession.objects.filter(date__lt=self.today).select_related("slot"):
            for member_id in enrolled.get(session.slot_id, []):
                if rng.random() < 0.75:
                    at = session.starts_at - datetime.timedelta(minutes=rng.randint(0, 15))
                    visits.append(
                        Attendance(
                            session=session,
                            member_id=member_id,
                            checked_in_at=min(at, now),
                            method=rng.choice(["desk", "desk", "qr", "coach"]),
                        )
                    )
        Attendance.objects.bulk_create(visits, batch_size=500)

    def _bookings(self):
        rng = self.rng
        upcoming = list(
            ClassSession.objects.filter(
                date__gt=self.today, date__lte=self.today + datetime.timedelta(days=7)
            ).order_by("date", "start")
        )
        admin = self.users.get("admin.prm")
        for session in rng.sample(upcoming, k=min(6, len(upcoming))):
            Booking.objects.create(
                session=session,
                guest_name=rng.choice(["Sara", "Noura", "Fatma", "Abdullah"]) + " (trial)",
                guest_mobile=f"+9655{rng.randint(1000000, 9999999)}",
                is_trial=True,
                source="trial",
                created_by=admin,
                updated_by=admin,
            )
        if upcoming:  # a full class with a waiting list
            full = upcoming[0]
            full.capacity = max(1, full.capacity // 4)
            full.save(update_fields=["capacity"])
            others = Member.objects.filter(branch=full.branch, is_active=True).exclude(enrollments__slot=full.slot_id)[
                : full.capacity + 2
            ]
            for i, member in enumerate(others):
                Booking.objects.create(
                    session=full,
                    member=member,
                    status="booked" if i < full.capacity else "waitlisted",
                    created_by=admin,
                    updated_by=admin,
                )

    def _discounts_and_approvals(self):
        ops = self.users.get("ops")
        Discount.objects.create(
            name="Family (sibling) 10%",
            name_ar="خصم العائلة 10%",
            kind="family",
            percent=Decimal("10"),
            applies_to_kinds=["membership"],
            created_by=ops,
        )
        Discount.objects.create(
            name="Referral reward", name_ar="مكافأة التوصية", kind="referral", amount=Decimal("5.000"), created_by=ops
        )
        Discount.objects.create(
            name="Elite Member tier",
            name_ar="فئة عضو إيليت",
            kind="elite",
            percent=Decimal("0"),
            is_enabled=False,
            created_by=ops,
        )  # rule to be decided (Playbook item 3)
        Discount.objects.create(
            name="Manual discount (with reason)",
            name_ar="خصم يدوي (مع السبب)",
            kind="manual",
            amount=Decimal("5.000"),
            created_by=ops,
        )
        # One of each approval for the demo.
        admin = self.users.get("admin.prm")
        option = PricingOption.objects.filter(branch=self.branches["PRM"], kind="trial").first()
        if option and ops:
            PriceChange.objects.create(
                pricing_option=option,
                old_price=option.price,
                new_price=Decimal("12.000"),
                effective_from=self.today + datetime.timedelta(days=14),
                reason="Test: new season trial price",
                created_by=admin,
            )
        membership = Membership.objects.filter(
            branch=self.branches["PRM"], end_date__gt=self.today + datetime.timedelta(days=10)
        ).first()
        if membership and admin:
            AccountRequest.objects.create(
                kind="freeze",
                membership=membership,
                branch=membership.branch,
                reason="Test: family travel",
                freeze_start=self.today,
                freeze_weeks=2,
                created_by=admin,
                updated_by=admin,
            )
        session = ClassSession.objects.filter(branch=self.branches["BED"], date__gt=self.today).first()
        coach = self.users.get("coach.bed1")
        if session and coach:
            ClassChange.objects.create(
                session=session, kind="cancel", reason="Test: mat maintenance", created_by=coach, updated_by=coach
            )
        # Front-desk stock for the shop's products (if the website seed has created them).
        from apps.shop.models import ProductVariant

        for variant in ProductVariant.objects.all():
            for branch in self.branches.values():
                BranchStock.objects.update_or_create(
                    variant=variant, branch=branch, defaults={"quantity": self.rng.randint(0, 6)}
                )
