"""Phase 3 desk screens, driven as each role would use them (fictional seed data)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client

from apps.finance.models import Vendor
from apps.inventory.models import PurchaseOrder, PurchaseRequest, Receipt, StockCount, Transfer, VendorQuote
from apps.members.models import Member
from apps.mindbody.models import CutoverStep, ImportBatch, OptionMap, ParallelRunCheck
from apps.shop.models import BranchStock, Order, Product


@pytest.fixture
def data(db):
    call_command("seed_kuwait", families=4, adults=3, verbosity=0)


def desk(who):
    from django.contrib.auth import get_user_model

    client = Client()
    client.force_login(get_user_model().objects.get(email=f"{who}@test.elite.local"))
    return client


def url(path, lang="en"):
    return f"/{lang}/desk/{path}"


SCREENS = {
    "admin.bed": [
        "stock/",
        "reorder/",
        "purchase-requests/",
        "purchase-requests/new/",
        "purchase-requests/new/?suggest=1",
        "transfers/",
        "transfers/new/",
        "stock-counts/",
        "online-orders/",
        "receipts/",
    ],
    "purchasing": ["purchase-orders/", "receiving/", "receipts/", "vendors/", "transfers/", "stock/"],
    "ops": [
        "stock/",
        "catalogue/",
        "catalogue/new/",
        "purchase-requests/",
        "purchase-orders/",
        "stock-counts/",
        "vendors/",
        "mindbody/",
        "mindbody/pricing-options/",
        "mindbody/parallel-run/",
        "mindbody/cut-over/",
    ],
    "accounts": ["stock/", "vendors/"],
    "it": ["mindbody/", "mindbody/cut-over/"],
}


def test_every_phase3_screen_renders_in_both_languages(data):
    for who, paths in SCREENS.items():
        client = desk(who)
        for path in paths:
            for lang in ("en", "ar"):
                response = client.get(url(path, lang))
                assert response.status_code == 200, (who, path, lang, response.status_code)
                if lang == "ar":
                    assert 'dir="rtl"' in response.content.decode()[:400]


def test_detail_pages_and_documents(data):
    ops = desk("ops")
    variant = BranchStock.objects.filter(branch__code="PRM").first().variant
    product = Product.objects.first()
    order = PurchaseOrder.objects.filter(status="draft").first()
    paths = [
        f"stock/{variant.pk}/",
        f"catalogue/{product.pk}/",
        f"purchase-requests/{PurchaseRequest.objects.first().pk}/",
        f"purchase-orders/{order.pk}/",
        f"receipts/{Receipt.objects.first().pk}/",
        f"transfers/{Transfer.objects.first().pk}/",
    ]
    paths += [f"stock-counts/{c.pk}/" for c in StockCount.objects.all()]
    for path in paths:
        for lang in ("en", "ar"):
            assert ops.get(url(path, lang)).status_code == 200, path
    for fmt, magic in (("pdf", b"%PDF-"), ("xlsx", b"PK")):
        for lang in ("en", "ar"):
            r = ops.get(url(f"purchase-orders/{order.pk}/?format={fmt}&lang={lang}"))
            assert r.status_code == 200 and r.content[: len(magic)] == magic, (fmt, lang)
        count = StockCount.objects.get(status="approved")
        r = ops.get(url(f"stock-counts/{count.pk}/?format={fmt}", "ar"))
        assert r.status_code == 200 and r.content[: len(magic)] == magic


def test_who_can_see_what(data):
    coach = desk("coach.bed1")
    for path in ["stock/", "purchase-requests/", "purchase-orders/", "vendors/", "mindbody/", "stock-counts/"]:
        assert coach.get(url(path)).status_code == 403, path
    admin = desk("admin.bed")
    for path in ["purchase-orders/", "receiving/", "catalogue/new/", "vendors/", "mindbody/", "mindbody/cut-over/"]:
        assert admin.get(url(path)).status_code == 403, path
    # A branch admin sees only their own branch's requests and counts.
    prm_request = PurchaseRequest.objects.filter(branch__code="PRM").first()
    assert admin.get(url(f"purchase-requests/{prm_request.pk}/")).status_code == 404
    prm_count = StockCount.objects.get(branch__code="PRM")
    assert admin.get(url(f"stock-counts/{prm_count.pk}/")).status_code == 404
    assert desk("accounts").get(url("purchase-requests/new/")).status_code == 403
    assert desk("purchasing").get(url("mindbody/")).status_code == 403


def test_purchasing_from_request_to_delivery(data):
    admin, ops, buyer = desk("admin.prm"), desk("ops"), desk("purchasing")
    stock = BranchStock.objects.filter(branch__code="PRM").select_related("variant").first()
    r = admin.post(
        url("purchase-requests/new/"),
        {"vendor_type": "international", "variant_0": stock.variant_id, "qty_0": "6", "reason_0": "Low"},
    )
    req = PurchaseRequest.objects.order_by("-pk").first()
    assert r.status_code == 302 and req.status == "submitted" and req.vendor_type == "international"
    admin.post(url(f"purchase-requests/{req.pk}/"), {"decision": "approve"})  # can't decide
    assert PurchaseRequest.objects.get(pk=req.pk).status == "submitted"
    ops.post(url(f"purchase-requests/{req.pk}/"), {"decision": "approve"})
    assert PurchaseRequest.objects.get(pk=req.pk).status == "approved"
    vendor = Vendor.objects.get(name="Overseas Gear Co. (test)")
    buyer.post(url("purchase-orders/"), {"vendor": vendor.pk, "requests": [req.pk], "language": "en"})
    order = PurchaseOrder.objects.order_by("-pk").first()
    line = order.lines.get()
    buyer.post(
        url(f"purchase-orders/{order.pk}/"),
        {"action": "save", f"price_{line.pk}": "3.5", "currency": "KWD", "freight_kwd": "2"},
    )
    buyer.post(url(f"purchase-orders/{order.pk}/"), {"action": "send"})
    assert PurchaseOrder.objects.get(pk=order.pk).status == "sent"
    before = BranchStock.objects.get(pk=stock.pk).quantity
    r = buyer.post(
        url("receiving/"),
        {"order": order.pk, "invoice_number": "T-900", f"inv_{line.pk}": "6", f"rec_{line.pk}": "6"},
    )
    assert r.status_code == 302 and BranchStock.objects.get(pk=stock.pk).quantity == before + 6
    assert PurchaseOrder.objects.get(pk=order.pk).status == "received"


def test_transfer_count_and_online_hand_over_at_the_desk(data):
    bed = desk("admin.bed")
    t = Transfer.objects.get(status="sent")
    r = bed.post(url(f"transfers/{t.pk}/"), {f"rec_{ln.pk}": ln.quantity for ln in t.lines.all()})
    assert r.status_code == 302 and Transfer.objects.get(pk=t.pk).status == "accepted"
    # Bedaya finishes this month's count; the OM approves.
    count = StockCount.objects.get(branch__code="BED")
    post = {"action": "submit", "counted_by": ""}
    for ln in count.lines.all():
        post[f"c_{ln.pk}"] = ln.system_quantity
    from django.contrib.auth import get_user_model

    post["counted_by"] = get_user_model().objects.get(email="coach.bed1@test.elite.local").pk
    bed.post(url(f"stock-counts/{count.pk}/"), post)
    assert StockCount.objects.get(pk=count.pk).status == "submitted"
    desk("ops").post(url(f"stock-counts/{count.pk}/"), {"action": "approve"})
    assert StockCount.objects.get(pk=count.pk).status == "approved"
    # Online order handed over at its branch.
    order = (
        Order.objects.filter(status="paid", items__branch__code="BED").first()
        or Order.objects.filter(status="paid").first()
    )
    branch_code = order.items.first().branch.code
    who = desk("admin.bed" if branch_code == "BED" else "admin.prm")
    assert who.post(url(f"online-orders/{order.pk}/fulfil/")).status_code == 302
    assert Order.objects.get(pk=order.pk).status == "completed"


def test_vendors_and_quotes(data):
    buyer = desk("purchasing")
    buyer.post(url("vendors/"), {"name": "New Desk Vendor (test)", "vendor_type": "local", "currency": "kwd"})
    vendor = Vendor.objects.get(name="New Desk Vendor (test)")
    assert vendor.currency == "KWD"
    pdf = SimpleUploadedFile("quote.pdf", b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n", "application/pdf")
    buyer.post(
        url("vendors/"),
        {"action": "quote", "vendor": vendor.pk, "description": "Mats", "amount": "120", "document": pdf},
    )
    quote = VendorQuote.objects.get(vendor=vendor)
    assert buyer.get(url(f"vendors/quotes/{quote.pk}/")).status_code == 200
    assert desk("admin.bed").get(url(f"vendors/quotes/{quote.pk}/")).status_code == 403


def test_mindbody_screens(data):
    it = desk("it")
    csv = (
        b"Client ID,First Name,Last Name,Birth Date,Gender,Mobile Phone,Home Location\n"
        b"MB-1,Desk,Importtest,01/02/2015,M,50009999,Elite Bedaya\n"
    )
    r = it.post(url("mindbody/"), {"kind": "clients", "file": SimpleUploadedFile("clients.csv", csv)})
    batch = ImportBatch.objects.get()
    assert r.status_code == 302 and batch.status == "checked" and not Member.objects.filter(last_name="Importtest")
    for lang in ("en", "ar"):
        assert it.get(url(f"mindbody/{batch.pk}/", lang)).status_code == 200
    it.post(url(f"mindbody/{batch.pk}/"), {"action": "apply"})
    assert Member.objects.filter(last_name="Importtest", source="mindbody").count() == 1
    # Mapping, parallel run and cut-over (the OM).
    ops = desk("ops")
    todo = OptionMap.objects.get(pricing_option__isnull=True, skip=False)
    ops.post(url("mindbody/pricing-options/"), {f"map_{todo.pk}": "skip"})
    assert OptionMap.objects.get(pk=todo.pk).skip
    from apps.organization.models import Branch

    ops.post(
        url("mindbody/parallel-run/"),
        {
            "branch": Branch.objects.get(code="BED").pk,
            "week": "2026-09-20",
            "knet": "0",
            "card": "0",
            "cash": "0",
            "active": "0",
        },
    )
    assert ParallelRunCheck.objects.filter(branch__code="BED").exists()
    step = CutoverStep.objects.get(order=1)
    ops.post(url("mindbody/cut-over/"), {"step": step.pk, "done": "1", "note": "Trial done"})
    assert CutoverStep.objects.get(pk=step.pk).done_at is not None
