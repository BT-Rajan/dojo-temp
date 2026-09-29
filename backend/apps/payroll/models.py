"""
M20 — Payroll for Elite's staff and coaches (decisions P2-1 to P2-11).

- PayrollSettings  the Kuwait rules (overtime, end-of-service, PIFSS, leave, cut-off). Values are
                   confirmed by the Accountant; no run can be approved until they are.
- PayProfile       bank details and PIFSS status for one person; PayComponent rows hold any mix
                   of salary, allowances, hourly rate, rate per class and commission.
- Leave, Advance, PayAdjustment   inputs for the month (overtime, bonus, absence…).
- PayrollRun       draft (built by the system) → submitted (OM) → approved (Accountant) → paid.
- Payslip, PayslipLine   the frozen result per person, bilingual.
"""

import datetime
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.crypto import EncryptedTextField
from apps.core.models import BaseModel

ZERO = Decimal("0.000")
D = Decimal


class PayrollSettings(BaseModel):
    """One row. Every value is a Kuwait Private Sector Labour Law default the Accountant confirms."""

    working_days_per_month = models.PositiveSmallIntegerField(default=26, help_text="Daily rate = monthly ÷ this.")
    hours_per_day = models.PositiveSmallIntegerField(default=8, help_text="Hourly rate = daily rate ÷ this.")
    overtime_normal = models.DecimalField(max_digits=4, decimal_places=2, default=D("1.25"))
    overtime_rest_day = models.DecimalField(max_digits=4, decimal_places=2, default=D("1.50"))
    overtime_holiday = models.DecimalField(max_digits=4, decimal_places=2, default=D("2.00"))
    eos_days_first_five_years = models.PositiveSmallIntegerField(default=15)
    eos_days_after_five_years = models.PositiveSmallIntegerField(default=30)
    eos_cap_months = models.PositiveSmallIntegerField(default=18, help_text="End-of-service is capped at this pay.")
    resign_share_under_3 = models.DecimalField(max_digits=5, decimal_places=4, default=D("0"))
    resign_share_3_to_5 = models.DecimalField(max_digits=5, decimal_places=4, default=D("0.5"))
    resign_share_5_to_10 = models.DecimalField(max_digits=5, decimal_places=4, default=D("0.6667"))
    resign_share_10_plus = models.DecimalField(max_digits=5, decimal_places=4, default=D("1"))
    pifss_employee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=D("10.50"))
    pifss_employer_percent = models.DecimalField(max_digits=5, decimal_places=2, default=D("11.50"))
    pifss_salary_cap = models.DecimalField(
        max_digits=10, decimal_places=3, default=D("2750.000"), help_text="Monthly pay counted for PIFSS is capped."
    )
    annual_leave_days = models.PositiveSmallIntegerField(default=30)
    sick_full_pay_days = models.PositiveSmallIntegerField(default=15)
    sick_three_quarter_days = models.PositiveSmallIntegerField(default=10)
    sick_half_pay_days = models.PositiveSmallIntegerField(default=10)
    sick_quarter_pay_days = models.PositiveSmallIntegerField(default=10)
    cutoff_day = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Classes taught and sales count up to this day of the month.",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmation_note = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "payroll settings"

    def __str__(self):
        return "Payroll settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def confirmed(self):
        return self.confirmed_at is not None


class PublicHoliday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)
    name_ar = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} {self.name}"


class PayProfile(BaseModel):
    staff = models.OneToOneField("staff.StaffProfile", on_delete=models.PROTECT, related_name="pay")
    iban = EncryptedTextField(blank=True)
    bank_name = models.CharField(max_length=80, blank=True)
    account_name = models.CharField(max_length=150, blank=True)
    is_kuwaiti = models.BooleanField(default=False, help_text="PIFSS social security applies.")
    note = models.CharField(max_length=255, blank=True)

    AUDIT_REDACT = ("iban",)

    def __str__(self):
        return f"Pay · {self.staff.user.full_name}"

    @property
    def is_freelance(self):
        return self.staff.employment_type == "freelance"

    @property
    def pifss_applies(self):
        return self.is_kuwaiti and not self.is_freelance

    @property
    def iban_last4(self):
        return self.iban[-4:] if self.iban else ""


class PayComponent(BaseModel):
    """Any combination per person (decision P2-1). Rates can be limited to one program."""

    class Kind(models.TextChoices):
        SALARY = "salary", "Monthly salary"
        ALLOWANCE = "allowance", "Monthly allowance"
        HOURLY = "hourly", "Hourly rate (classes taught)"
        PER_CLASS = "per_class", "Rate per class taught"
        COMMISSION = "commission", "Commission on own sales"

    MONTHLY = (Kind.SALARY, Kind.ALLOWANCE)

    profile = models.ForeignKey(PayProfile, on_delete=models.CASCADE, related_name="components")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    name = models.CharField(max_length=80, blank=True, help_text="e.g. Transport allowance.")
    name_ar = models.CharField(max_length=80, blank=True)
    amount = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True, help_text="KD per month, hour or class."
    )
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Commission %.")
    program = models.ForeignKey(
        "organization.Program",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
        help_text="Hourly / per-class rate for this program only.",
    )
    session_kinds = models.JSONField(
        default=list, blank=True, help_text='Session kinds counted, e.g. ["class"] or ["seminar","camp"]. Empty = all.'
    )
    sale_categories = models.JSONField(
        default=list, blank=True, help_text='Commission categories, e.g. ["new","renew"]. Empty = all.'
    )
    counts_for_pifss = models.BooleanField(default=True)
    valid_from = models.DateField(default=timezone.localdate)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["profile_id", "kind", "valid_from"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.amount or self.percent}"

    def active_in(self, start, end) -> bool:
        return self.valid_from <= end and (self.valid_to is None or self.valid_to >= start)


class Leave(BaseModel):
    class Kind(models.TextChoices):
        ANNUAL = "annual", "Annual leave"
        SICK = "sick", "Sick leave"
        UNPAID = "unpaid", "Unpaid leave"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    staff = models.ForeignKey("staff.StaffProfile", on_delete=models.PROTECT, related_name="leaves")
    kind = models.CharField(max_length=6, choices=Kind.choices)
    start = models.DateField()
    end = models.DateField()
    days = models.PositiveSmallIntegerField(help_text="Working days (Fridays and public holidays not counted).")
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-start"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.start}–{self.end}"


class Advance(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved — being repaid"
        REPAID = "repaid", "Repaid"
        REJECTED = "rejected", "Rejected"

    staff = models.ForeignKey("staff.StaffProfile", on_delete=models.PROTECT, related_name="advances")
    amount = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(D("0.001"))])
    instalments = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(12)])
    reason = models.CharField(max_length=255)
    first_month = models.DateField(help_text="First payroll month the repayment is taken.")
    repaid = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Advance {self.amount} ({self.staff.user.full_name})"

    @property
    def outstanding(self):
        return max(self.amount - self.repaid, ZERO)

    @property
    def instalment(self):
        return (self.amount / self.instalments).quantize(D("0.001"))


class PayAdjustment(BaseModel):
    class Kind(models.TextChoices):
        OVERTIME_NORMAL = "ot_normal", "Overtime — normal day (hours)"
        OVERTIME_REST = "ot_rest", "Overtime — rest day (hours)"
        OVERTIME_HOLIDAY = "ot_holiday", "Overtime — public holiday (hours)"
        BONUS = "bonus", "Bonus (e.g. Instructor of the Month)"
        EXTRA = "extra", "Extra classes, seminars or camps"
        ADDITION = "addition", "Other addition"
        ABSENCE = "absence", "Absence (days deducted)"
        DEDUCTION = "deduction", "Other deduction"

    HOURS = (Kind.OVERTIME_NORMAL, Kind.OVERTIME_REST, Kind.OVERTIME_HOLIDAY)
    DAYS = (Kind.ABSENCE,)
    DEDUCTIONS = (Kind.ABSENCE, Kind.DEDUCTION)

    staff = models.ForeignKey("staff.StaffProfile", on_delete=models.PROTECT, related_name="pay_adjustments")
    month = models.DateField(help_text="First day of the payroll month.")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, help_text="Hours of overtime or days of absence."
    )
    amount = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True, help_text="KD.")
    note = models.CharField(max_length=255)

    class Meta:
        ordering = ["month", "staff_id", "kind"]

    def __str__(self):
        return f"{self.get_kind_display()} {self.quantity or self.amount}"


class PayrollRun(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft — being checked by the OM"
        SUBMITTED = "submitted", "Waiting for the Accountant"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"

    month = models.DateField(unique=True, help_text="First day of the month.")
    period_start = models.DateField(help_text="Classes and sales counted from this day…")
    period_end = models.DateField(help_text="…to this day (the cut-off).")
    pay_date = models.DateField()
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.DRAFT)
    built_at = models.DateTimeField(default=timezone.now)
    warnings = models.JSONField(default=list, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    return_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-month"]

    def __str__(self):
        return f"Payroll {self.month:%B %Y}"

    @property
    def reference(self):
        return f"SAL-{self.month:%Y-%m}"

    @property
    def is_locked(self):
        return self.status in (self.Status.APPROVED, self.Status.PAID)


class Payslip(models.Model):
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    staff = models.ForeignKey("staff.StaffProfile", on_delete=models.PROTECT, related_name="payslips")
    branch = models.ForeignKey("organization.Branch", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    full_name = models.CharField(max_length=150)
    full_name_ar = models.CharField(max_length=150, blank=True)
    job_title = models.CharField(max_length=100)
    job_title_ar = models.CharField(max_length=100, blank=True)
    employment_type = models.CharField(max_length=12)
    gross = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    deductions = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    net = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    employer_pifss = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    eos_accrual = models.DecimalField(max_digits=10, decimal_places=3, default=ZERO)
    iban_last4 = models.CharField(max_length=4, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["run_id", "full_name"]
        constraints = [models.UniqueConstraint(fields=["run", "staff"], name="one_payslip_per_person_per_run")]

    def __str__(self):
        return f"{self.run.reference} · {self.full_name}"

    @property
    def cost(self):
        """What this person costs Elite this month (for the income statement)."""
        return self.gross + self.employer_pifss


class PayslipLine(models.Model):
    class Kind(models.TextChoices):
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"
        EMPLOYER = "employer", "Paid by Elite (not deducted)"

    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=9, choices=Kind.choices)
    code = models.CharField(max_length=20)
    label = models.CharField(max_length=150)
    label_ar = models.CharField(max_length=150, blank=True)
    quantity = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=3)
    source = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["payslip_id", "kind", "id"]

    def __str__(self):
        return f"{self.label} {self.amount}"


def month_start(day: datetime.date) -> datetime.date:
    return day.replace(day=1)
