"""
Price approvals (scope M1, business rule 5): nothing a customer pays changes without the
Operations Manager's approval, and nobody approves their own request (ISO 27001 A.5.3,
segregation of duties).
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.services import record_event
from apps.rbac.services import has_perm

from .models import Branch, PriceChange, PricingOption, Program


def _check_approver(user, requester, branch_id):
    if not has_perm(user, "pricing.approve", branch_id):
        raise PermissionDenied("Only the Operations Manager can approve prices.")
    if requester is not None and requester.pk == user.pk:
        raise PermissionDenied("A price you requested must be approved by someone else.")


@transaction.atomic
def request_price_change(option: PricingOption, new_price, effective_from, reason: str, user) -> PriceChange:
    if not has_perm(user, "pricing.manage", option.branch_id):
        raise PermissionDenied("You cannot request price changes for this branch.")
    if not reason.strip():
        raise ValidationError("Give a reason for the price change.")
    if effective_from < timezone.localdate():
        raise ValidationError("A price change cannot start in the past.")
    change = PriceChange.objects.create(
        pricing_option=option,
        old_price=option.price,
        new_price=new_price,
        effective_from=effective_from,
        reason=reason.strip(),
        created_by=user,
        updated_by=user,
    )
    record_event(
        action="price_change_requested",
        instance=change,
        branch_id=option.branch_id,
        changes={"old": str(option.price), "new": str(new_price)},
    )
    return change


@transaction.atomic
def decide_price_change(change: PriceChange, approve: bool, user, note: str = "") -> PriceChange:
    change = PriceChange.objects.select_for_update().select_related("pricing_option").get(pk=change.pk)
    if change.status != PriceChange.Status.PENDING:
        raise ValidationError("This request has already been decided.")
    _check_approver(user, change.created_by, change.pricing_option.branch_id)
    change.status = PriceChange.Status.APPROVED if approve else PriceChange.Status.REJECTED
    change.decided_by, change.decided_at, change.decision_note = user, timezone.now(), note
    change.save(update_fields=["status", "decided_by", "decided_at", "decision_note", "updated_at"])
    record_event(
        action="price_change_approved" if approve else "price_change_rejected",
        instance=change,
        branch_id=change.pricing_option.branch_id,
    )
    if approve:
        apply_due_price_changes()
    return change


@transaction.atomic
def apply_due_price_changes(today=None) -> int:
    """Puts approved prices live on their start date. Runs on approval and every morning."""
    today = today or timezone.localdate()
    due = PriceChange.objects.select_for_update().filter(status=PriceChange.Status.APPROVED, effective_from__lte=today)
    count = 0
    for change in due.select_related("pricing_option"):
        option = PricingOption.objects.select_for_update().get(pk=change.pricing_option_id)
        option.price = change.new_price
        option.version += 1
        option.save(update_fields=["price", "version", "updated_at"])
        change.status = PriceChange.Status.APPLIED
        change.save(update_fields=["status", "updated_at"])
        record_event(action="price_change_applied", instance=option, changes={"price": str(change.new_price)})
        count += 1
    return count


@transaction.atomic
def decide_pricing_option(option: PricingOption, approve: bool, user) -> PricingOption:
    """A new pricing option can be sold only after approval."""
    option = PricingOption.objects.select_for_update().get(pk=option.pk)
    if option.approval != PricingOption.Approval.PENDING:
        raise ValidationError("This pricing option has already been decided.")
    _check_approver(user, option.created_by, option.branch_id)
    option.approval = PricingOption.Approval.APPROVED if approve else PricingOption.Approval.REJECTED
    option.updated_by = user
    option.version += 1
    option.save(update_fields=["approval", "updated_by", "version", "updated_at"])
    record_event(action="pricing_option_approved" if approve else "pricing_option_rejected", instance=option)
    return option


# ---------------------------------------------------------------------------
# Branches and their programs (decision P7-12)
# ---------------------------------------------------------------------------
BRANCH_FIELDS = (
    "name", "name_ar", "area", "area_ar", "address", "phone", "open_days", "positioning", "google_review_url",
)  # fmt: skip


def _need_branches(user):
    from apps.rbac.services import has_perm

    if not has_perm(user, "branches.manage"):
        raise PermissionDenied("Only the CEO, the Operations Manager or Systems & IT manage branches.")


def _clean_branch(data):
    import re

    from django.core.validators import URLValidator

    for f in ("name", "name_ar", "area"):
        if not (data.get(f) or "").strip():
            raise ValidationError("Give the branch name in English and Arabic, and its area.")
    days = sorted({int(d) for d in data.get("open_days") or [] if str(d).isdigit() and 0 <= int(d) <= 6})
    if not days:
        raise ValidationError("Tick the days the branch is open.")
    data["open_days"] = days
    phone = re.sub(r"[\s\-()]", "", data.get("phone") or "")
    if phone and not re.fullmatch(r"\+?\d{7,15}", phone):
        raise ValidationError("Enter the branch phone as digits, e.g. 22223333 or +96522223333.")
    data["phone"] = phone
    if data.get("google_review_url"):
        URLValidator(schemes=["https"])(data["google_review_url"])
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items() if k in BRANCH_FIELDS}


@transaction.atomic
def create_branch(user, *, code, **data) -> Branch:
    import re

    from apps.audit.services import record_event

    _need_branches(user)
    code = (code or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2,5}", code):
        raise ValidationError("The branch code is 2 to 5 letters, e.g. KHT. It appears in reference numbers.")
    if Branch.objects.filter(code__iexact=code).exists():
        raise ValidationError("That branch code is already used.")
    branch = Branch.objects.create(code=code, created_by=user, updated_by=user, **_clean_branch(data))
    record_event(action="branch_created", instance=branch)
    create_branch_page(branch)
    return branch


@transaction.atomic
def update_branch(user, branch: Branch, **data) -> Branch:
    _need_branches(user)
    branch = Branch.objects.select_for_update().get(pk=branch.pk)
    for k, v in _clean_branch(data).items():
        setattr(branch, k, v)
    branch.updated_by = user
    branch.save()
    return branch


def closing_blockers(branch: Branch) -> list[str]:
    from django.utils import timezone

    from apps.classes.models import ClassSession
    from apps.sales.models import Membership

    today = timezone.localdate()
    out = []
    n = Membership.objects.filter(branch=branch, status="active", end_date__gte=today).count()
    if n:
        out.append(f"{n} memberships are still running; move or end them first.")
    n = ClassSession.objects.filter(branch=branch, date__gte=today, status="scheduled").count()
    if n:
        out.append(f"{n} classes are still scheduled; cancel them through Class changes so members are told.")
    return out


@transaction.atomic
def close_branch(user, branch: Branch, reason: str) -> Branch:
    """Hidden from the website, bookings and new sales; history stays in every report."""
    from apps.audit.services import record_event
    from apps.classes.models import ClassSlot

    _need_branches(user)
    if not (reason or "").strip():
        raise ValidationError("Give the reason for closing the branch.")
    blockers = closing_blockers(branch)
    if blockers:
        raise ValidationError(blockers)
    if Branch.objects.filter(is_active=True).exclude(pk=branch.pk).count() == 0:
        raise ValidationError("At least one branch must stay open.")
    branch.is_active, branch.updated_by = False, user
    branch.save(update_fields=["is_active", "updated_by", "updated_at"])
    ClassSlot.objects.filter(branch=branch, is_active=True).update(is_active=False)
    page = getattr(branch, "web_page", None)
    if page is not None and page.live:
        page.unpublish()
    record_event(action="branch_closed", instance=branch, changes={"reason": reason.strip()[:255]})
    return branch


@transaction.atomic
def reopen_branch(user, branch: Branch) -> Branch:
    from apps.audit.services import record_event

    _need_branches(user)
    branch.is_active, branch.updated_by = True, user
    branch.save(update_fields=["is_active", "updated_by", "updated_at"])
    record_event(action="branch_reopened", instance=branch)
    return branch


def create_branch_page(branch: Branch):
    """A draft page for the website (Marketing completes and publishes it in the CMS). Skipped if the site is empty."""
    from django.utils.text import slugify

    from apps.website.models import BranchPage, ContentPage, HomePage

    if getattr(branch, "web_page", None) is not None:
        return branch.web_page
    parent = ContentPage.objects.filter(slug="branches").first() or HomePage.objects.first()
    if parent is None:
        return None
    from apps.classes.models import WEEKDAYS, WEEKDAYS_AR

    names = dict(WEEKDAYS)
    open_en = ", ".join(names[d] for d in branch.open_days)
    open_ar = "، ".join(WEEKDAYS_AR[d] for d in branch.open_days)
    slug = slugify(f"elite-{branch.name}") or f"branch-{branch.code.lower()}"
    if parent.get_children().filter(slug=slug).exists():
        slug = f"{slug}-{branch.code.lower()}"
    page = BranchPage(
        title=branch.name,
        title_ar=branch.name_ar,
        slug=slug,
        branch=branch,
        live=False,
        promise_en=branch.positioning or branch.name,
        ticks_en="Classes for kids and adults\nQualified coaches\nFree trial class",
        ticks_ar="حصص للأطفال والكبار\nمدربون معتمدون\nحصة تجريبية مجانية",
        price_lines="0|Prices to be added|تُضاف الأسعار",
        open_days_en=open_en,
        open_days_ar=open_ar,
        closed_weekdays=",".join(str(d) for d in range(7) if d not in branch.open_days),
        address_en=branch.address[:200],
        band_cta=True,
    )
    parent.add_child(instance=page)
    page.save_revision()
    return page


def branch_checklist(branch: Branch) -> list[dict]:
    """What the branch still needs before it opens, each with the screen that fixes it."""
    from apps.classes.models import ClassSlot
    from apps.inventory.models import StockMovement
    from apps.organization.models import Room
    from apps.rbac.models import RoleAssignment

    slots = ClassSlot.objects.filter(branch=branch, is_active=True)
    no_coach = slots.filter(instructors__isnull=True).count()
    desk_staff = (
        RoleAssignment.objects.current()
        .filter(branch=branch, role__code__in=["branch_admin", "operations_support"])
        .count()
    )
    page = getattr(branch, "web_page", None)
    rows = [
        ("details", "Address, phone and Google review link", "العنوان والهاتف ورابط تقييم Google",
         bool(branch.address and branch.phone and branch.google_review_url), None),
        ("rooms", "At least one room (mat)", "قاعة واحدة على الأقل",
         Room.objects.filter(branch=branch, is_active=True).exists(), "desk:rooms"),
        ("programs", "Programs (what is taught, for which ages)", "البرامج (ما يُدرّس ولأي أعمار)",
         Program.objects.filter(branch=branch, is_active=True).exists(), "programs"),
        ("prices", "Approved membership prices", "أسعار اشتراكات معتمدة",
         PricingOption.objects.filter(branch=branch, is_active=True, kind="membership",
                                      approval="approved").exists(), "desk:pricing"),
        ("timetable", "Weekly timetable" + (f" ({no_coach} classes without a coach)" if no_coach else ""),
         "الجدول الأسبوعي" + (f" ({no_coach} حصص بدون مدرب)" if no_coach else ""),
         slots.exists() and not no_coach, "desk:timetable"),
        ("staff", "Front-desk staff with a role at this branch", "موظفو استقبال بدور في هذا الفرع",
         desk_staff > 0, "desk:staff_list"),
        ("stock", "Opening stock", "المخزون الافتتاحي",
         StockMovement.objects.filter(branch=branch).exists(), "desk:stock"),
        ("website", "Website page published", "صفحة الموقع منشورة",
         bool(page and page.live), "cms"),
    ]  # fmt: skip
    return [{"key": k, "en": en, "ar": ar, "done": done, "link": link} for k, en, ar, done, link in rows]


@transaction.atomic
def save_program(user, branch: Branch, *, program=None, name, name_ar, disciplines, audience="any", age_min=None,
                 age_max=None, description="", is_active=True) -> Program:  # fmt: skip
    from apps.rbac.services import has_perm

    if not (has_perm(user, "programs.manage", branch.pk) or has_perm(user, "branches.manage")):
        raise PermissionDenied("Only the Operations Manager or the Training Lead edit programs.")
    name, name_ar = (name or "").strip(), (name_ar or "").strip()
    if not name or not name_ar:
        raise ValidationError("Give the program name in English and Arabic.")
    if not disciplines:
        raise ValidationError("Choose at least one discipline.")
    if audience not in Program.Audience.values:
        raise ValidationError("Choose who the program is for.")
    if age_min is not None and age_max is not None and age_min > age_max:
        raise ValidationError("The minimum age is above the maximum age.")
    if Program.objects.filter(branch=branch, name__iexact=name).exclude(pk=getattr(program, "pk", None)).exists():
        raise ValidationError("This branch already has a program with that name.")
    program = program or Program(branch=branch, created_by=user)
    program.name, program.name_ar, program.audience = name, name_ar, audience
    program.age_min, program.age_max, program.description, program.is_active = age_min, age_max, description, is_active
    program.updated_by = user
    program.save()
    program.disciplines.set(disciplines)
    return program
