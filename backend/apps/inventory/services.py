"""
Inventory rules (scope M8, business rules 6–10, EA-INV-PROC-01 v3.1, decisions P3-1 to P3-7).

Every change to a branch's stock goes through `move()`, which locks the stock row, writes the
ledger (StockMovement) and refreshes what the online shop may sell. Nothing else writes
BranchStock.quantity.
"""

import calendar
import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.audit.services import record_event
from apps.core.files import clean_document
from apps.core.messaging import send_message
from apps.operations.services import next_number, next_reference
from apps.organization.models import Branch
from apps.rbac.services import has_perm, notify_perm
from apps.shop.models import BranchStock, ProductVariant

from .models import (
    Discrepancy,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequest,
    PurchaseRequestLine,
    Receipt,
    ReceiptLine,
    StockCount,
    StockCountLine,
    StockMovement,
    Transfer,
    TransferLine,
)

D = Decimal
ZERO = D("0.000")
REASON_CODES = [c for c, *_ in StockCount.REASONS]
BUSINESS_DAYS = {6, 0, 1, 2, 3}  # Sunday–Thursday (Python weekdays), decision P3-3


def kd(value) -> Decimal:
    return D(value).quantize(D("0.001"), rounding=ROUND_HALF_UP)


def _need(user, perm, branch_id, message):
    if not has_perm(user, perm, branch_id):
        raise PermissionDenied(message)


def receiving_branch():
    """All vendor deliveries are received at Promenade (rule 8)."""
    return Branch.objects.get(code=getattr(settings, "RECEIVING_BRANCH_CODE", "PRM"))


# ---------------------------------------------------------------------------
# Business days (Sunday–Thursday, not public holidays)
# ---------------------------------------------------------------------------
def _holidays(start, end):
    from apps.payroll.models import PublicHoliday

    return set(PublicHoliday.objects.filter(date__range=(start, end)).values_list("date", flat=True))


def is_business_day(day, holidays=None) -> bool:
    holidays = _holidays(day, day) if holidays is None else holidays
    return day.weekday() in BUSINESS_DAYS and day not in holidays


def add_business_days(moment, days: int):
    """The same time of day, `days` business days later (e.g. submitted Thursday 17:00 → Monday 17:00)."""
    local = timezone.localtime(moment)
    day, n = local.date(), 0
    holidays = _holidays(day, day + datetime.timedelta(days=days * 3 + 10))
    while n < days:
        day += datetime.timedelta(days=1)
        if is_business_day(day, holidays):
            n += 1
    return timezone.make_aware(datetime.datetime.combine(day, local.time()))


def nth_working_day(month_first, n: int):
    day, count = month_first, 0
    holidays = _holidays(month_first, month_first + datetime.timedelta(days=40))
    while True:
        if is_business_day(day, holidays):
            count += 1
            if count == n:
                return day
        day += datetime.timedelta(days=1)


def last_working_day(month_first):
    day = month_first.replace(day=calendar.monthrange(month_first.year, month_first.month)[1])
    holidays = _holidays(month_first, day)
    while not is_business_day(day, holidays):
        day -= datetime.timedelta(days=1)
    return day


# ---------------------------------------------------------------------------
# The stock ledger
# ---------------------------------------------------------------------------
def _stock(variant, branch) -> BranchStock:
    stock, _ = BranchStock.objects.get_or_create(variant_id=getattr(variant, "pk", variant), branch=branch)
    return BranchStock.objects.select_for_update().get(pk=stock.pk)


def refresh_online(variant_id):
    """What the website may sell = stock available at the branches (never below zero)."""
    variant = ProductVariant.objects.select_related("product").get(pk=variant_id)
    if not (variant.product.is_active and variant.product.sell_online and variant.is_active):
        available = 0
    else:
        agg = BranchStock.objects.filter(variant=variant).aggregate(q=Sum("quantity"), r=Sum("reserved"))
        available = max((agg["q"] or 0) - (agg["r"] or 0), 0)
    if variant.stock != available:
        ProductVariant.objects.filter(pk=variant.pk).update(stock=available)
    return available


@transaction.atomic
def move(
    variant,
    branch,
    change: int,
    kind,
    user=None,
    *,
    reference="",
    unit_cost=None,
    reason="",
    note="",
    check=True,
    at=None,
):
    """Changes the shelf stock at one branch and writes the ledger. `check` refuses to go below what is free."""
    stock = _stock(variant, branch)
    if check and change < 0 and stock.available + change < 0:
        name = variant if isinstance(variant, ProductVariant) else ProductVariant.objects.get(pk=variant)
        raise ValidationError(f"Only {max(stock.available, 0)} of {name} available at {branch.name}.")
    stock.quantity += change
    stock.save(update_fields=["quantity"])
    movement = StockMovement.objects.create(
        variant_id=stock.variant_id,
        branch=branch,
        change=change,
        balance=stock.quantity,
        kind=kind,
        reference=reference[:40],
        unit_cost=unit_cost,
        reason=reason,
        note=note[:255],
        user=user,
        created_at=at or timezone.now(),
    )
    refresh_online(stock.variant_id)
    return movement


@transaction.atomic
def reserve(variant, branch, quantity: int):
    stock = _stock(variant, branch)
    if stock.available < quantity:
        raise ValidationError(f"Only {max(stock.available, 0)} available at {branch.name}.")
    stock.reserved += quantity
    stock.save(update_fields=["reserved"])
    refresh_online(stock.variant_id)
    return stock


@transaction.atomic
def release(variant, branch, quantity: int):
    stock = _stock(variant, branch)
    stock.reserved = max(stock.reserved - quantity, 0)
    stock.save(update_fields=["reserved"])
    refresh_online(stock.variant_id)
    return stock


@transaction.atomic
def set_opening(
    variant, branch, quantity: int, user=None, note="Opening balance", kind=StockMovement.Kind.OPENING, at=None
):
    """Brings a branch's shelf to `quantity` with an opening (or import) entry in the ledger."""
    stock = _stock(variant, branch)
    change = quantity - stock.quantity
    if change:
        return move(variant, branch, change, kind, user, note=note, check=False, at=at)
    return None


def stock_value(branch=None) -> Decimal:
    qs = BranchStock.objects.filter(quantity__gt=0).select_related("variant")
    if branch is not None:
        qs = qs.filter(branch=branch)
    return kd(sum((s.quantity * s.variant.cost for s in qs), ZERO))


@transaction.atomic
def adjust(variant, branch, new_quantity: int, user, reason_code: str, note: str):
    """A one-off correction outside the monthly count: the OM only, with a reason code (rule 10)."""
    _need(user, "inventory.approve", branch.pk, "Only the Operations Manager corrects stock.")
    if reason_code not in REASON_CODES:
        raise ValidationError("Choose a reason code.")
    if not note.strip():
        raise ValidationError("Write why the stock is corrected.")
    stock = _stock(variant, branch)
    change = new_quantity - stock.quantity
    if change == 0:
        raise ValidationError("That is already the stock on the shelf.")
    return move(variant, branch, change, StockMovement.Kind.ADJUST, user, reason=reason_code, note=note, check=False)


# ---------------------------------------------------------------------------
# Purchase requests (FRM-05)
# ---------------------------------------------------------------------------
@transaction.atomic
def submit_request(branch, user, *, vendor_type, lines, vendor=None, note="") -> PurchaseRequest:
    """lines = [{"variant": v or None, "item": "", "size": "", "quantity": n, "reason": ""}]"""
    _need(user, "inventory.manage", branch.pk, "You cannot request purchases for this branch.")
    lines = [ln for ln in lines if ln.get("quantity")]
    if not lines:
        raise ValidationError("Add at least one item with a quantity.")
    for ln in lines:
        if ln["quantity"] < 1:
            raise ValidationError("Quantities must be at least 1.")
        if not ln.get("variant") and not (ln.get("item") or "").strip():
            raise ValidationError("Each line needs a product or an item name.")
    if vendor_type == PurchaseRequest.VendorType.LOCAL:
        month_start = timezone.localdate().replace(day=1)
        s0 = timezone.make_aware(datetime.datetime.combine(month_start, datetime.time.min))
        taken = (
            PurchaseRequest.objects.select_for_update()
            .filter(branch=branch, vendor_type="local", created_at__gte=s0)
            .exclude(status=PurchaseRequest.Status.REJECTED)
            .exists()
        )
        if taken:
            raise ValidationError("Local purchase requests are limited to one per branch per calendar month.")
    req = PurchaseRequest.objects.create(
        reference=next_reference("PRF", branch),
        branch=branch,
        vendor_type=vendor_type,
        vendor=vendor,
        note=note.strip()[:255],
        due_at=add_business_days(timezone.now(), 2),
        created_by=user,
        updated_by=user,
    )
    PurchaseRequestLine.objects.bulk_create(
        [
            PurchaseRequestLine(
                request=req,
                variant=ln.get("variant"),
                item=(ln.get("item") or "").strip()[:120],
                size=(ln.get("size") or "").strip()[:30],
                quantity=ln["quantity"],
                reason=(ln.get("reason") or "").strip()[:200],
            )
            for ln in lines
        ]
    )
    due = timezone.localtime(req.due_at)
    text = f"Purchase request {req.reference} from {branch.name} ({len(lines)} line(s)) — decide by {due:%a %d/%m}."
    transaction.on_commit(lambda: notify_perm("inventory.approve", text, branch.pk, exclude=user))
    return req


@transaction.atomic
def decide_request(req: PurchaseRequest, user, decision: str, note="", amended=None) -> PurchaseRequest:
    req = PurchaseRequest.objects.select_for_update().get(pk=req.pk)
    _need(user, "inventory.approve", req.branch_id, "Only the Operations Manager decides purchase requests.")
    if req.created_by_id == user.pk:
        raise PermissionDenied("Someone else must decide a request you made.")
    if req.status != PurchaseRequest.Status.SUBMITTED:
        raise ValidationError("This request has already been decided.")
    if decision in ("reject", "amend") and not note.strip():
        raise ValidationError("Give the reason for rejecting or amending — the branch is told.")
    lines = list(req.lines.all())
    if decision == "reject":
        req.status = PurchaseRequest.Status.REJECTED
    elif decision == "amend":
        amended = amended or {}
        for ln in lines:
            ln.approved_quantity = max(int(amended.get(ln.pk, ln.quantity)), 0)
            ln.save(update_fields=["approved_quantity"])
        if not any(ln.approved_quantity for ln in lines):
            raise ValidationError("Nothing is left to order — reject the request instead.")
        req.status = PurchaseRequest.Status.AMENDED
    elif decision == "approve":
        for ln in lines:
            ln.approved_quantity = ln.quantity
            ln.save(update_fields=["approved_quantity"])
        req.status = PurchaseRequest.Status.APPROVED
    else:
        raise ValidationError("Unknown decision.")
    req.decided_by, req.decided_at, req.decision_note, req.updated_by = user, timezone.now(), note.strip()[:255], user
    req.save()
    requester = req.created_by
    if requester is not None and requester.mobile:
        verdict = {"approved": "approved", "amended": "approved with changes", "rejected": "rejected"}[req.status]
        text = f"Purchase request {req.reference} was {verdict}." + (
            f" {req.decision_note}" if req.decision_note else ""
        )
        transaction.on_commit(lambda: send_message(requester.mobile, text, category="staff"))
    if req.status != PurchaseRequest.Status.REJECTED:
        transaction.on_commit(
            lambda: notify_perm("inventory.purchase", f"{req.reference} approved — ready to order.", exclude=user)
        )
    return req


def remind_overdue_requests(now=None) -> int:
    now = now or timezone.now()
    n = 0
    for req in PurchaseRequest.objects.filter(status="submitted", due_at__lt=now, reminder_sent=False):
        if PurchaseRequest.objects.filter(pk=req.pk, reminder_sent=False).update(reminder_sent=True):
            notify_perm(
                "inventory.approve",
                f"Purchase request {req.reference} is past its 2-business-day decision time.",
                req.branch_id,
            )
            n += 1
    return n


# ---------------------------------------------------------------------------
# Purchase orders (EA-PO-YYYY-NNN) and landed cost
# ---------------------------------------------------------------------------
@transaction.atomic
def create_order(user, vendor, requests, **terms) -> PurchaseOrder:
    _need(user, "inventory.purchase", None, "Only the Purchasing Coordinator or the OM places orders.")
    requests = list(PurchaseRequest.objects.select_for_update().filter(pk__in=[r.pk for r in requests]))
    if not requests:
        raise ValidationError("Choose at least one approved purchase request (no order without approval — rule 7).")
    for r in requests:
        if r.status not in PurchaseRequest.OPEN_FOR_ORDER:
            raise ValidationError(f"{r.reference} is not approved.")
    home = receiving_branch()
    year = timezone.localdate().year
    order = PurchaseOrder.objects.create(
        reference=f"EA-PO-{year}-{next_number('EA-PO', home, year):03d}",
        vendor=vendor,
        currency=(terms.get("currency") or vendor.currency or "KWD").upper(),
        exchange_rate=D(str(terms.get("exchange_rate") or 1)),
        freight_kwd=D(str(terms.get("freight_kwd") or 0)),
        customs_percent=D(str(terms.get("customs_percent", 20))),
        target_margin=D(str(terms.get("target_margin", 50))),
        language=terms.get("language", "ar"),
        note=(terms.get("note") or "").strip(),
        created_by=user,
        updated_by=user,
    )
    order.requests.set(requests)
    merged = {}
    for r in requests:
        for ln in r.lines.all():
            if not ln.final_quantity:
                continue
            key = ("v", ln.variant_id) if ln.variant_id else ("i", ln.item.lower(), ln.size.lower())
            if key in merged:
                merged[key]["quantity"] += ln.final_quantity
            else:
                cost = ln.variant.cost if ln.variant_id else ZERO
                rate = order.exchange_rate or D(1)
                merged[key] = {
                    "variant": ln.variant,
                    "item": ln.item,
                    "size": ln.size,
                    "quantity": ln.final_quantity,
                    "unit_price": kd(cost / rate) if order.currency == "KWD" else ZERO,
                }
    PurchaseOrderLine.objects.bulk_create([PurchaseOrderLine(order=order, **v) for v in merged.values()])
    PurchaseRequest.objects.filter(pk__in=[r.pk for r in requests]).update(status=PurchaseRequest.Status.ORDERED)
    return order


@transaction.atomic
def update_order(order: PurchaseOrder, user, *, prices=None, **terms) -> PurchaseOrder:
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    _need(user, "inventory.purchase", None, "Only the Purchasing Coordinator or the OM edits orders.")
    if order.status != PurchaseOrder.Status.DRAFT:
        raise ValidationError("An order that has been sent can't be changed.")
    for field in ("currency", "exchange_rate", "freight_kwd", "customs_percent", "target_margin", "language", "note"):
        if field in terms and terms[field] not in (None, ""):
            value = terms[field]
            setattr(
                order,
                field,
                value.upper()
                if field == "currency"
                else (D(str(value)) if field not in ("language", "note") else value),
            )
    if order.currency == "KWD":
        order.exchange_rate = D(1)
    if order.exchange_rate <= 0:
        raise ValidationError("The exchange rate must be above zero.")
    order.updated_by = user
    order.save()
    for line_id, price in (prices or {}).items():
        PurchaseOrderLine.objects.filter(order=order, pk=line_id).update(unit_price=D(str(price)))
    return order


@transaction.atomic
def send_order(order: PurchaseOrder, user) -> PurchaseOrder:
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    _need(user, "inventory.purchase", None, "Only the Purchasing Coordinator or the OM sends orders.")
    if order.status != PurchaseOrder.Status.DRAFT:
        raise ValidationError("This order has already been sent.")
    if any(ln.unit_price <= 0 for ln in order.lines.all()):
        raise ValidationError("Enter the vendor's unit price on every line first.")
    order.status, order.sent_at, order.updated_by = PurchaseOrder.Status.SENT, timezone.now(), user
    order.save()
    record_event(action="purchase_order_sent", instance=order)
    return order


def landed_costs(order: PurchaseOrder) -> list[dict]:
    """
    Per line: landed unit cost in KD = unit × rate × (1 + customs %) + freight share (by value),
    margin at the current retail price, and the counter-price that would reach the target margin.
    """
    lines = list(order.lines.select_related("variant__product"))
    rate, customs = order.exchange_rate or D(1), order.customs_percent / D(100)
    target = order.target_margin / D(100)
    total_value = sum((ln.unit_price * ln.quantity * rate for ln in lines), ZERO)
    total_qty = sum((ln.quantity for ln in lines), 0) or 1
    out = []
    for ln in lines:
        value = ln.unit_price * ln.quantity * rate
        share = order.freight_kwd * (value / total_value if total_value else D(ln.quantity) / D(total_qty))
        freight_unit = share / ln.quantity if ln.quantity else ZERO
        landed = ln.unit_price * rate * (1 + customs) + freight_unit
        sell = ln.variant.price if ln.variant_id else None
        margin = ((sell - landed) / sell * 100).quantize(D("0.1")) if sell else None
        counter = None
        if sell:
            counter = max((sell * (1 - target) - freight_unit) / (rate * (1 + customs)), ZERO).quantize(D("0.01"))
        out.append(
            {
                "line": ln,
                "landed": kd(landed),
                "sell": sell,
                "margin": margin,
                "counter_price": counter,
                "meets_target": margin is not None and margin >= order.target_margin,
                "value_kwd": kd(value),
            }
        )
    return out


def order_totals(order):
    rows = landed_costs(order)
    value = sum((r["value_kwd"] for r in rows), ZERO)
    landed = sum((r["landed"] * r["line"].quantity for r in rows), ZERO)
    with_margin = [r for r in rows if r["sell"]]
    sales = sum((r["sell"] * r["line"].quantity for r in with_margin), ZERO)
    cost = sum((r["landed"] * r["line"].quantity for r in with_margin), ZERO)
    margin = ((sales - cost) / sales * 100).quantize(D("0.1")) if sales else None
    return {
        "value": kd(value),
        "landed": kd(landed),
        "margin": margin,
        "quantity": sum(r["line"].quantity for r in rows),
    }


# ---------------------------------------------------------------------------
# Receiving (FRM-01) and discrepancies (FRM-04)
# ---------------------------------------------------------------------------
@transaction.atomic
def receive(
    user, *, vendor, invoice_number, lines, order=None, invoice_file=None, received_on=None, note=""
) -> Receipt:
    """lines = [{"variant": v, "invoiced": n, "received": n, "note": "", "order_line": ol or None}]"""
    home = receiving_branch()
    _need(user, "inventory.purchase", home.pk, "Deliveries are received at Promenade by the Purchasing Coordinator.")
    if not invoice_number.strip():
        raise ValidationError("Enter the vendor's invoice number.")
    lines = [ln for ln in lines if ln.get("invoiced") or ln.get("received")]
    if not lines:
        raise ValidationError("Enter what was invoiced and what arrived.")
    if order is not None:
        order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
        if order.status not in (PurchaseOrder.Status.SENT, PurchaseOrder.Status.PARTIAL):
            raise ValidationError("Receive only against an order that was sent to the vendor.")
    landed = {r["line"].pk: r["landed"] for r in landed_costs(order)} if order else {}
    receipt = Receipt(
        reference=next_reference("IRF", home),
        order=order,
        vendor=vendor,
        branch=home,
        invoice_number=invoice_number.strip()[:60],
        received_on=received_on or timezone.localdate(),
        received_by=user,
        note=note.strip()[:255],
        created_by=user,
        updated_by=user,
    )
    if invoice_file is not None:
        receipt.invoice.save("invoice", clean_document(invoice_file), save=False)
    receipt.save()
    short = False
    for ln in lines:
        variant, invoiced, received = ln["variant"], int(ln.get("invoiced") or 0), int(ln.get("received") or 0)
        if invoiced < 0 or received < 0:
            raise ValidationError("Quantities can't be negative.")
        order_line = ln.get("order_line")
        cost = landed.get(order_line.pk) if order_line else None
        cost = cost if cost is not None else variant.cost
        ReceiptLine.objects.create(
            receipt=receipt,
            order_line=order_line,
            variant=variant,
            invoiced_quantity=invoiced,
            received_quantity=received,
            unit_cost=cost,
            note=(ln.get("note") or "")[:200],
        )
        if received:
            move(
                variant,
                home,
                received,
                StockMovement.Kind.RECEIPT,
                user,
                reference=receipt.reference,
                unit_cost=cost,
                check=False,
            )
            if cost:
                ProductVariant.objects.filter(pk=variant.pk).update(cost=cost)  # decision P3-6
        if order_line is not None:
            PurchaseOrderLine.objects.filter(pk=order_line.pk).update(
                received_quantity=order_line.received_quantity + received
            )
        short = short or invoiced != received
    if order is not None:
        remaining = sum(ln.outstanding for ln in order.lines.all())
        order.status = PurchaseOrder.Status.RECEIVED if remaining == 0 else PurchaseOrder.Status.PARTIAL
        order.save(update_fields=["status", "updated_at"])
        if remaining == 0:
            order.requests.update(status=PurchaseRequest.Status.RECEIVED)
    if short:
        disc = Discrepancy.objects.create(
            reference=next_reference("MDR", home), receipt=receipt, created_by=user, updated_by=user
        )
        text = (
            f"{disc.reference}: delivery {receipt.reference} from {vendor.name} "
            f"(invoice {receipt.invoice_number}) doesn't match the invoice."
        )
        transaction.on_commit(lambda: notify_perm("inventory.approve", text, home.pk, exclude=user))
    return receipt


@transaction.atomic
def update_discrepancy(
    disc: Discrepancy, user, *, vendor_notified_on=None, resolution="", resolve=False
) -> Discrepancy:
    disc = Discrepancy.objects.select_for_update().get(pk=disc.pk)
    if not (has_perm(user, "inventory.purchase") or has_perm(user, "inventory.approve")):
        raise PermissionDenied("Only purchasing or the OM follow up discrepancies.")
    if vendor_notified_on:
        disc.vendor_notified_on = vendor_notified_on
    if resolution.strip():
        disc.resolution = (disc.resolution + "\n" if disc.resolution else "") + resolution.strip()
    if resolve:
        if not disc.vendor_notified_on:
            raise ValidationError("Record when the vendor was told before resolving.")
        if not disc.resolution:
            raise ValidationError("Write how it was resolved (credit note, replacement…).")
        disc.status, disc.resolved_by, disc.resolved_at = Discrepancy.Status.RESOLVED, user, timezone.now()
    disc.updated_by = user
    disc.save()
    return disc


# ---------------------------------------------------------------------------
# Transfers (FRM-03): ownership moves only when the receiver accepts (rule 9)
# ---------------------------------------------------------------------------
@transaction.atomic
def send_transfer(from_branch, to_branch, user, lines, *, receipt=None, note="") -> Transfer:
    if not (has_perm(user, "inventory.manage", from_branch.pk) or has_perm(user, "inventory.purchase", from_branch.pk)):
        raise PermissionDenied("You cannot send stock from this branch.")
    if from_branch == to_branch:
        raise ValidationError("Choose a different receiving branch.")
    lines = [(v, int(q)) for v, q in lines if q and int(q) > 0]
    if not lines:
        raise ValidationError("Add at least one item and quantity.")
    transfer = Transfer.objects.create(
        reference=next_reference("ITF", from_branch),
        from_branch=from_branch,
        to_branch=to_branch,
        receipt=receipt,
        sent_by=user,
        note=note.strip()[:255],
        created_by=user,
        updated_by=user,
    )
    for variant, qty in sorted(lines, key=lambda x: x[0].pk):  # fixed lock order
        reserve(variant, from_branch, qty)  # held in transit: can't be sold while travelling
        TransferLine.objects.create(transfer=transfer, variant=variant, quantity=qty)
    text = f"Transfer {transfer.reference} from {from_branch.name} is on its way: count it and accept it in the desk."
    transaction.on_commit(lambda: notify_perm("inventory.manage", text, to_branch.pk, exclude=user))
    return transfer


@transaction.atomic
def accept_transfer(transfer: Transfer, user, received: dict, *, called_sender_and_om=False, note="") -> Transfer:
    transfer = Transfer.objects.select_for_update().get(pk=transfer.pk)
    _need(user, "inventory.manage", transfer.to_branch_id, "Only the receiving branch accepts a transfer.")
    if transfer.sent_by_id == user.pk:
        raise PermissionDenied("The person who sent the transfer can't accept it.")
    if transfer.status != Transfer.Status.SENT:
        raise ValidationError("This transfer is no longer waiting.")
    lines = list(transfer.lines.select_related("variant").order_by("variant_id"))
    counts = {ln.pk: int(received.get(ln.pk, ln.quantity)) for ln in lines}
    if any(c < 0 for c in counts.values()):
        raise ValidationError("Counts can't be negative.")
    mismatch = any(counts[ln.pk] != ln.quantity for ln in lines)
    if mismatch and not (called_sender_and_om and note.strip()):
        raise ValidationError("The count doesn't match. Call the sender and the OM, tick that you did, and explain.")
    for ln in lines:
        release(ln.variant, transfer.from_branch, ln.quantity)
        move(
            ln.variant,
            transfer.from_branch,
            -ln.quantity,
            StockMovement.Kind.TRANSFER_OUT,
            user,
            reference=transfer.reference,
            check=False,
        )
        if counts[ln.pk]:
            move(
                ln.variant,
                transfer.to_branch,
                counts[ln.pk],
                StockMovement.Kind.TRANSFER_IN,
                user,
                reference=transfer.reference,
                check=False,
            )
        ln.received_quantity = counts[ln.pk]
        ln.save(update_fields=["received_quantity"])
    transfer.status, transfer.accepted_by, transfer.accepted_at = Transfer.Status.ACCEPTED, user, timezone.now()
    transfer.mismatch, transfer.mismatch_note, transfer.updated_by = mismatch, note.strip()[:255], user
    transfer.save()
    if mismatch:
        text = f"Transfer {transfer.reference} arrived short at {transfer.to_branch.name}: {transfer.mismatch_note}"
        transaction.on_commit(lambda: notify_perm("inventory.approve", text, transfer.to_branch_id, exclude=user))
    return transfer


@transaction.atomic
def cancel_transfer(transfer: Transfer, user) -> Transfer:
    transfer = Transfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.sent_by_id != user.pk and not has_perm(user, "inventory.approve", transfer.from_branch_id):
        raise PermissionDenied("Only the sender or the OM can cancel a transfer.")
    if transfer.status != Transfer.Status.SENT:
        raise ValidationError("Only a transfer still on its way can be cancelled.")
    for ln in transfer.lines.select_related("variant").order_by("variant_id"):
        release(ln.variant, transfer.from_branch, ln.quantity)
    transfer.status, transfer.updated_by = Transfer.Status.CANCELLED, user
    transfer.save()
    return transfer


# ---------------------------------------------------------------------------
# Monthly count (FRM-08, rule 10)
# ---------------------------------------------------------------------------
@transaction.atomic
def create_count(branch, month=None, user=None) -> StockCount:
    today = timezone.localdate()
    month = (month or today).replace(day=1)
    existing = StockCount.objects.filter(branch=branch, month=month).first()
    if existing:
        return existing
    next_month = (month + datetime.timedelta(days=32)).replace(day=1)
    count = StockCount.objects.create(
        reference=next_reference("FRM-08", branch, month.year),
        branch=branch,
        month=month,
        count_date=today,
        due_date=nth_working_day(next_month, 3),
        created_by=user,
        updated_by=user,
    )
    stocks = (
        BranchStock.objects.filter(branch=branch)
        .filter(Q(quantity__gt=0) | Q(quantity__lt=0) | Q(variant__is_active=True, variant__product__is_active=True))
        .select_related("variant")
    )
    StockCountLine.objects.bulk_create(
        [StockCountLine(count=count, variant_id=s.variant_id, system_quantity=s.quantity) for s in stocks]
    )
    return count


def auto_create_counts(today=None) -> int:
    """On the last working day of the month, each branch's count sheet is made (rule 10)."""
    today = today or timezone.localdate()
    if today != last_working_day(today.replace(day=1)):
        return 0
    n = 0
    for branch in Branch.objects.filter(is_active=True):
        if not StockCount.objects.filter(branch=branch, month=today.replace(day=1)).exists():
            count = create_count(branch, today)
            notify_perm(
                "inventory.manage", f"Monthly count {count.reference} is ready. Due {count.due_date:%d/%m}.", branch.pk
            )
            n += 1
    return n


def _editable(count, user):
    _need(user, "inventory.manage", count.branch_id, "You cannot count stock at this branch.")
    if count.status not in (StockCount.Status.COUNTING, StockCount.Status.RETURNED):
        raise ValidationError("This count has been submitted.")


@transaction.atomic
def save_count(count: StockCount, user, entries: dict) -> StockCount:
    """entries = {line_id: {"counted": n, "recount": n, "reason": "US", "note": ""}} (blank = unchanged)."""
    count = StockCount.objects.select_for_update().get(pk=count.pk)
    _editable(count, user)
    for line in count.lines.all():
        e = entries.get(line.pk)
        if not e:
            continue
        for key, field in (("counted", "counted_quantity"), ("recount", "recount_quantity")):
            if key in e:
                value = e[key]
                setattr(line, field, None if value in ("", None) else int(value))
        if "reason" in e:
            line.reason = e["reason"] if e["reason"] in REASON_CODES else ""
        if "note" in e:
            line.note = (e["note"] or "")[:200]
        line.save()
    count.updated_by = user
    count.save(update_fields=["updated_by", "updated_at"])
    return count


@transaction.atomic
def submit_count(count: StockCount, user, counted_by) -> StockCount:
    count = StockCount.objects.select_for_update().get(pk=count.pk)
    _editable(count, user)
    if counted_by is None or counted_by.pk == user.pk:
        raise ValidationError("Two people count: choose who counted — you are recording.")
    problems = []
    previous = (
        StockCount.objects.filter(branch=count.branch, month__lt=count.month, status="approved")
        .order_by("-month")
        .first()
    )
    short_before = set()
    if previous:
        short_before = set(previous.lines.filter(adjusted_by__lt=0).values_list("variant_id", flat=True))
    for line in count.lines.select_related("variant__product"):
        if line.counted_quantity is None:
            problems.append(f"{line.variant}: not counted")
            continue
        if line.counted_quantity != line.system_quantity and line.recount_quantity is None:
            problems.append(f"{line.variant}: recount needed")
        elif line.final_quantity != line.system_quantity and not line.reason:
            problems.append(f"{line.variant}: reason code needed")
        line.short_last_month = line.variant_id in short_before and (line.difference or 0) < 0
        line.save(update_fields=["short_last_month"])
    if problems:
        raise ValidationError("Finish these lines: " + "; ".join(problems[:8]) + (" …" if len(problems) > 8 else ""))
    count.status, count.counted_by, count.recorded_by = StockCount.Status.SUBMITTED, counted_by, user
    count.submitted_at, count.return_note, count.updated_by = timezone.now(), "", user
    count.save()
    text = f"Monthly count {count.reference} ({count.branch.name}) is ready for your approval."
    transaction.on_commit(lambda: notify_perm("inventory.approve", text, count.branch_id, exclude=user))
    return count


@transaction.atomic
def approve_count(count: StockCount, user) -> StockCount:
    count = StockCount.objects.select_for_update().get(pk=count.pk)
    _need(user, "inventory.approve", count.branch_id, "Only the Operations Manager approves stock corrections.")
    if user.pk in (count.counted_by_id, count.recorded_by_id):
        raise PermissionDenied("Someone who didn't count must approve.")
    if count.status != StockCount.Status.SUBMITTED:
        raise ValidationError("Only a submitted count can be approved.")
    for line in count.lines.select_related("variant"):
        # The difference found on the day; sales and transfers since then are already in the ledger.
        change = line.final_quantity - line.system_quantity
        line.adjusted_by = change
        line.save(update_fields=["adjusted_by"])
        if change:
            move(
                line.variant,
                count.branch,
                change,
                StockMovement.Kind.COUNT,
                user,
                reference=count.reference,
                reason=line.reason,
                note=line.note,
                check=False,
            )
    count.status, count.approved_by, count.approved_at, count.updated_by = (
        StockCount.Status.APPROVED,
        user,
        timezone.now(),
        user,
    )
    count.save()
    return count


@transaction.atomic
def return_count(count: StockCount, user, note: str) -> StockCount:
    count = StockCount.objects.select_for_update().get(pk=count.pk)
    _need(user, "inventory.approve", count.branch_id, "Only the Operations Manager returns a count.")
    if count.status != StockCount.Status.SUBMITTED:
        raise ValidationError("Only a submitted count can be returned.")
    if not note.strip():
        raise ValidationError("Say which lines to recount.")
    count.status, count.return_note, count.updated_by = StockCount.Status.RETURNED, note.strip()[:255], user
    count.save()
    return count


# ---------------------------------------------------------------------------
# Reorder suggestions
# ---------------------------------------------------------------------------
def reorder_suggestions(branch, days=30) -> list[dict]:
    since = timezone.now() - datetime.timedelta(days=days)
    sold = dict(
        StockMovement.objects.filter(branch=branch, kind__in=["sale", "online"], created_at__gte=since)
        .values("variant_id")
        .annotate(n=Sum("change"))
        .values_list("variant_id", "n")
    )
    out = []
    for s in BranchStock.objects.filter(
        branch=branch, variant__is_active=True, variant__product__is_active=True
    ).select_related("variant__product"):
        v = s.variant
        per_day = D(-(sold.get(v.pk) or 0)) / D(days)
        cover = (D(s.available) / per_day).quantize(D("1")) if per_day > 0 else None
        low = (v.reorder_level and s.available <= v.reorder_level) or (cover is not None and cover < 14)
        if not low:
            continue
        target = v.max_level or max(v.reorder_level * 2, int((per_day * 30).to_integral_value()) or 1)
        out.append(
            {
                "variant": v,
                "available": s.available,
                "reorder_level": v.reorder_level,
                "sold": -(sold.get(v.pk) or 0),
                "days_cover": cover,
                "suggest": max(target - s.available, 1),
            }
        )
    return sorted(out, key=lambda r: (r["days_cover"] is None, r["days_cover"] or 0, r["available"]))


def daily_jobs(today=None) -> dict:
    return {"counts_created": auto_create_counts(today), "requests_reminded": remind_overdue_requests()}
