"""
Phase 3 test data (fictional): vendor details and quotations, costs and reorder levels on every size,
purchase requests at each stage, a local order received at Promenade with a short delivery, an
international order with landed cost still in draft, a transfer on its way to Bedaya and one accepted,
last month's count approved at Promenade and this month's in progress at Bedaya, online orders
waiting to be handed over, Mindbody pricing-option mapping, one parallel-run week and the cut-over list.

Never loaded in production (seed_kuwait refuses to run there).
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.finance.models import Vendor
from apps.inventory import services as inv
from apps.inventory.models import (
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
    VendorQuote,
)
from apps.mindbody import services as mb
from apps.mindbody.models import CutoverStep, ExternalRef, ImportBatch, OptionMap, ParallelRunCheck
from apps.organization.models import PricingOption
from apps.reports.models import week_start
from apps.shop.models import BranchStock, Order, OrderItem, ProductVariant, place_order

TEST_DOMAIN = "test.elite.local"
D = Decimal


def reset_phase3():
    """Runs before reset_phase2 (vendors) and reset_phase1 (shelf stock)."""
    for model in (
        OrderItem,
        Order,
        StockCountLine,
        StockCount,
        TransferLine,
        Transfer,
        Discrepancy,
        ReceiptLine,
        Receipt,
        PurchaseOrderLine,
        PurchaseOrder,
        PurchaseRequestLine,
        PurchaseRequest,
        VendorQuote,
        StockMovement,
        ParallelRunCheck,
        CutoverStep,
        OptionMap,
        ExternalRef,
        ImportBatch,
    ):
        model.objects.all().delete()
    BranchStock.objects.update(reserved=0)


class Phase3Data:
    def __init__(self, seed):
        self.rng, self.today, self.branches = seed.rng, seed.today, seed.branches
        self.users = {u.email.split("@")[0]: u for u in get_user_model().objects.filter(email__endswith=TEST_DOMAIN)}
        self.prm = self.branches["PRM"]
        self.bed = self.branches["BED"]

    def load(self):
        self._vendors()
        self._catalogue()
        self._costs()
        self._local_order()
        self._international_order()
        self._waiting_request()
        self._transfers()
        self._counts()
        self._online_orders()
        self._mindbody()

    # ------------------------------------------------------------------
    def _variants(self, branch, n, min_qty=1):
        stocks = (
            BranchStock.objects.filter(branch=branch, quantity__gte=min_qty, variant__product__is_active=True)
            .select_related("variant__product")
            .order_by("variant_id")
        )
        return [s.variant for s in stocks[:n]]

    def _vendors(self):
        acct, buyer = self.users.get("accounts"), self.users.get("purchasing")
        self.local = Vendor.objects.get(name="Gulf Sports Supply (test)")
        self.local.name_ar, self.local.contact, self.local.phone = (
            "الخليج للتجهيزات الرياضية (تجريبي)",
            "Test Contact",
            "50000001",
        )
        self.local.email = "sales@gulf-sports.test"
        self.local.save()
        self.overseas = Vendor.objects.get(name="Overseas Gear Co. (test)")
        self.overseas.vendor_type, self.overseas.currency = "international", "USD"
        self.overseas.contact, self.overseas.email = "Test Export Desk", "export@overseas-gear.test"
        self.overseas.save()
        self.printer = Vendor.objects.create(
            name="Kuwait Patch & Print (test)",
            name_ar="الكويت للطباعة والشعارات (تجريبي)",
            contact="Test Contact",
            phone="50000002",
            created_by=acct,
        )
        VendorQuote.objects.create(
            vendor=self.overseas,
            date=self.today - datetime.timedelta(days=20),
            description="Gloves and shin guards, 40 sets — FOB price list (test)",
            amount=D("1180.00"),
            currency="USD",
            valid_until=self.today + datetime.timedelta(days=40),
            created_by=buyer,
        )
        VendorQuote.objects.create(
            vendor=self.printer,
            date=self.today - datetime.timedelta(days=60),
            description="Embroidered academy patches, 200 pcs (test)",
            amount=D("140.000"),
            currency="KWD",
            valid_until=self.today - datetime.timedelta(days=5),
            created_by=buyer,
        )

    def _catalogue(self):
        """The website seed normally brings the catalogue; without it, a few fictional items with stock."""
        from apps.inventory.services import set_opening
        from apps.shop.models import Product

        if ProductVariant.objects.exists():
            return
        items = [
            ("Boxing Gloves (sample)", "قفازات ملاكمة (عينة)", "gloves", "18.000", ["8 oz", "10 oz", "12 oz"]),
            ("Shin Guards (sample)", "واقي الساق (عينة)", "shin_guards", "12.000", ["S", "M", "L"]),
            ("Academy Rash Guard (sample)", "راش جارد الأكاديمية (عينة)", "rash_guards", "15.000", ["140", "150", "M"]),
            ("Belt (sample)", "حزام (عينة)", "belts", "4.000", ["A1", "A2"]),
        ]
        for name, name_ar, category, price, sizes in items:
            product = Product.objects.create(
                name_en=name,
                name_ar=name_ar,
                slug=name.lower().replace(" ", "-").replace("(", "").replace(")", ""),
                category=category,
                price=D(price),
                sell_online=category != "belts",
            )
            for i, size in enumerate(sizes):
                variant = ProductVariant.objects.create(product=product, size=size, sort_order=i)
                for branch in (self.prm, self.bed):
                    set_opening(variant, branch, self.rng.randint(2, 6), note="Opening balance (test data)")

    def _costs(self):
        for variant in ProductVariant.objects.select_related("product"):
            price = variant.price or D("0")
            variant.cost = (price * D("0.42")).quantize(D("0.001"))
            variant.reorder_level, variant.max_level = 2, 8
            variant.save(update_fields=["cost", "reorder_level", "max_level"])
        from apps.shop.models import Product

        Product.objects.filter(supplier__isnull=True).update(supplier=self.local)

    def _local_order(self):
        """Bedaya's local request → approved → ordered → delivered to Promenade one short → sent on to Bedaya."""
        ops, buyer, admin = self.users["ops"], self.users["purchasing"], self.users["admin.bed"]
        variants = self._variants(self.prm, 3, min_qty=0)
        req = inv.submit_request(
            self.bed,
            admin,
            vendor_type="local",
            vendor=self.local,
            lines=[{"variant": v, "quantity": 4, "reason": "Below reorder level (test)"} for v in variants],
            note="Monthly local restock (test)",
        )
        inv.decide_request(req, ops, "approve")
        order = inv.create_order(buyer, self.local, [req], language="ar")
        inv.send_order(order, buyer)
        lines = []
        for i, ol in enumerate(order.lines.select_related("variant")):
            lines.append(
                {
                    "variant": ol.variant,
                    "order_line": ol,
                    "invoiced": ol.quantity,
                    "received": ol.quantity - (1 if i == 0 else 0),
                    "note": "One missing from the box (test)" if i == 0 else "",
                }
            )
        receipt = inv.receive(buyer, vendor=self.local, invoice_number="GSS-1101", lines=lines, order=order)
        disc = Discrepancy.objects.filter(receipt=receipt).first()
        if disc:
            inv.update_discrepancy(
                disc, buyer, vendor_notified_on=self.today, resolution="Vendor to send the missing piece (test)."
            )
        self.receipt = receipt
        # Received at Promenade for Bedaya: sent on, still on its way.
        inv.send_transfer(
            self.prm,
            self.bed,
            buyer,
            [(ln.variant, ln.received_quantity) for ln in receipt.lines.select_related("variant")],
            receipt=receipt,
            note="Bedaya's restock from GSS-1101 (test)",
        )

    def _international_order(self):
        ops, buyer, admin = self.users["ops"], self.users["purchasing"], self.users["admin.prm"]
        variants = self._variants(self.prm, 6, min_qty=0)[3:6]
        req = inv.submit_request(
            self.prm,
            admin,
            vendor_type="international",
            vendor=self.overseas,
            lines=[{"variant": v, "quantity": 12, "reason": "Season restock (test)"} for v in variants],
        )
        inv.decide_request(
            req, ops, "amend", note="Order 10 of each for now (test).", amended={ln.pk: 10 for ln in req.lines.all()}
        )
        order = inv.create_order(
            buyer,
            self.overseas,
            [req],
            currency="USD",
            exchange_rate="0.307",
            freight_kwd="45",
            customs_percent=5,
            target_margin=50,
            language="en",
        )
        prices = {ln.pk: (ln.variant.price / D("0.307") * D("0.3")).quantize(D("0.01")) for ln in order.lines.all()}
        inv.update_order(order, buyer, prices=prices)

    def _waiting_request(self):
        admin = self.users["admin.prm"]
        variants = self._variants(self.prm, 8, min_qty=0)[6:8]
        inv.submit_request(
            self.prm,
            admin,
            vendor_type="local",
            vendor=self.printer,
            lines=[{"variant": v, "quantity": 5, "reason": "Low stock (test)"} for v in variants]
            + [{"item": "Embroidered academy patch", "size": "", "quantity": 50, "reason": "New uniform (test)"}],
        )

    def _transfers(self):
        sender, receiver = self.users["admin.bed"], self.users["admin.prm"]
        variants = self._variants(self.bed, 2, min_qty=2)
        if not variants:
            return
        t = inv.send_transfer(self.bed, self.prm, sender, [(v, 1) for v in variants], note="Sizes Promenade asked for")
        inv.accept_transfer(t, receiver, {})

    def _counts(self):
        ops, admin_prm, coach_prm = self.users["ops"], self.users["admin.prm"], self.users["coach.prm"]
        last_month = (self.today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        count = inv.create_count(self.prm, last_month, ops)
        entries, first = {}, True
        for ln in count.lines.all():
            if first and ln.system_quantity > 0:
                entries[ln.pk] = {
                    "counted": ln.system_quantity - 1,
                    "recount": ln.system_quantity - 1,
                    "reason": "D",
                    "note": "Torn packaging, written off (test)",
                }
                first = False
            else:
                entries[ln.pk] = {"counted": ln.system_quantity}
        inv.save_count(count, admin_prm, entries)
        inv.submit_count(count, admin_prm, coach_prm)
        inv.approve_count(count, ops)
        # This month at Bedaya: counting has started.
        current = inv.create_count(self.bed, self.today, ops)
        started = {ln.pk: {"counted": ln.system_quantity} for ln in list(current.lines.all())[:4]}
        inv.save_count(current, self.users["admin.bed"], started)

    def _online_orders(self):
        buyers = [
            ("Test Customer One", "60000101", "pickup", self.prm),
            ("Test Customer Two", "60000102", "delivery", None),
        ]
        for name, mobile, how, branch in buyers:
            candidates = [
                s.variant
                for s in BranchStock.objects.filter(
                    variant__product__sell_online=True, variant__product__is_active=True
                )
                .select_related("variant__product")
                .order_by("variant_id")
                if s.available >= 1
            ]
            if not candidates:
                return
            variant = candidates[self.rng.randrange(len(candidates))]
            customer = {"customer_name": name, "mobile": "+965" + mobile, "email": "", "pickup_branch": branch}
            if how == "delivery":
                customer.update(delivery_area="Salmiya", delivery_address="Block 1, Street 1 (test)")
            order = place_order(
                cart_lines=[(variant.pk, 1)],
                customer=customer,
                fulfilment=how,
                payment_method="knet",
                delivery_fee=D("2.000"),
                language="en",
            )
            order.mark_paid(f"TEST-KNET-{order.pk:04d}")

    def _mindbody(self):
        ops = self.users["ops"]
        prm_option = PricingOption.objects.filter(branch=self.prm, is_active=True).order_by("pk").first()
        rows = [
            ("12 Classes / Month (Mindbody test)", self.prm, prm_option, False),
            ("Summer Camp 2025 (Mindbody test)", self.prm, None, True),
            ("Kids Unlimited Quarterly (Mindbody test)", self.bed, None, False),
        ]
        for name, branch, option, skip in rows:
            OptionMap.objects.create(
                mindbody_name=name, branch=branch, pricing_option=option, skip=skip, created_by=ops, updated_by=ops
            )
        last_week = week_start(self.today) - datetime.timedelta(days=7)
        system = mb.system_week(self.prm, last_week)
        mb.record_check(
            self.prm,
            last_week,
            ops,
            knet=D(system["knet"]),
            card=D(system["card"]),
            cash=D(system["cash"]) + D("5.000"),
            active=int(system["active"]),
            explanation="Mindbody shows 5 KD more cash: a drop-in entered there only (test).",
        )
        mb.ensure_cutover_steps()
        step = CutoverStep.objects.get(order=4)
        mb.tick_step(step, ops, done=True, note="Walkthroughs held at both branches (test).")
        ref_time = timezone.now()
        CutoverStep.objects.filter(pk=step.pk).update(done_at=ref_time - datetime.timedelta(days=2))
