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

from .models import PriceChange, PricingOption


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
