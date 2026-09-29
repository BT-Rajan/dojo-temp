"""
Loads the Kuwait test data package (EA-SYS-SCOPE-01 M21) into a development or test database.

    python manage.py seed_kuwait            # add data
    python manage.py seed_kuwait --reset    # wipe seeded data first

Refuses to run in production.
"""

import datetime
import random
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.members.models import EmergencyContact, Guardian, GuardianLink, MediaConsent, Member
from apps.organization.models import Branch, Discipline, PricingOption, Program
from apps.rbac.models import Role, RoleAssignment
from apps.rbac.sync import sync_rbac
from apps.staff.models import StaffProfile
from apps.testdata import kuwait as kw

TEST_EMAIL_DOMAIN = "test.elite.local"
DEV_PASSWORD = "Elite-Test-2026!"  # nosec B105 - fictional test accounts, never in production

DISCIPLINES = [
    ("kajukenbo", "Kajukenbo", "كاجوكينبو", "mixed"),
    ("kickboxing", "Kickboxing", "كيك بوكسينغ", "striking"),
    ("jiujitsu", "Jiu-Jitsu", "جوجيتسو", "grappling"),
    ("grappling", "Grappling", "المصارعة الأرضية", "grappling"),
    ("striking", "Striking", "الضربات", "striking"),
    ("taekwondo", "Taekwondo", "تايكوندو", "striking"),
    ("kyokushin", "Kyokushin Karate", "كيوكوشن كاراتيه", "striking"),
    ("shin_kyokushin", "Shin-Kyokushin", "شين كيوكوشن", "striking"),
    ("systema", "Systema", "سيستيما", "other"),
]

# branch, name, name_ar, disciplines, audience, age_min, age_max
PROGRAMS = [
    ("PRM", "Elite Program 5-7", "برنامج إيليت 5-7", ["kajukenbo", "kickboxing", "jiujitsu"], "any", 5, 7),
    ("PRM", "Elite Program 8-12", "برنامج إيليت 8-12", ["kajukenbo", "kickboxing", "jiujitsu"], "any", 8, 12),
    ("PRM", "Jiu-Jitsu 13+", "جوجيتسو 13+", ["jiujitsu"], "any", 13, None),
    ("PRM", "Grappling", "المصارعة الأرضية", ["grappling"], "any", 8, None),
    ("PRM", "Striking", "الضربات", ["striking", "kickboxing"], "any", 8, None),
    ("BED", "Taekwondo Boys", "تايكوندو أولاد", ["taekwondo"], "boys", 6, 13),
    ("BED", "Kyokushin Karate", "كيوكوشن كاراتيه", ["kyokushin"], "any", 6, None),
    ("BED", "Shin-Kyokushin Junior", "شين كيوكوشن ناشئين", ["shin_kyokushin"], "boys", 6, 13),
    ("BED", "Kickboxing", "كيك بوكسينغ", ["kickboxing"], "any", 10, None),
    ("BED", "Kajukenbo", "كاجوكينبو", ["kajukenbo"], "any", 6, None),
    ("BED", "Ladies' Class", "كلاس السيدات", ["kickboxing", "kajukenbo"], "ladies", 6, None),
]

# branch, name, kind, price, days, programs
PRICING = [
    ("PRM", "Elite Promenade", "membership", "85.000", 30, ["Elite Program 5-7", "Elite Program 8-12"]),
    ("PRM", "Elite Promenade - Grappling", "membership", "85.000", 30, ["Grappling", "Jiu-Jitsu 13+"]),
    ("PRM", "Elite Promenade - Striking", "membership", "85.000", 30, ["Striking"]),
    ("PRM", "Trial Pass", "trial", "10.000", 7, []),
    ("PRM", "Day Pass", "day_pass", "8.000", 1, []),
    ("PRM", "Private Session", "private", "25.000", 30, []),
    ("PRM", "Summer Camp", "camp", "120.000", 30, []),
    ("BED", "Kajukenbo Fixed Membership 10 x 4", "membership", "65.000", 30, ["Kajukenbo"]),
    ("BED", "Kickboxing - 10x4", "membership", "65.000", 30, ["Kickboxing"]),
    ("BED", "TKD - 10 sessions x 4 weeks", "membership", "65.000", 30, ["Taekwondo Boys"]),
    ("BED", "Kyokushin Karate - 10 sessions x 4 weeks", "membership", "65.000", 30, ["Kyokushin Karate"]),
    ("BED", "Shin-Kyokushin - 10x4", "membership", "65.000", 30, ["Shin-Kyokushin Junior"]),
    ("BED", "Shin-Kyokushin - 12x5", "membership", "80.000", 35, ["Shin-Kyokushin Junior"]),
    ("BED", "Shin-Kyokushin - 12x6", "membership", "90.000", 42, ["Shin-Kyokushin Junior"]),
    ("BED", "Kyokushin 3M", "membership", "180.000", 90, ["Kyokushin Karate"]),
    ("BED", "Adult Membership 10x4", "membership", "55.000", 30, ["Kickboxing", "Kajukenbo", "Kyokushin Karate"]),
    ("BED", "Ladies' Class 10x4", "membership", "55.000", 30, ["Ladies' Class"]),
    ("BED", "Trial Pass", "trial", "10.000", 7, []),
    ("BED", "Day Pass", "day_pass", "8.000", 1, []),
    ("BED", "Systema Membership", "other", "30.000", 30, []),
    ("BED", "Kajukenbo Seminar", "seminar", "15.000", 1, []),
]

# email prefix, name, name_ar, job title, employment type, role, branch (None = all), disciplines
STAFF = [
    ("ceo", "Yaqoub Al-Test", "يعقوب التجربة", "Chief Executive Officer", "full_time", "ceo", None, []),
    ("ops", "Nader Al-Test", "نادر التجربة", "Operations Manager", "full_time", "operations_manager", None, []),
    ("training", "Adel Al-Test", "عادل التجربة", "Training Lead", "full_time", "training_lead", None, ["kajukenbo"]),
    (
        "grappling",
        "Marco Silva",
        "ماركو سيلفا",
        "Grappling Track Lead",
        "full_time",
        "track_lead",
        None,
        ["jiujitsu", "grappling"],
    ),
    (
        "striking",
        "Ayman Farouk",
        "أيمن فاروق",
        "Striking Track Lead",
        "full_time",
        "track_lead",
        None,
        ["kickboxing", "striking"],
    ),
    ("coach.prm", "Tariq Hamdan", "طارق حمدان", "Instructor", "hourly", "instructor", "PRM", ["kajukenbo"]),
    ("coach.bed1", "Bilal Karam", "بلال كرم", "Instructor", "part_time", "instructor", "BED", ["shin_kyokushin"]),
    ("coach.bed2", "Farah Nasser", "فرح ناصر", "Instructor (Ladies)", "part_time", "instructor", "BED", ["kickboxing"]),
    ("coach.free", "Omar Test", "عمر تجربة", "Instructor (Freelance)", "freelance", "instructor", "BED", ["taekwondo"]),
    ("marketing", "Maha Al-Test", "مها التجربة", "Marketing Lead", "full_time", "marketing_lead", None, []),
    ("content", "Aya Test", "آية تجربة", "Marketing Implementation", "full_time", "marketing_staff", None, []),
    ("it", "Sami Al-Test", "سامي التجربة", "Systems & IT Lead", "full_time", "it_admin", None, []),
    ("admin.prm", "Vera Santos", "فيرا سانتوس", "Branch Admin", "full_time", "branch_admin", "PRM", []),
    ("admin.bed", "Tamer Youssef", "تامر يوسف", "Branch Admin", "full_time", "branch_admin", "BED", []),
    ("support", "Rana Test", "رنا تجربة", "Operations Support / Coach", "full_time", "operations_support", None, []),
    (
        "purchasing",
        "Bassam Test",
        "بسام تجربة",
        "Purchasing Coordinator",
        "full_time",
        "purchasing_coordinator",
        "PRM",
        [],
    ),
    ("accounts", "Hani Test", "هاني تجربة", "Accountant", "full_time", "accountant", None, []),
]

MEDICAL_NOTES = [
    "Asthma — carries an inhaler.",
    "Previous knee injury (2025), avoid deep squats.",
    "Type 1 diabetes — may need a snack break.",
    "Wears glasses; contact lenses for sparring.",
]
ALLERGIES = ["Peanuts", "Bee stings", "Penicillin", "Dust"]


class Command(BaseCommand):
    help = "Load fictional Kuwait test data (never in production)."

    def add_arguments(self, parser):
        parser.add_argument("--families", type=int, default=45)
        parser.add_argument("--adults", type=int, default=30)
        parser.add_argument("--seed", type=int, default=2026)
        parser.add_argument("--reset", action="store_true", help="Delete existing test data first.")

    def handle(self, *args, **opts):
        if getattr(settings, "ENVIRONMENT", "") == "production":
            raise CommandError("Test data can never be loaded into the live system.")
        self.rng = random.Random(opts["seed"])  # nosec B311 - deterministic fake data, not security
        self.today = timezone.localdate()
        self.used_cids: set[str] = set()
        self.used_mobiles: set[str] = set()

        with transaction.atomic():
            if opts["reset"]:
                self._reset()
            sync_rbac(reset_role_permissions=False)
            self.branches = self._branches()
            self._catalogue()
            self._staff()
            self.member_count = 0
            for _ in range(opts["families"]):
                self._family()
            for _ in range(opts["adults"]):
                self._adult()
            self._edge_cases()
            from apps.testdata.phase1 import Phase1Data

            Phase1Data(self).load()
            from apps.testdata.phase2 import Phase2Data

            Phase2Data(self).load()
            from apps.testdata.phase3 import Phase3Data

            Phase3Data(self).load()
            from apps.testdata.phase4 import Phase4Data

            Phase4Data(self).load()

        self.stdout.write(
            self.style.SUCCESS(
                f"Kuwait test data loaded: {Branch.objects.count()} branches, {Program.objects.count()} programs, "
                f"{PricingOption.objects.count()} pricing options, {StaffProfile.objects.count()} staff, "
                f"{Guardian.objects.count()} guardians, {Member.objects.count()} members."
            )
        )
        self.stdout.write(
            f"Test logins: <role>@{TEST_EMAIL_DOMAIN} (e.g. ops@{TEST_EMAIL_DOMAIN}), password {DEV_PASSWORD}"
        )

    # ------------------------------------------------------------------
    def _reset(self):
        from apps.testdata.phase1 import reset_phase1
        from apps.testdata.phase2 import reset_phase2
        from apps.testdata.phase3 import reset_phase3
        from apps.testdata.phase4 import reset_phase4

        reset_phase4()
        reset_phase3()
        reset_phase2()
        reset_phase1()
        MediaConsent.objects.all().delete()
        EmergencyContact.objects.all().delete()
        GuardianLink.objects.all().delete()
        Member.objects.all().delete()
        Guardian.objects.all().delete()
        StaffProfile.objects.all().delete()
        # Test users are kept (the audit log may reference them); their branch-scoped roles are rebuilt.
        RoleAssignment.objects.filter(user__email__endswith=TEST_EMAIL_DOMAIN, branch__isnull=False).delete()
        PricingOption.objects.all().delete()
        Program.objects.all().delete()
        Discipline.objects.all().delete()
        # Branches are kept (website pages and enquiries point at them); _branches() refreshes them.

    def _branches(self):
        prm, _ = Branch.objects.update_or_create(
            code="PRM",
            defaults=dict(
                name="Elite Promenade",
                name_ar="إيليت بروميناد",
                area="Hawalli",
                area_ar="حولي",
                address="Promenade Mall, Hawalli",
                open_days=[0, 1, 2, 3, 4],
                positioning="The Complete Fighter Program",
            ),
        )
        bed, _ = Branch.objects.update_or_create(
            code="BED",
            defaults=dict(
                name="Elite Bedaya",
                name_ar="إيليت بداية",
                area="Sabah Al Salem",
                area_ar="صباح السالم",
                address="Sabah Al Salem",
                open_days=[0, 1, 2, 3, 4, 5],
                positioning="Choose Your Discipline",
            ),
        )
        return {"PRM": prm, "BED": bed}

    def _catalogue(self):
        disc = {}
        for code, name, name_ar, track in DISCIPLINES:
            disc[code], _ = Discipline.objects.update_or_create(
                code=code, defaults=dict(name=name, name_ar=name_ar, track=track)
            )
        self.programs = {}
        for b, name, name_ar, codes, audience, amin, amax in PROGRAMS:
            prog, _ = Program.objects.update_or_create(
                branch=self.branches[b],
                name=name,
                defaults=dict(name_ar=name_ar, audience=audience, age_min=amin, age_max=amax),
            )
            prog.disciplines.set([disc[c] for c in codes])
            self.programs[(b, name)] = prog
        for b, name, kind, price, days, progs in PRICING:
            opt, _ = PricingOption.objects.update_or_create(
                branch=self.branches[b], name=name, defaults=dict(kind=kind, price=Decimal(price), duration_days=days)
            )
            opt.programs.set([self.programs[(b, p)] for p in progs])
        self.disciplines = disc

    def _user(self, prefix, name, name_ar):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=f"{prefix}@{TEST_EMAIL_DOMAIN}", defaults=dict(full_name=name, full_name_ar=name_ar)
        )
        if created:
            user.set_password(DEV_PASSWORD)
            user.save()
        return user

    def _staff(self):
        roles = {r.code: r for r in Role.objects.all()}
        for prefix, name, name_ar, title, etype, role, branch, discs in STAFF:
            user = self._user(prefix, name, name_ar)
            profile, _ = StaffProfile.objects.update_or_create(
                user=user,
                defaults=dict(
                    job_title=title,
                    employment_type=etype,
                    primary_branch=self.branches.get(branch) if branch else None,
                    nationality=self.rng.choice(["Kuwaiti", "Egyptian", "Filipino", "Brazilian", "Indian"]),
                    start_date=self.today - datetime.timedelta(days=self.rng.randint(90, 3000)),
                ),
            )
            profile.disciplines.set([self.disciplines[d] for d in discs])
            RoleAssignment.objects.get_or_create(
                user=user,
                role=roles[role],
                branch=self.branches.get(branch) if branch else None,
                defaults=dict(reason="Test data"),
            )
        # Roaa-style dual role: operations support who also coaches.
        support = get_user_model().objects.get(email=f"support@{TEST_EMAIL_DOMAIN}")
        RoleAssignment.objects.get_or_create(
            user=support, role=roles["instructor"], branch=None, defaults=dict(reason="Test data: dual role")
        )

    # ------------------------------------------------------------------
    def _consent(self, member, signer):
        pattern = self.rng.choices(["all", "internal", "social_internal", "none"], weights=[55, 20, 15, 10])[0]
        flags = {
            "all": (True, True, True),
            "internal": (True, False, False),
            "social_internal": (True, True, False),
            "none": (False, False, False),
        }[pattern]
        MediaConsent.objects.create(
            member=member,
            internal_records=flags[0],
            social_media=flags[1],
            website_marketing=flags[2],
            signed_by_name=signer,
        )

    def _member(self, branch_code, first, last, gender, age, nationality, **extra):
        dob = kw.birth_date(self.rng, age, self.today)
        member = Member(
            branch=self.branches[branch_code],
            first_name=first[0],
            first_name_ar=first[1],
            last_name=last[0],
            last_name_ar=last[1],
            date_of_birth=dob,
            gender=gender,
            nationality=nationality,
            civil_id=kw.make_civil_id(self.rng, dob, self.used_cids),
            area=self.rng.choice(kw.AREAS_BY_BRANCH[branch_code]),
            source=self.rng.choices(
                ["walk_in", "referral", "instagram", "whatsapp", "google", "website"], weights=[30, 30, 15, 12, 8, 5]
            )[0],
            joined_on=self.today - datetime.timedelta(days=self.rng.randint(0, 900)),
            **extra,
        )
        if self.rng.random() < 0.12:
            member.medical_notes = self.rng.choice(MEDICAL_NOTES)
        if self.rng.random() < 0.08:
            member.allergies = self.rng.choice(ALLERGIES)
        member.save()
        self.member_count += 1
        return member

    def _family(self):
        branch = self.rng.choice(["PRM", "BED"])
        if self.rng.random() < 0.12:
            (gfirst, family, nationality) = self.rng.choice(kw.EXPAT_FAMILIES)
        else:
            family = self.rng.choice(kw.FAMILY_NAMES)
            nationality = kw.weighted(self.rng, kw.NATIONALITY_WEIGHTS)
            gfirst = None
        is_father = self.rng.random() < 0.7
        if gfirst is None:
            gfirst = self.rng.choice(kw.MALE_NAMES if is_father else kw.FEMALE_NAMES)
        gdob = kw.birth_date(self.rng, self.rng.randint(30, 52), self.today)
        guardian = Guardian.objects.create(
            full_name=f"{gfirst[0]} {family[0]}",
            full_name_ar=f"{gfirst[1]} {family[1]}",
            mobile=kw.make_mobile(self.rng, self.used_mobiles),
            civil_id=kw.make_civil_id(self.rng, gdob, self.used_cids),
        )
        for _ in range(self.rng.choices([1, 2, 3, 4], weights=[45, 35, 15, 5])[0]):
            girl = self.rng.random() < 0.3
            age = self.rng.randint(5, 15)
            first = self.rng.choice(kw.FEMALE_NAMES if girl else kw.MALE_NAMES)
            branch_code = "BED" if girl and self.rng.random() < 0.7 else branch
            child = self._member(branch_code, first, family, "female" if girl else "male", age, nationality)
            GuardianLink.objects.create(
                guardian=guardian, member=child, relationship="father" if is_father else "mother", is_primary=True
            )
            EmergencyContact.objects.create(
                member=child,
                name=f"{self.rng.choice(kw.FEMALE_NAMES)[0]} {family[0]}",
                relationship="Aunt" if self.rng.random() < 0.5 else "Grandmother",
                mobile=kw.make_mobile(self.rng, self.used_mobiles),
            )
            self._consent(child, guardian.full_name)

    def _adult(self):
        female = self.rng.random() < 0.4
        first = self.rng.choice(kw.FEMALE_NAMES if female else kw.MALE_NAMES)
        family = self.rng.choice(kw.FAMILY_NAMES)
        branch = "BED" if female else self.rng.choice(["PRM", "BED"])
        member = self._member(
            branch,
            first,
            family,
            "female" if female else "male",
            self.rng.randint(18, 48),
            kw.weighted(self.rng, kw.NATIONALITY_WEIGHTS),
            mobile=kw.make_mobile(self.rng, self.used_mobiles),
        )
        self._consent(member, f"{first[0]} {family[0]}")

    def _edge_cases(self):
        # Two different children with the same name (duplicate-name handling).
        for _ in range(2):
            self._member("BED", ("Mohammed", "محمد"), ("Al-Ajmi", "العجمي"), "male", 10, "Kuwaiti")
        # An inactive former member.
        former = self._member("PRM", ("Hamad", "حمد"), ("Al-Ghanim", "الغانم"), "male", 12, "Kuwaiti")
        former.is_active = False
        former.save()
        # A member whose consent was withdrawn (newest consent row has nothing ticked).
        withdrawn = self._member("PRM", ("Jana", "جنى"), ("Al-Mudhaf", "المضف"), "female", 9, "Kuwaiti")
        MediaConsent.objects.create(
            member=withdrawn,
            internal_records=True,
            social_media=True,
            website_marketing=True,
            signed_by_name="Test parent",
            signed_at=timezone.now() - datetime.timedelta(days=60),
        )
        MediaConsent.objects.create(member=withdrawn, signed_by_name="Test parent", notes="Withdrawn in writing")
        # A parent with a portal login, linked to two children.
        user = self._user("parent", "Parent Test", "ولي أمر تجربة")
        guardian = Guardian.objects.create(
            full_name="Parent Test", mobile=kw.make_mobile(self.rng, self.used_mobiles), user=user
        )
        for name in (("Yousef", "يوسف"), ("Dana", "دانة")):
            child = self._member(
                "BED", name, ("Al-Test", "التجربة"), "male" if name[0] == "Yousef" else "female", 8, "Kuwaiti"
            )
            GuardianLink.objects.create(guardian=guardian, member=child, relationship="father", is_primary=True)
        RoleAssignment.objects.get_or_create(
            user=user, role=Role.objects.get(code="guardian"), branch=None, defaults=dict(reason="Test data")
        )
