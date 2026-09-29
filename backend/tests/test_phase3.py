"""Phase 3 rules: stock ledger, purchasing, receiving, transfers, monthly counts, online stock, Mindbody import."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.finance.models import Vendor
from apps.inventory import services as inv
from apps.inventory.models import Discrepancy, PurchaseOrder, PurchaseRequest, StockMovement
from apps.members.models import Member
from apps.mindbody import readers
from apps.mindbody import services as mb
from apps.mindbody.models import ImportBatch, OptionMap
from apps.organization.models import PricingOption
from apps.payroll.models import PublicHoliday
from apps.sales.models import Membership
from apps.shop.models import BranchStock, Order, Product, ProductVariant, fulfil_order, place_order

D = Decimal
TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


@pytest.fixture
def s(branches, make_user):
    prm, bed = branches["PRM"], branches["BED"]
    gloves = Product.objects.create(name_en="Pro Gloves", slug="pro-gloves", category="gloves", price=D("20"))
    belt = Product.objects.create(
        name_en="Pro Belt", slug="pro-belt", category="belts", price=D("5"), sell_online=False
    )
    v10 = ProductVariant.objects.create(product=gloves, size="10 oz", cost=D("8"), sort_order=1)
    v12 = ProductVariant.objects.create(product=gloves, size="12 oz", cost=D("8"), sort_order=2)
    vb = ProductVariant.objects.create(product=belt, size="A2", cost=D("1.5"))
    users = {
        "om": make_user("operations_manager"),
        "buyer": make_user("purchasing_coordinator", branch=prm),
        "desk": make_user("branch_admin", branch=prm),
        "desk2": make_user("branch_admin", branch=prm),
        "bed_desk": make_user("branch_admin", branch=bed),
        "bed_desk2": make_user("branch_admin", branch=bed),
        "coach": make_user("instructor", branch=prm),
        "it": make_user("it_admin"),
    }
    local = Vendor.objects.create(name="Local Test Vendor", currency="KWD")
    overseas = Vendor.objects.create(name="Overseas Test Vendor", vendor_type="international", currency="USD")
    return {"prm": prm, "bed": bed, "v10": v10, "v12": v12, "belt": vb, "local": local, "overseas": overseas, **users}


def qty(variant, branch):
    return BranchStock.objects.get(variant=variant, branch=branch).quantity


# ---------------------------------------------------------------------------
# Ledger and online stock
# ---------------------------------------------------------------------------
def test_ledger_is_the_only_writer_and_online_stock_follows_it(s):
    inv.set_opening(s["v10"], s["prm"], 5)
    inv.set_opening(s["v10"], s["bed"], 2)
    s["v10"].refresh_from_db()
    assert s["v10"].stock == 7
    inv.move(s["v10"], s["prm"], -2, "sale", s["desk"], reference="R1")
    last = StockMovement.objects.filter(variant=s["v10"], branch=s["prm"]).order_by("pk").last()
    assert (last.change, last.balance, last.kind) == (-2, 3, "sale")
    inv.reserve(s["v10"], s["prm"], 3)
    with pytest.raises(ValidationError):
        inv.move(s["v10"], s["prm"], -1, "sale", s["desk"])  # everything left is reserved
    s["v10"].refresh_from_db()
    assert s["v10"].stock == 2
    # Belts are never sold online.
    inv.set_opening(s["belt"], s["prm"], 9)
    s["belt"].refresh_from_db()
    assert s["belt"].stock == 0
    # Corrections outside the count: the OM only, with a reason.
    with pytest.raises(PermissionDenied):
        inv.adjust(s["v12"], s["prm"], 4, s["desk"], "D", "x")
    with pytest.raises(ValidationError):
        inv.adjust(s["v12"], s["prm"], 4, s["om"], "D", " ")
    inv.adjust(s["v12"], s["prm"], 4, s["om"], "EE", "Opening typed wrong")
    assert qty(s["v12"], s["prm"]) == 4


def test_business_days_skip_friday_saturday_and_holidays():
    thursday = timezone.make_aware(datetime.datetime(2026, 10, 1, 17, 0))
    due = timezone.localtime(inv.add_business_days(thursday, 2))
    assert due.date() == datetime.date(2026, 10, 5) and due.hour == 17  # Sun, Mon
    assert inv.nth_working_day(datetime.date(2026, 11, 1), 3) == datetime.date(2026, 11, 3)
    assert inv.last_working_day(datetime.date(2026, 10, 1)) == datetime.date(2026, 10, 29)


def test_business_days_respect_public_holidays(db):
    PublicHoliday.objects.create(date=datetime.date(2026, 10, 4), name="Test holiday")
    thursday = timezone.make_aware(datetime.datetime(2026, 10, 1, 9, 0))
    assert timezone.localtime(inv.add_business_days(thursday, 1)).date() == datetime.date(2026, 10, 5)


# ---------------------------------------------------------------------------
# Purchase requests and orders
# ---------------------------------------------------------------------------
def _request(s, branch=None, user=None, vendor_type="local", n=4):
    return inv.submit_request(
        branch or s["prm"],
        user or s["desk"],
        vendor_type=vendor_type,
        lines=[{"variant": s["v10"], "quantity": n}, {"variant": s["v12"], "quantity": n}],
    )


def test_purchase_requests_limit_due_and_segregation(s):
    with pytest.raises(PermissionDenied):
        _request(s, branch=s["bed"], user=s["desk"])  # not their branch
    with pytest.raises(ValidationError):
        inv.submit_request(s["prm"], s["desk"], vendor_type="local", lines=[{"variant": s["v10"], "quantity": 0}])
    req = _request(s)
    assert req.reference.startswith("PRF-") and req.due_at > timezone.now()
    with pytest.raises(ValidationError):
        _request(s, user=s["desk2"])  # one local request per branch per month
    _request(s, user=s["desk2"], vendor_type="international")  # international has no monthly limit
    # The OM decides; never their own; reasons required for reject/amend.
    own = _request(s, branch=s["bed"], user=s["bed_desk"])
    with pytest.raises(PermissionDenied):
        inv.decide_request(req, s["desk2"], "approve")
    with pytest.raises(ValidationError):
        inv.decide_request(req, s["om"], "reject")
    line = req.lines.get(variant=s["v10"])
    req = inv.decide_request(req, s["om"], "amend", note="Only 2 of the 10 oz", amended={line.pk: 2})
    assert req.status == "amended" and req.lines.get(pk=line.pk).final_quantity == 2
    with pytest.raises(ValidationError):
        inv.decide_request(req, s["om"], "approve")  # already decided
    assert own.status == "submitted"
    # Overdue reminders go once.
    PurchaseRequest.objects.filter(pk=own.pk).update(due_at=timezone.now() - datetime.timedelta(hours=1))
    assert inv.remind_overdue_requests() == 1
    assert inv.remind_overdue_requests() == 0


def test_orders_need_approved_requests_and_landed_cost_maths(s):
    req = _request(s, vendor_type="international", n=10)
    with pytest.raises(ValidationError):
        inv.create_order(s["buyer"], s["overseas"], [req])  # not approved
    inv.decide_request(req, s["om"], "approve")
    with pytest.raises(PermissionDenied):
        inv.create_order(s["desk"], s["overseas"], [req])
    order = inv.create_order(
        s["buyer"],
        s["overseas"],
        [req],
        exchange_rate="0.3",
        freight_kwd="12",
        customs_percent=20,
        target_margin=50,
    )
    assert order.reference == f"EA-PO-{TODAY.year}-001" and order.currency == "USD"
    assert PurchaseRequest.objects.get(pk=req.pk).status == "ordered"
    with pytest.raises(ValidationError):
        inv.send_order(order, s["buyer"])  # no prices yet
    prices = {ln.pk: (D("10") if ln.variant_id == s["v10"].pk else D("30")) for ln in order.lines.all()}
    inv.update_order(order, s["buyer"], prices=prices)
    rows = {r["line"].variant_id: r for r in inv.landed_costs(order)}
    # Values in KD: 10×10×0.3 = 30 and 10×30×0.3 = 90 → freight 12 split 3 / 9 → 0.3 and 0.9 a unit.
    assert rows[s["v10"].pk]["landed"] == D("3.900")  # 10×0.3×1.2 + 0.3
    assert rows[s["v12"].pk]["landed"] == D("11.700")  # 30×0.3×1.2 + 0.9
    assert rows[s["v10"].pk]["margin"] == D("80.5") and rows[s["v10"].pk]["meets_target"]
    assert rows[s["v12"].pk]["margin"] == D("41.5") and not rows[s["v12"].pk]["meets_target"]
    # Counter-price that gives 50% at a 20 KD retail: (10 − 0.9) / (0.3 × 1.2) = 25.28 USD.
    assert rows[s["v12"].pk]["counter_price"] == D("25.28")
    inv.send_order(order, s["buyer"])
    with pytest.raises(ValidationError):
        inv.update_order(order, s["buyer"], note="late change")


def test_receiving_at_promenade_updates_cost_and_opens_a_discrepancy(s):
    req = _request(s, n=3)
    inv.decide_request(req, s["om"], "approve")
    order = inv.create_order(s["buyer"], s["local"], [req])
    inv.send_order(order, s["buyer"])
    lines = [
        {"variant": ol.variant, "order_line": ol, "invoiced": 3, "received": 3 if ol.variant_id == s["v10"].pk else 2}
        for ol in order.lines.all()
    ]
    with pytest.raises(PermissionDenied):
        inv.receive(s["bed_desk"], vendor=s["local"], invoice_number="INV-1", lines=lines, order=order)
    with pytest.raises(ValidationError):
        inv.receive(s["buyer"], vendor=s["local"], invoice_number=" ", lines=lines, order=order)
    receipt = inv.receive(s["buyer"], vendor=s["local"], invoice_number="INV-1", lines=lines, order=order)
    assert receipt.branch == s["prm"] and qty(s["v10"], s["prm"]) == 3 and qty(s["v12"], s["prm"]) == 2
    assert PurchaseOrder.objects.get(pk=order.pk).status == "partial"
    disc = Discrepancy.objects.get(receipt=receipt)
    with pytest.raises(ValidationError):
        inv.update_discrepancy(disc, s["buyer"], resolve=True)  # vendor not told yet
    inv.update_discrepancy(disc, s["buyer"], vendor_notified_on=TODAY, resolution="Credit note", resolve=True)
    assert Discrepancy.objects.get(pk=disc.pk).status == "resolved"
    # The last unit arrives: the order and its request are complete.
    last = order.lines.get(variant=s["v12"])
    inv.receive(
        s["buyer"],
        vendor=s["local"],
        invoice_number="INV-2",
        lines=[{"variant": s["v12"], "order_line": last, "invoiced": 1, "received": 1}],
        order=order,
    )
    assert PurchaseOrder.objects.get(pk=order.pk).status == "received"
    assert PurchaseRequest.objects.get(pk=req.pk).status == "received"


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------
def test_transfers_move_stock_only_when_the_receiver_accepts(s):
    inv.set_opening(s["v10"], s["prm"], 6)
    with pytest.raises(PermissionDenied):
        inv.send_transfer(s["prm"], s["bed"], s["bed_desk"], [(s["v10"], 2)])
    t = inv.send_transfer(s["prm"], s["bed"], s["buyer"], [(s["v10"], 4)])
    stock = BranchStock.objects.get(variant=s["v10"], branch=s["prm"])
    assert (stock.quantity, stock.reserved, stock.available) == (6, 4, 2)  # can't be sold while travelling
    with pytest.raises(PermissionDenied):
        inv.accept_transfer(t, s["desk"], {})  # not the receiving branch
    line = t.lines.get()
    with pytest.raises(ValidationError):
        inv.accept_transfer(t, s["bed_desk"], {line.pk: 3})  # short: call first and explain
    t = inv.accept_transfer(t, s["bed_desk"], {line.pk: 3}, called_sender_and_om=True, note="One missing")
    assert t.mismatch and qty(s["v10"], s["prm"]) == 2 and qty(s["v10"], s["bed"]) == 3
    assert BranchStock.objects.get(variant=s["v10"], branch=s["prm"]).reserved == 0
    # Cancelling returns the hold.
    t2 = inv.send_transfer(s["prm"], s["bed"], s["desk"], [(s["v10"], 1)])
    inv.cancel_transfer(t2, s["desk"])
    assert BranchStock.objects.get(variant=s["v10"], branch=s["prm"]).reserved == 0


def test_the_sender_cannot_accept_their_own_transfer(s):
    from apps.rbac.models import Role, RoleAssignment

    inv.set_opening(s["v10"], s["prm"], 2)
    RoleAssignment.objects.create(user=s["buyer"], role=Role.objects.get(code="branch_admin"), branch=s["bed"])
    t = inv.send_transfer(s["prm"], s["bed"], s["buyer"], [(s["v10"], 1)])
    with pytest.raises(PermissionDenied):
        inv.accept_transfer(t, s["buyer"], {})


# ---------------------------------------------------------------------------
# Monthly count
# ---------------------------------------------------------------------------
def test_monthly_count_two_people_recount_reason_and_om_correction(s):
    inv.set_opening(s["v10"], s["prm"], 5)
    inv.set_opening(s["v12"], s["prm"], 3)
    count = inv.create_count(s["prm"], TODAY, s["om"])
    assert inv.create_count(s["prm"], TODAY) == count  # one per branch per month
    assert count.reference.startswith("FRM-08-PRM-") and count.due_date.weekday() in inv.BUSINESS_DAYS
    lines = {ln.variant_id: ln for ln in count.lines.all()}
    a, b = lines[s["v10"].pk], lines[s["v12"].pk]
    inv.save_count(count, s["desk"], {a.pk: {"counted": 5}, b.pk: {"counted": 1}})
    with pytest.raises(ValidationError):
        inv.submit_count(count, s["desk"], s["desk"])  # two people
    with pytest.raises(ValidationError):
        inv.submit_count(count, s["desk"], s["coach"])  # recount needed
    inv.save_count(count, s["desk"], {b.pk: {"recount": 2}})
    with pytest.raises(ValidationError):
        inv.submit_count(count, s["desk"], s["coach"])  # reason needed
    inv.save_count(count, s["desk"], {b.pk: {"reason": "D", "note": "Torn"}})
    inv.submit_count(count, s["desk"], s["coach"])
    with pytest.raises(ValidationError):
        inv.save_count(count, s["desk"], {a.pk: {"counted": 4}})  # locked once submitted
    # A sale after the count day stays in the ledger; approval applies only the difference found.
    inv.move(s["v12"], s["prm"], -1, "sale", s["desk"])
    count = inv.return_count(count, s["om"], "Recount the 12 oz")
    assert count.status == "returned"
    inv.submit_count(count, s["desk"], s["coach"])
    count = inv.approve_count(count, s["om"])
    assert count.status == "approved" and qty(s["v12"], s["prm"]) == 1  # 3 − 1 sold − 1 damaged
    assert StockMovement.objects.filter(kind="count", variant=s["v12"], change=-1, reason="D").exists()


def test_a_counter_cannot_approve_their_own_count(s):
    inv.set_opening(s["v10"], s["prm"], 1)
    count = inv.create_count(s["prm"], TODAY)
    inv.save_count(count, s["desk"], {ln.pk: {"counted": ln.system_quantity} for ln in count.lines.all()})
    inv.submit_count(count, s["desk"], s["om"])
    with pytest.raises(PermissionDenied):
        inv.approve_count(count, s["om"])


def test_counts_are_created_on_the_last_working_day(s):
    month = TODAY.replace(day=1)
    assert inv.auto_create_counts(inv.last_working_day(month)) == 2
    assert inv.auto_create_counts(inv.last_working_day(month)) == 0


# ---------------------------------------------------------------------------
# Online orders share branch stock (M19)
# ---------------------------------------------------------------------------
def _checkout(s, variant, n=1, pickup=None):
    customer = {"customer_name": "Test Buyer", "mobile": "+96560000001", "email": "", "pickup_branch": pickup}
    how = "pickup" if pickup else "delivery"
    return place_order(
        cart_lines=[(variant.pk, n)],
        customer=customer,
        fulfilment=how,
        payment_method="knet",
        delivery_fee=D("2"),
        language="en",
    )


def test_online_orders_reserve_then_take_stock_on_hand_over(s):
    from apps.shop.models import OutOfStock

    inv.set_opening(s["v10"], s["bed"], 2)
    order = _checkout(s, s["v10"], 2, pickup=s["prm"])  # Promenade has none: Bedaya's stock is used
    item = order.items.get()
    assert item.branch == s["bed"] and BranchStock.objects.get(variant=s["v10"], branch=s["bed"]).reserved == 2
    with pytest.raises(OutOfStock):
        _checkout(s, s["v10"])
    with pytest.raises(OutOfStock):
        _checkout(s, s["belt"])
    with pytest.raises(ValueError):
        fulfil_order(order, s["bed_desk"])  # not paid yet
    order.mark_paid("TEST-1")
    fulfil_order(Order.objects.get(pk=order.pk), s["bed_desk"])
    stock = BranchStock.objects.get(variant=s["v10"], branch=s["bed"])
    assert (stock.quantity, stock.reserved) == (0, 0)
    assert StockMovement.objects.filter(kind="online", reference=order.reference).exists()
    # A failed payment gives the stock back.
    inv.set_opening(s["v12"], s["prm"], 1)
    failed = _checkout(s, s["v12"])
    failed.mark_failed()
    assert BranchStock.objects.get(variant=s["v12"], branch=s["prm"]).reserved == 0


# ---------------------------------------------------------------------------
# Mindbody readers and import
# ---------------------------------------------------------------------------
CLIENTS_CSV = (
    b"Client List report (test)\n"
    b"\n"
    b"Client ID,Last Name,First Name,Birth Date,Gender,Mobile Phone,Email,Home Location,Shoe size\n"
    b"1001,Al-Test,Salem,15/05/2016,Male,50001234,,Elite Promenade,\n"
    b"1002,Al-Test,Huda,03/02/1985,Female,50005678,huda@example.test,Elite Promenade,\n"
    b"1003,Nobirth,Test,,Male,50001111,,Elite Promenade,\n"
    b"1004,Otherbranch,Test,20/10/2012,F,5000 2222,,Bedaya,\n"
)

HTML_MEMBERSHIPS = b"""<html><body><table><tr><td>Pricing Option Expirations</td></tr>
<tr><th>Client ID</th><th>Client</th><th>Pricing Option</th><th>Location</th><th>Activation Date</th>
<th>Expiration Date</th><th>Remaining</th></tr>
<tr><td>1001</td><td>Al-Test, Salem</td><td>Kids Monthly MB</td><td>Elite Promenade</td><td>01/09/2026</td>
<td>30/09/2026</td><td></td></tr>
</table></body></html>"""


def test_readers_find_the_header_and_read_dates_and_numbers():
    rows, mapping, unknown = readers.table(CLIENTS_CSV, "clients")
    assert len(rows) == 4 and rows[0]["_row"] == 4 and "Shoe size" in unknown
    assert rows[0]["first_name"] == "Salem" and rows[0]["id"] == "1001"
    rows, _, _ = readers.table(HTML_MEMBERSHIPS, "memberships")
    assert rows[0]["option"] == "Kids Monthly MB" and rows[0]["end"] == "30/09/2026"
    assert readers.date_order(["09/25/2026"]) == "mdy" and readers.date_order(["25/09/2026"]) == "dmy"
    assert readers.date("03/02/1985") == datetime.date(1985, 2, 3)
    assert readers.number("(12.500)") == D("-12.500") and readers.number("١٥") == D("15")
    assert readers.time("6:30 PM") == datetime.time(18, 30)
    assert readers.split_name("Al-Test, Salem") == ("Salem", "Al-Test")
    with pytest.raises(ValueError):
        readers.table(b"a,b\n1,2\n", "clients")


def _upload(s, kind, content, name="export.csv"):
    return mb.create_batch(s["it"], kind, SimpleUploadedFile(name, content), None)


def test_mindbody_dry_run_changes_nothing_and_apply_is_safe_to_repeat(s):
    with pytest.raises(PermissionDenied):
        mb.create_batch(s["desk"], "clients", SimpleUploadedFile("x.csv", CLIENTS_CSV))
    batch = _upload(s, "clients", CLIENTS_CSV)
    assert batch.status == "checked" and batch.summary["counts"]["created"] == 3
    assert Member.objects.count() == 0  # dry run
    assert any("no birth date" in i["message"] for i in batch.issues)
    batch = mb.run(batch, s["it"], apply=True)
    assert batch.status == "applied" and Member.objects.filter(source="mindbody").count() == 3
    assert Member.objects.get(first_name="Test", last_name="Otherbranch").branch == s["bed"]
    assert Member.objects.get(first_name="Salem").mobile == "+96550001234"
    with pytest.raises(ValidationError):
        mb.run(batch, s["it"], apply=True)  # the same batch twice
    again = mb.run(_upload(s, "clients", CLIENTS_CSV), s["it"], apply=True)
    assert again.summary["counts"].get("unchanged") == 3 and Member.objects.count() == 3


def test_mindbody_memberships_wait_for_pricing_option_mapping(s):
    mb.run(_upload(s, "clients", CLIENTS_CSV), s["it"], apply=True)
    option = PricingOption.objects.create(
        branch=s["prm"], name="Kids Monthly", kind="membership", price=D("85"), duration_days=30, approval="approved"
    )
    batch = _upload(s, "memberships", HTML_MEMBERSHIPS, "exp.xls")
    assert batch.summary["counts"]["waiting_for_mapping"] == 1
    mapping = OptionMap.objects.get(mindbody_name="Kids Monthly MB")  # kept even though it was a dry run
    assert [i for i in batch.issues if i["level"] == "map"]
    other = PricingOption.objects.create(
        branch=s["bed"], name="Other", kind="membership", price=D("1"), duration_days=30, approval="approved"
    )
    with pytest.raises(ValidationError):
        mb.map_option(mapping, s["it"], other)  # another branch's option
    mb.map_option(mapping, s["it"], option)
    batch = mb.run(ImportBatch.objects.get(pk=batch.pk), s["it"], apply=True)
    m = Membership.objects.get(member__first_name="Salem")
    assert (m.pricing_option, m.start_date, m.end_date) == (
        option,
        datetime.date(2026, 9, 1),
        datetime.date(2026, 9, 30),
    )
    mb.run(_upload(s, "memberships", HTML_MEMBERSHIPS, "exp.xls"), s["it"], apply=True)
    assert Membership.objects.count() == 1


def test_mindbody_inventory_sets_branch_stock(s):
    csv = (
        b"Product Name,Size,Color,Barcode,Location,In Stock,Our Cost,Retail Price\n"
        b"Pro Gloves,10 oz,,111,Elite Promenade,4,7.5,20\n"
        b"Pro Gloves,14 oz,,112,Elite Bedaya,2,7.5,20\n"
    )
    batch = mb.run(_upload(s, "inventory", csv), s["it"], apply=True)
    assert batch.status == "applied"
    assert qty(s["v10"], s["prm"]) == 4
    assert ProductVariant.objects.filter(product__name_en="Pro Gloves", size="14 oz").exists()
    assert StockMovement.objects.filter(kind="import", variant=s["v10"]).exists()


def test_a_file_that_cannot_be_read_is_reported(s):
    batch = _upload(s, "sales", b"nothing,useful\n1,2\n")
    assert batch.status == "failed" and "column headings" in batch.issues[0]["message"]


def test_parallel_run_differences_need_an_explanation(s):
    start = datetime.date(2026, 9, 19)
    check = mb.record_check(s["prm"], start, s["om"], knet=D("0"), card=D("0"), cash=D("5"), active=0)
    assert not check.agreed and mb.differences(check)["cash"] == D("-5")
    check = mb.record_check(
        s["prm"], start, s["om"], knet=D("0"), card=D("0"), cash=D("5"), active=0, explanation="Drop-in only in MB"
    )
    assert check.agreed
    mb.ensure_cutover_steps()
    mb.ensure_cutover_steps()
    from apps.mindbody.models import CutoverStep

    assert CutoverStep.objects.count() == len(mb.CUTOVER)
    with pytest.raises(PermissionDenied):
        mb.tick_step(CutoverStep.objects.first(), s["desk"])
