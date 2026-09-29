"""
M7 — Training, curriculum and progression (replaces the Kajukenbo Master Curriculum workbook, the 4–6 week
evaluations on paper and the test-day records). Working decisions P4-1 to P4-10.

- Art            a belt system (Kajukenbo scalable curriculum, Kyokushin, Taekwondo…), followed through programs'
                 disciplines.
- Track          a part of the curriculum taught by its own instructors (Kickboxing, Jiu-Jitsu, Self-Defence).
- Rank           a belt, with its stripe, BJJ equivalent, seminar total and the eligibility numbers for it.
- Skill          what is worked on while wearing a belt, per track and category.
- MemberRank     a member's current belt in an art (placement, then promotions).
- SkillCheck     a skill ticked off for a member (from an evaluation score of 3 or 4).
- SeminarCredit  seminar points added by hand (seminars before the system); others come from check-ins.
- Evaluation     every 4–6 weeks, scores per skill, notes, "ready for test".
- TestDay        a grading day; TestCandidate holds each student's component results.
- Promotion      the belt history; the belt is handed over at the front desk as a 0 KD free issue.
- ProgressNote   the monthly note to parents.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel
from apps.website.belts import BELT_CHOICES

SCORES = [
    (1, "Not yet", "ليس بعد"),
    (2, "Developing", "قيد التطور"),
    (3, "Competent", "متمكن"),
    (4, "Strong", "قوي"),
]
PASS_SCORE = 3


class Art(BaseModel):
    code = models.SlugField(max_length=30, unique=True)
    name = models.CharField(max_length=80)
    name_ar = models.CharField(max_length=80)
    disciplines = models.ManyToManyField("organization.Discipline", related_name="arts", blank=True)
    test_components = models.JSONField(
        default=list,
        blank=True,
        help_text='[["kickboxing", "Kickboxing", "الكيك بوكسينغ"], …] — seminars is automatic.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def first_rank(self):
        return self.ranks.order_by("order").first()


class Track(models.Model):
    art = models.ForeignKey(Art, on_delete=models.CASCADE, related_name="tracks")
    code = models.SlugField(max_length=30)
    name = models.CharField(max_length=80)
    name_ar = models.CharField(max_length=80)
    order = models.PositiveSmallIntegerField(default=0)
    disciplines = models.ManyToManyField(
        "organization.Discipline", related_name="tracks", blank=True, help_text="Classes whose instructors use it."
    )
    who_teaches = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["art_id", "order"]
        constraints = [models.UniqueConstraint(fields=["art", "code"], name="one_track_code_per_art")]

    def __str__(self):
        return f"{self.art} · {self.name}"


class Rank(BaseModel):
    class Phase(models.TextChoices):
        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"
        EXPERT = "expert", "Expert"

    art = models.ForeignKey(Art, on_delete=models.CASCADE, related_name="ranks")
    order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=60)
    name_ar = models.CharField(max_length=60)
    belt = models.CharField(max_length=12, choices=BELT_CHOICES, help_text="Colour shown on screen.")
    phase = models.CharField(max_length=12, choices=Phase.choices, blank=True)
    stripe = models.CharField(max_length=60, blank=True, help_text="Jiu-Jitsu stripe, e.g. 1 × White stripe.")
    stripe_ar = models.CharField(max_length=60, blank=True)
    bjj_equivalent = models.CharField(max_length=60, blank=True)
    seminars_required = models.PositiveSmallIntegerField(default=0, help_text="Total seminars attended.")
    final_exam = models.BooleanField(default=False)
    min_classes = models.PositiveSmallIntegerField(default=0, help_text="Classes since the last promotion.")
    min_weeks = models.PositiveSmallIntegerField(default=0, help_text="Weeks at the previous belt.")
    min_evaluations = models.PositiveSmallIntegerField(default=2)
    belt_product = models.ForeignKey(
        "shop.Product", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", help_text="Belt in stock."
    )

    class Meta:
        ordering = ["art_id", "order"]
        constraints = [models.UniqueConstraint(fields=["art", "order"], name="one_rank_per_order")]

    def __str__(self):
        return f"{self.art.name} · {self.name}"

    def next(self):
        return Rank.objects.filter(art_id=self.art_id, order__gt=self.order).order_by("order").first()


class Skill(models.Model):
    rank = models.ForeignKey(Rank, on_delete=models.CASCADE, related_name="skills")
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name="skills")
    category = models.CharField(max_length=40, help_text="Strikes, Kicks, Positions, Katas…")
    category_ar = models.CharField(max_length=40, blank=True)
    name = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["rank__order", "track__order", "order", "id"]

    def __str__(self):
        return self.name


class MemberRank(BaseModel):
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="ranks")
    art = models.ForeignKey(Art, on_delete=models.PROTECT, related_name="+")
    rank = models.ForeignKey(Rank, on_delete=models.PROTECT, related_name="+")
    since = models.DateField(default=timezone.localdate, help_text="Date of the last promotion or placement.")
    belt_size = models.CharField(max_length=20, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "art"], name="one_rank_per_member_art")]

    def __str__(self):
        return f"{self.member} · {self.rank}"


class SkillCheck(models.Model):
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="skill_checks")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="checks")
    checked_on = models.DateField(default=timezone.localdate)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    evaluation = models.ForeignKey("Evaluation", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["member", "skill"], name="one_check_per_member_skill")]

    def __str__(self):
        return f"{self.member_id} ✓ {self.skill}"


class SeminarCredit(BaseModel):
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="seminar_credits")
    art = models.ForeignKey(Art, on_delete=models.PROTECT, related_name="+")
    points = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(20)])
    date = models.DateField(default=timezone.localdate)
    note = models.CharField(max_length=200)

    class Meta:
        ordering = ["-date"]


class Evaluation(BaseModel):
    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="evaluations")
    art = models.ForeignKey(Art, on_delete=models.PROTECT, related_name="+")
    rank = models.ForeignKey(Rank, on_delete=models.PROTECT, related_name="+", help_text="Belt at the time.")
    track = models.ForeignKey(Track, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    date = models.DateField(default=timezone.localdate)
    instructor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="evaluations")
    notes = models.TextField(blank=True)
    ready_for_test = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.member} · {self.date}"


class EvaluationScore(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="scores")
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="+")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["evaluation", "skill"], name="one_score_per_skill")]

    def __str__(self):
        return f"{self.skill}: {self.score}"


class TestDay(BaseModel):
    __test__ = False  # not a pytest test class

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        DONE = "done", "Results recorded"

    art = models.ForeignKey(Art, on_delete=models.PROTECT, related_name="test_days")
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="test_days")
    date = models.DateField()
    title = models.CharField(max_length=120, blank=True)
    examiners = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="test_days", blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PLANNED)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.art.name} test day {self.date:%d/%m/%Y} ({self.branch.code})"


class TestCandidate(BaseModel):
    __test__ = False  # not a pytest test class

    class Result(models.TextChoices):
        PENDING = "pending", "Not tested yet"
        PASSED = "passed", "Passed"
        NOT_YET = "not_yet", "Not yet"
        ABSENT = "absent", "Absent"

    test_day = models.ForeignKey(TestDay, on_delete=models.CASCADE, related_name="candidates")
    member = models.ForeignKey("members.Member", on_delete=models.PROTECT, related_name="tests")
    from_rank = models.ForeignKey(Rank, on_delete=models.PROTECT, related_name="+")
    to_rank = models.ForeignKey(Rank, on_delete=models.PROTECT, related_name="+")
    eligible = models.BooleanField(default=True)
    override_reason = models.CharField(max_length=255, blank=True, help_text="Why a not-yet-eligible student tests.")
    components = models.JSONField(default=dict, blank=True, help_text='{"kickboxing": "pass" | "fail"}')
    seminars_ok = models.BooleanField(default=False)
    result = models.CharField(max_length=8, choices=Result.choices, default=Result.PENDING)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["member__first_name", "member__last_name"]
        constraints = [models.UniqueConstraint(fields=["test_day", "member"], name="one_entry_per_test_day")]


class Promotion(BaseModel):
    class Kind(models.TextChoices):
        PLACEMENT = "placement", "Placement (belt set when joining the system)"
        TEST = "test", "Test day"
        DIRECT = "direct", "Promotion by a lead"

    class Belt(models.TextChoices):
        NONE = "none", "No belt to hand over"
        TO_ISSUE = "to_issue", "Belt to hand over"
        ISSUED = "issued", "Belt handed over"

    member = models.ForeignKey("members.Member", on_delete=models.PROTECT, related_name="promotions")
    art = models.ForeignKey(Art, on_delete=models.PROTECT, related_name="+")
    from_rank = models.ForeignKey(Rank, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    to_rank = models.ForeignKey(Rank, on_delete=models.PROTECT, related_name="+")
    date = models.DateField(default=timezone.localdate)
    kind = models.CharField(max_length=9, choices=Kind.choices)
    candidate = models.OneToOneField(
        TestCandidate, null=True, blank=True, on_delete=models.PROTECT, related_name="promotion"
    )
    branch = models.ForeignKey("organization.Branch", on_delete=models.PROTECT, related_name="+")
    note = models.CharField(max_length=255, blank=True)
    belt_status = models.CharField(max_length=8, choices=Belt.choices, default=Belt.NONE)
    sale = models.ForeignKey("sales.Sale", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    notified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.member} → {self.to_rank}"


class ProgressNote(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"

    member = models.ForeignKey("members.Member", on_delete=models.CASCADE, related_name="progress_notes")
    art = models.ForeignKey(Art, on_delete=models.PROTECT, related_name="+")
    month = models.DateField(help_text="First day of the month described.")
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="progress_notes"
    )
    worked_on = models.TextField(blank=True)
    next_steps = models.TextField(blank=True)
    status = models.CharField(max_length=5, choices=Status.choices, default=Status.DRAFT)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-month", "member__first_name"]
        constraints = [models.UniqueConstraint(fields=["member", "art", "month"], name="one_note_per_member_month")]
