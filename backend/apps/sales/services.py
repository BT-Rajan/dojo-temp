"""
Sales rules (scope M5, business rules 1, 2, 5, 6):

- only approved, active pricing options of the logged-in branch can be sold;
- equipment is sold by exact size from the branch's own stock; nothing leaves without a sale
  (a 0 KD free issue still reduces stock);
- every sale gets the next receipt number of its branch;
- the category (New / Renew / Trial Pass / Day Pass / Equipment) is set by the system;
- freeze, refund and cancellation are requested by the desk and decided by the OM, and
  nobody decides their own request;
- the end-of-day cash-up compares counted cash and terminal totals with the system.
"""

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.messaging import send_message
from apps.core.validators import day_range, normalize_kuwait_mobile
from apps.members.models import Member
from apps.members.services import contact_language, contact_mobile, siblings
from apps.organization.models import PricingOption
from apps.rbac.services import has_perm
from apps.shop.models import BranchStock, ProductVariant

from .models import (
    ZERO,
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

EXPIRING_DAYS = 5
FREEZE_MIN_WEEKS, FREEZE_MAX_WEEKS = 1, 4
FREEZE_FEE = Decimal(str(getattr(settings, "FREEZE_FEE_KD", "0")))


def _need(user, perm, branch_id, message):
    if not has_perm(user, perm, branch_id):
        raise PermissionDenied(message)


# ---------------------------------------------------------------------------
# Member status (calculated, never typed — scope M2)
# ---------------------------------------------------------------------------
@dataclass
class Status:
    code: str  # active, expiring, expired, frozen, trial, lead, former
    membership: Membership | None = None

    LABELS = {
        "active": ("Active", "فعّال"),
        "expiring": ("Expiring", "ينتهي قريباً"),
        "expired": ("Expired", "منتهي"),
        "frozen": ("Frozen", "مجمّد"),
        "trial": ("Trial", "تجربة"),
        "lead": ("Lead", "مهتم"),
        "former": ("Former", "سابق"),
    }

    def label(self, lang="en"):
        en, ar = self.LABELS[self.code]
        return ar if lang == "ar" else en


def memberships_for(member):
    return (
        Membership.objects.filter(member=member)
        .select_related("pricing_option")
        .prefetch_related("freezes", "pricing_option__programs")
    )


def member_status(member: Member, today=None) -> Status:
    today = today or timezone.localdate()
    if not member.is_active:
        return Status("former")
    items = [m for m in memberships_for(member) if m.status == Membership.Status.ACTIVE]
    real = [m for m in items if m.is_membership]
    for m in real:
        if m.start_date <= today <= m.end_date and m.frozen_on(today):
            return Status("frozen", m)
    current = [m for m in real if m.valid_on(today) and m.sessions_left != 0]
    if current:
        m = max(current, key=lambda x: x.end_date)
        return Status("expiring" if (m.end_date - today).days <= EXPIRING_DAYS else "active", m)
    if real:
        return Status("expired", max(real, key=lambda x: x.end_date))
    if (
        any(m.pricing_option.kind == PricingOption.Kind.TRIAL for m in items)
        or member.bookings.filter(is_trial=True).exists()
    ):
        return Status("trial")
    return Status("lead")


def membership_for_class(member: Member, program_id, day):
    """The membership to use for a check-in, and a warning code when there is none that fits."""
    items = [m for m in memberships_for(member) if m.status == Membership.Status.ACTIVE]
    usable = [m for m in items if m.valid_on(day) and not m.frozen_on(day)]
    fitting = [m for m in usable if m.covers_program(program_id)]
    with_sessions = [m for m in fitting if m.sessions_left != 0]
    if with_sessions:
        # Use the one ending soonest, so a newer purchase isn't consumed first.
        return min(with_sessions, key=lambda m: m.end_date), ""
    if fitting:
        return fitting[0], "no_sessions"
    if usable:
        return usable[0], "other_program"
    if any(m.valid_on(day) and m.frozen_on(day) for m in items):
        return None, "frozen"
    if any(m.is_membership for m in items):
        return None, "expired"
    return None, "no_membership"


# ---------------------------------------------------------------------------
# Selling
# ---------------------------------------------------------------------------
@dataclass
class Item:
    pricing_option: PricingOption | None = None
    variant: ProductVariant | None = None
    quantity: int = 1
    discount: Discount | None = None
    discount_reason: str = ""
    free_issue: bool = False
    free_issue_reason: str = ""
    start_date: datetime.date | None = None


@dataclass
class Pay:
    method: str
    amount: Decimal
    reference: str = ""


@dataclass
class Cart:
    items: list[Item] = field(default_factory=list)
    payments: list[Pay] = field(default_factory=list)


def _next_receipt_number(branch) -> int:
    counter, _ = ReceiptCounter.objects.get_or_create(branch=branch)
    counter = ReceiptCounter.objects.select_for_update().get(pk=counter.pk)
    counter.last_number += 1
    counter.save(update_fields=["last_number"])
    return counter.last_number


def _category(option: PricingOption, member) -> str:
    kind = option.kind
    if kind == PricingOption.Kind.MEMBERSHIP:
        had_before = (
            member is not None
            and Membership.objects.filter(member=member, pricing_option__kind=PricingOption.Kind.MEMBERSHIP)
            .exclude(status=Membership.Status.REFUNDED)
            .exists()
        )
        return SaleLine.Category.RENEW if had_before else SaleLine.Category.NEW
    return {
        PricingOption.Kind.TRIAL: SaleLine.Category.TRIAL,
        PricingOption.Kind.DAY_PASS: SaleLine.Category.DAY_PASS,
    }.get(kind, SaleLine.Category.OTHER)


def _check_discount(item: Item, member, branch, today, kind):
    discount = item.discount
    if discount is None:
        return
    if not discount.usable_on(today, branch.pk, kind):
        raise ValidationError(f"The discount '{discount.name}' can't be used here.")
    if discount.kind == Discount.Kind.MANUAL and not item.discount_reason.strip():
        raise ValidationError("A manual discount needs a reason.")
    if discount.kind == Discount.Kind.FAMILY:
        if member is None or not siblings(member).exists():
            raise ValidationError("The family discount needs a brother or sister who is also a member.")
        if item.pricing_option is not None and not item.pricing_option.family_discount_allowed:
            raise ValidationError("This pricing option does not take the family discount.")
    if discount.kind == Discount.Kind.REFERRAL:
        raise ValidationError("Referral rewards are applied automatically from the member's credit.")


def _membership_dates(option: PricingOption, member, start_date, today):
    days = option.validity_days
    if not days:
        return None
    start = start_date or today
    if member is not None and option.kind == PricingOption.Kind.MEMBERSHIP and start_date is None:
        # Renewing early doesn't lose days: the new period starts after the current one.
        current = (
            Membership.objects.filter(
                member=member,
                status=Membership.Status.ACTIVE,
                pricing_option__kind=PricingOption.Kind.MEMBERSHIP,
                end_date__gte=today,
            )
            .order_by("-end_date")
            .first()
        )
        if current is not None:
            start = current.end_date + datetime.timedelta(days=1)
    return start, start + datetime.timedelta(days=days - 1)


@transaction.atomic
def sell(
    *,
    branch,
    user,
    cart: Cart,
    member: Member | None = None,
    customer_name="",
    customer_mobile="",
    referred_by: Member | None = None,
    receipt_channels=(),
    note="",
) -> Sale:
    _need(user, "sales.sell", branch.pk, "You cannot sell at this branch.")
    if not cart.items:
        raise ValidationError("Add at least one item.")
    if member is None and not customer_name.strip():
        raise ValidationError("Choose a member, or enter the customer's name.")
    if customer_mobile:
        customer_mobile = normalize_kuwait_mobile(customer_mobile)
    today = timezone.localdate()

    sale = Sale(
        branch=branch,
        member=member,
        customer_name=customer_name.strip(),
        customer_mobile=customer_mobile,
        number=_next_receipt_number(branch),
        receipt_channels=list(receipt_channels),
        note=note,
        created_by=user,
        updated_by=user,
    )
    sale.save()

    subtotal = discount_total = ZERO
    new_membership_line = None
    for item in cart.items:
        if bool(item.pricing_option) == bool(item.variant):
            raise ValidationError("Each line is either a pricing option or a product size.")
        if item.quantity < 1:
            raise ValidationError("Quantity must be at least 1.")
        if item.pricing_option is not None:
            option = PricingOption.objects.select_for_update().get(pk=item.pricing_option.pk)
            if option.branch_id != branch.pk:
                raise ValidationError(f"'{option.name}' belongs to the other branch.")
            if not option.is_sellable(today):
                raise ValidationError(f"'{option.name}' is not approved or not on sale today.")
            if option.validity_days and item.quantity != 1:
                raise ValidationError("Sell memberships and passes one at a time.")
            if option.validity_days and member is None and option.kind == PricingOption.Kind.MEMBERSHIP:
                raise ValidationError("A membership must be sold to a member profile.")
            _check_discount(item, member, branch, today, option.kind)
            unit = option.price
            gross = unit * item.quantity
            disc = item.discount.value_for(gross) if item.discount else ZERO
            line = SaleLine(
                sale=sale,
                pricing_option=option,
                description=option.name,
                description_ar=option.name_ar,
                category=_category(option, member),
                quantity=item.quantity,
                unit_price=unit,
                discount=item.discount,
                discount_amount=disc,
                discount_reason=item.discount_reason.strip(),
                line_total=gross - disc,
            )
            # Referral credit: the oldest unused credit comes off a membership line.
            if member is not None and option.kind == PricingOption.Kind.MEMBERSHIP and line.line_total > 0:
                credit = (
                    ReferralCredit.objects.select_for_update()
                    .filter(referrer=member, used_on__isnull=True)
                    .order_by("created_at")
                    .first()
                )
                if credit is not None:
                    extra = min(credit.amount, line.line_total)
                    line.discount_amount += extra
                    line.line_total -= extra
                    line.discount_reason = (line.discount_reason + " · referral reward").strip(" ·")
                    line.save()
                    credit.used_on = line
                    credit.save(update_fields=["used_on"])
            if line.pk is None:
                line.save()
            dates = _membership_dates(option, member, item.start_date, today)
            if dates is not None and member is not None:
                Membership.objects.create(
                    member=member,
                    branch=branch,
                    pricing_option=option,
                    sale_line=line,
                    start_date=dates[0],
                    end_date=dates[1],
                    sessions_total=option.total_sessions,
                    created_by=user,
                    updated_by=user,
                )
                if line.category == SaleLine.Category.NEW:
                    new_membership_line = line
        else:
            from apps.inventory.services import move

            variant = ProductVariant.objects.select_related("product").get(pk=item.variant.pk)
            if not BranchStock.objects.filter(variant=variant, branch=branch).exists():
                raise ValidationError(f"{variant} is not stocked at this branch.")
            if item.free_issue and not item.free_issue_reason.strip():
                raise ValidationError("A free issue needs a reason (e.g. grading belt).")
            # Only this branch's own free stock can be sold (reserved online / in-transit stock can't).
            move(
                variant,
                branch,
                -item.quantity,
                "free_issue" if item.free_issue else "sale",
                user,
                reference=sale.reference,
                unit_cost=variant.cost,
                note=item.free_issue_reason.strip() if item.free_issue else "",
            )
            unit = ZERO if item.free_issue else variant.price
            gross = unit * item.quantity
            if item.discount is not None:
                _check_discount(item, member, branch, today, "equipment")
            disc = item.discount.value_for(gross) if item.discount and not item.free_issue else ZERO
            line = SaleLine.objects.create(
                sale=sale,
                variant=variant,
                description=f"{variant.product.name_en} · {variant.size}",
                description_ar=f"{variant.product.name_ar} · {variant.size}" if variant.product.name_ar else "",
                category=SaleLine.Category.EQUIPMENT,
                quantity=item.quantity,
                unit_price=unit,
                discount=item.discount if not item.free_issue else None,
                discount_amount=disc,
                discount_reason=(item.free_issue_reason if item.free_issue else item.discount_reason).strip(),
                line_total=gross - disc,
                free_issue=item.free_issue,
            )
        subtotal += line.unit_price * line.quantity
        discount_total += line.discount_amount

    total = subtotal - discount_total
    paid = sum((p.amount for p in cart.payments), ZERO)
    if paid != total:
        raise ValidationError(f"Payments ({paid:.3f} KD) must equal the total ({total:.3f} KD).")
    for pay in cart.payments:
        if pay.method not in Payment.Method.values:
            raise ValidationError("Choose KNET, card or cash.")
        if pay.amount <= 0:
            raise ValidationError("Each payment must be more than 0.")
        if pay.method in (Payment.Method.KNET, Payment.Method.CARD) and not pay.reference.strip():
            raise ValidationError("Enter the terminal reference for KNET and card payments.")
        Payment.objects.create(
            sale=sale, method=pay.method, amount=pay.amount, reference=pay.reference.strip(), received_by=user
        )

    sale.subtotal, sale.discount_total, sale.total = subtotal, discount_total, total
    sale.save(update_fields=["subtotal", "discount_total", "total"])

    if new_membership_line is not None and member is not None:
        from apps.leads.services import link_new_member, referrer_for

        if referred_by is None and new_membership_line.category == SaleLine.Category.NEW:
            referred_by = referrer_for(member)  # decision P5-8: the referral link or card
        link_new_member(member, sale)
    if referred_by is not None and new_membership_line is not None and referred_by.pk != member.pk:
        reward = Discount.objects.filter(kind=Discount.Kind.REFERRAL, is_enabled=True).first()
        if reward is not None and reward.amount:
            try:
                with transaction.atomic():
                    ReferralCredit.objects.create(referrer=referred_by, referred=member, amount=reward.amount)
            except IntegrityError:
                pass  # this new member already earned someone a reward
    record_event(
        action="sale", instance=sale, branch_id=branch.pk, changes={"reference": sale.reference, "total": str(total)}
    )
    transaction.on_commit(lambda: send_receipt(sale.pk))
    return sale


def receipt_text(sale: Sale, lang: str) -> str:
    lines = [
        ("إيصال أكاديمية إيليت" if lang == "ar" else "Elite Academy receipt") + f" {sale.reference}",
        sale.created_at.astimezone(timezone.get_current_timezone()).strftime("%Y-%m-%d %H:%M"),
    ]
    for line in sale.lines.all():
        name = line.description_ar if lang == "ar" and line.description_ar else line.description
        lines.append(f"{name} × {line.quantity}: {line.line_total:.3f} " + ("د.ك" if lang == "ar" else "KD"))
    lines.append(("المجموع" if lang == "ar" else "Total") + f": {sale.total:.3f} " + ("د.ك" if lang == "ar" else "KD"))
    return "\n".join(lines)


def send_receipt(sale_id: int):
    sale = Sale.objects.select_related("branch", "member").prefetch_related("lines").get(pk=sale_id)
    lang = contact_language(sale.member) if sale.member_id else "ar"
    channels = sale.receipt_channels or []
    mobile = contact_mobile(sale.member) if sale.member_id else sale.customer_mobile
    if "whatsapp" in channels and mobile:
        send_message(mobile, receipt_text(sale, lang))
    email = sale.member.email if sale.member_id else ""
    if "email" in channels and email:
        send_mail(
            f"Elite Academy receipt {sale.reference}", receipt_text(sale, "en"), None, [email], fail_silently=True
        )
    if channels:
        Sale.objects.filter(pk=sale.pk).update(receipt_sent_at=timezone.now())


# ---------------------------------------------------------------------------
# Freeze, refund and cancellation
# ---------------------------------------------------------------------------
@transaction.atomic
def request_change(
    *,
    kind,
    user,
    reason,
    membership: Membership | None = None,
    sale: Sale | None = None,
    freeze_start=None,
    freeze_weeks=None,
    refund_amount=None,
    refund_method="",
) -> AccountRequest:
    branch = membership.branch if membership else (sale.branch if sale else None)
    if branch is None:
        raise ValidationError("Choose the membership or sale.")
    _need(user, "sales.request", branch.pk, "You cannot log requests for this branch.")
    if not reason.strip():
        raise ValidationError("Give the member's reason.")
    today = timezone.localdate()
    if AccountRequest.objects.filter(
        membership=membership, sale=sale, status=AccountRequest.Status.PENDING, kind=kind
    ).exists():
        raise ValidationError("There is already a pending request of this kind.")
    if kind == AccountRequest.Kind.FREEZE:
        if membership is None or not membership.is_membership:
            raise ValidationError("Only memberships can be frozen.")
        if membership.freeze_used:
            raise ValidationError("This membership has already been frozen once.")
        if not (freeze_weeks and FREEZE_MIN_WEEKS <= int(freeze_weeks) <= FREEZE_MAX_WEEKS):
            raise ValidationError("A freeze is 1 to 4 weeks.")
        if freeze_start is None or freeze_start < today or freeze_start > membership.end_date:
            raise ValidationError("The freeze must start today or later, before the membership ends.")
    elif kind == AccountRequest.Kind.REFUND:
        source = membership.sale_line.sale if membership and membership.sale_line_id else sale
        if source is None:
            raise ValidationError("There is no sale to refund.")
        already = -sum((s.total for s in source.refunds.all()), ZERO)
        if refund_amount is None or refund_amount <= 0 or refund_amount > source.total - already:
            raise ValidationError(f"The refund can be at most {source.total - already:.3f} KD.")
        if refund_method not in Payment.Method.values:
            raise ValidationError("Choose how the money goes back: KNET, card or cash.")
        sale = source
    elif kind == AccountRequest.Kind.CANCEL:
        if membership is None or membership.status != Membership.Status.ACTIVE:
            raise ValidationError("Only an active membership can be cancelled.")
    req = AccountRequest.objects.create(
        kind=kind,
        membership=membership,
        sale=sale,
        branch=branch,
        reason=reason.strip(),
        freeze_start=freeze_start,
        freeze_weeks=freeze_weeks,
        refund_amount=refund_amount,
        refund_method=refund_method,
        created_by=user,
        updated_by=user,
    )
    record_event(action=f"{kind}_requested", instance=req, branch_id=branch.pk)
    return req


@transaction.atomic
def decide_request(req: AccountRequest, approve: bool, user, note="") -> AccountRequest:
    req = AccountRequest.objects.select_for_update().get(pk=req.pk)
    if req.status != AccountRequest.Status.PENDING:
        raise ValidationError("This request has already been decided.")
    _need(user, "sales.approve_refund", req.branch_id, "Only the Operations Manager decides these requests.")
    if req.created_by_id == user.pk:
        raise PermissionDenied("A request you logged must be decided by someone else.")
    req.status = AccountRequest.Status.APPROVED if approve else AccountRequest.Status.REJECTED
    req.decided_by, req.decided_at, req.decision_note = user, timezone.now(), note
    if approve:
        _apply_request(req, user)
    req.save()
    record_event(action=f"{req.kind}_{'approved' if approve else 'rejected'}", instance=req, branch_id=req.branch_id)
    return req


def _apply_request(req: AccountRequest, user):
    today = timezone.localdate()
    if req.kind == AccountRequest.Kind.FREEZE:
        m = Membership.objects.select_for_update().get(pk=req.membership_id)
        Freeze.objects.create(membership=m, start_date=req.freeze_start, end_date=req.freeze_end, request=req)
        m.end_date += datetime.timedelta(weeks=req.freeze_weeks)
        m.freeze_used = True
        m.save(update_fields=["end_date", "freeze_used", "updated_at"])
    elif req.kind == AccountRequest.Kind.CANCEL:
        m = Membership.objects.select_for_update().get(pk=req.membership_id)
        m.status = Membership.Status.CANCELLED
        m.end_date = min(m.end_date, today)
        m.save(update_fields=["status", "end_date", "updated_at"])
    elif req.kind == AccountRequest.Kind.REFUND:
        original = req.sale
        refund = Sale.objects.create(
            branch=req.branch,
            kind=Sale.Kind.REFUND,
            member=original.member,
            customer_name=original.customer_name,
            refund_of=original,
            number=_next_receipt_number(req.branch),
            subtotal=-req.refund_amount,
            total=-req.refund_amount,
            note=f"Refund of {original.reference}",
            created_by=user,
            updated_by=user,
        )
        SaleLine.objects.create(
            sale=refund,
            description=f"Refund · {original.reference}",
            description_ar=f"استرداد · {original.reference}",
            category=original.lines.first().category if original.lines.exists() else "other",
            quantity=1,
            unit_price=-req.refund_amount,
            line_total=-req.refund_amount,
        )
        Payment.objects.create(
            sale=refund,
            method=req.refund_method,
            amount=-req.refund_amount,
            reference=f"REFUND-{original.reference}",
            received_by=user,
        )
        req.refund_sale = refund
        if req.membership_id:
            Membership.objects.filter(pk=req.membership_id).update(status=Membership.Status.REFUNDED, end_date=today)
        # Returned equipment goes back on the shelf at the branch that sold it.
        if req.refund_amount >= original.total:
            from apps.inventory.services import move

            for line in original.lines.filter(variant__isnull=False):
                move(
                    line.variant_id,
                    original.branch,
                    line.quantity,
                    "refund",
                    user,
                    reference=refund.reference,
                    check=False,
                )


# ---------------------------------------------------------------------------
# End-of-day cash-up
# ---------------------------------------------------------------------------
def expected_totals(branch, day):
    start, end = day_range(day)
    payments = Payment.objects.filter(sale__branch=branch, received_at__gte=start, received_at__lt=end)
    totals = {m: payments.filter(method=m).aggregate(t=Sum("amount"))["t"] or ZERO for m in Payment.Method.values}
    return totals


def cash_paid_out(branch, day):
    """Expenses paid from the drawer that day (decision P2-12). Rejected ones must go back in the drawer."""
    from apps.finance.models import Expense

    return (
        Expense.objects.filter(branch=branch, date=day, paid_from=Expense.PaidFrom.DRAWER)
        .exclude(status=Expense.Status.REJECTED)
        .aggregate(t=Sum("amount"))["t"]
        or ZERO
    )


def _apply_expected(cash_up):
    totals = expected_totals(cash_up.branch, cash_up.date)
    cash_up.cash_paid_out = cash_paid_out(cash_up.branch, cash_up.date)
    cash_up.expected_cash = totals["cash"] - cash_up.cash_paid_out
    cash_up.expected_knet, cash_up.expected_card = totals["knet"], totals["card"]


@transaction.atomic
def open_cash_up(branch, day, user) -> CashUp:
    _need(user, "sales.cashup", branch.pk, "You cannot do the cash-up for this branch.")
    cash_up, _ = CashUp.objects.select_for_update().get_or_create(
        branch=branch, date=day, defaults={"created_by": user, "updated_by": user}
    )
    if cash_up.status == CashUp.Status.DRAFT:
        _apply_expected(cash_up)
        cash_up.save(update_fields=["expected_cash", "cash_paid_out", "expected_knet", "expected_card", "updated_at"])
    return cash_up


@transaction.atomic
def submit_cash_up(cash_up: CashUp, user, *, counted_cash, terminal_knet, terminal_card, reason="") -> CashUp:
    cash_up = CashUp.objects.select_for_update().get(pk=cash_up.pk)
    _need(user, "sales.cashup", cash_up.branch_id, "You cannot do the cash-up for this branch.")
    if cash_up.status != CashUp.Status.DRAFT:
        raise ValidationError("This cash-up has already been submitted.")
    _apply_expected(cash_up)  # recalculate: sales and expenses may have happened since opening
    cash_up.counted_cash, cash_up.terminal_knet, cash_up.terminal_card = counted_cash, terminal_knet, terminal_card
    cash_up.reason = reason.strip()
    if cash_up.needs_reason and not cash_up.reason:
        raise ValidationError(f"Explain any difference above {CashUp.REASON_THRESHOLD:.3f} KD.")
    cash_up.status = CashUp.Status.SUBMITTED
    cash_up.submitted_by, cash_up.submitted_at = user, timezone.now()
    cash_up.updated_by = user
    cash_up.save()
    record_event(
        action="cash_up_submitted",
        instance=cash_up,
        branch_id=cash_up.branch_id,
        changes={
            "cash": str(cash_up.cash_difference),
            "knet": str(cash_up.knet_difference),
            "card": str(cash_up.card_difference),
        },
    )
    transaction.on_commit(lambda: _notify_cash_up(cash_up.pk))
    return cash_up


def _notify_cash_up(cash_up_id):
    """Sent to the Operations Manager and the Accountant (scope M5)."""
    from apps.rbac.models import RoleAssignment

    cash_up = CashUp.objects.select_related("branch").get(pk=cash_up_id)
    text = (
        f"Cash-up {cash_up.branch.code} {cash_up.date}: cash {cash_up.cash_difference:+.3f}, "
        f"KNET {cash_up.knet_difference:+.3f}, card {cash_up.card_difference:+.3f} KD."
        + (f" Reason: {cash_up.reason}" if cash_up.reason else "")
    )
    users = {
        a.user
        for a in RoleAssignment.objects.current()
        .filter(role__code__in=["operations_manager", "accountant"])
        .select_related("user")
    }
    for u in users:
        if u.mobile:
            send_message(u.mobile, text)


@transaction.atomic
def verify_cash_up(cash_up: CashUp, user) -> CashUp:
    cash_up = CashUp.objects.select_for_update().get(pk=cash_up.pk)
    if not (has_perm(user, "reports.verify", cash_up.branch_id) or has_perm(user, "finance.manage", cash_up.branch_id)):
        raise PermissionDenied("Only the Operations Manager or the Accountant verifies cash-ups.")
    if cash_up.status != CashUp.Status.SUBMITTED:
        raise ValidationError("Only a submitted cash-up can be verified.")
    if cash_up.submitted_by_id == user.pk:
        raise PermissionDenied("Someone else must verify your cash-up.")
    cash_up.status, cash_up.verified_by, cash_up.verified_at = CashUp.Status.VERIFIED, user, timezone.now()
    cash_up.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    record_event(action="cash_up_verified", instance=cash_up, branch_id=cash_up.branch_id)
    return cash_up
