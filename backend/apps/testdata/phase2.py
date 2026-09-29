"""
Phase 2 test data (fictional): five weeks of sales behind the Phase 1 memberships, daily cash-ups,
branch expenses with receipt photos, verified weekly reports, shift openings, incidents and
complaints, a handover, vendors and invoices, pay set-up for every test staff member, leave,
advances, adjustments, an approved payroll for last month and a draft for this month.

Never loaded in production (seed_kuwait refuses to run there).
"""

import datetime
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.finance.models import Expense, IncomeStatement, Vendor, VendorInvoice
from apps.operations.models import SHIFT_CHECK_CODES, Complaint, Handover, Incident, ReferenceCounter, ShiftOpening
from apps.organization.models import PricingOption
from apps.payroll.models import (
    Advance,
    Leave,
    PayAdjustment,
    PayComponent,
    PayProfile,
    PayrollRun,
    PayrollSettings,
    Payslip,
    PayslipLine,
    PublicHoliday,
)
from apps.reports.models import ActiveMembersSnapshot, ReportSubscription, WeeklyReport, week_start
from apps.sales.models import CashUp, Membership, Payment, ReceiptCounter, Sale, SaleLine
from apps.shop.models import BranchStock
from apps.staff.models import StaffDocument, StaffProfile

TEST_DOMAIN = "test.elite.local"
WEEKS = 5
D = Decimal


def reset_phase2():
    for model in (
        PayslipLine,
        Payslip,
        PayrollRun,
        PayAdjustment,
        Advance,
        Leave,
        PayComponent,
        PayProfile,
        PayrollSettings,
        PublicHoliday,
        StaffDocument,
        ReportSubscription,
        ActiveMembersSnapshot,
        WeeklyReport,
        IncomeStatement,
        VendorInvoice,
        Vendor,
        Expense,
        Handover,
        Complaint,
        Incident,
        ShiftOpening,
        ReferenceCounter,
    ):
        model.objects.all().delete()


def _receipt_image(text: str) -> ContentFile:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (360, 480), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((10, 10, 350, 470), outline="black")
    for i, line in enumerate(["TEST RECEIPT", "(fictional)", "", *text.split("\n")]):
        draw.text((24, 30 + i * 22), line, fill="black")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=70)
    return ContentFile(buf.getvalue(), name="receipt.jpg")


class Phase2Data:
    def __init__(self, seed):
        self.rng, self.today, self.branches = seed.rng, seed.today, seed.branches
        self.users = {u.email.split("@")[0]: u for u in get_user_model().objects.filter(email__endswith=TEST_DOMAIN)}
        self.start = week_start(self.today) - datetime.timedelta(days=7 * WEEKS)

    def load(self):
        self._sales_history()
        self._expenses()
        self._cash_ups()
        self._shift_openings()
        self._incidents_and_complaints()
        self._weekly_reports()
        self._snapshots()
        self._vendors()
        self._older_classes()
        self._payroll()
        self._handover_and_subscriptions()

    # ------------------------------------------------------------------
    def _open(self, branch, day):
        from apps.reports.services import _python_open_days

        return day.weekday() in _python_open_days(branch)

    def _moment(self, day, hour_from=16, hour_to=21):
        t = datetime.time(self.rng.randint(hour_from, hour_to - 1), self.rng.choice([0, 10, 20, 30, 40, 50]))
        return timezone.make_aware(datetime.datetime.combine(day, t))

    def _new_sale(self, branch, when, seller, member=None, customer_name=""):
        counter, _ = ReceiptCounter.objects.get_or_create(branch=branch)
        counter.last_number += 1
        counter.save(update_fields=["last_number"])
        sale = Sale.objects.create(
            branch=branch,
            number=counter.last_number,
            member=member,
            customer_name=customer_name,
            created_by=seller,
            updated_by=seller,
            receipt_channels=["whatsapp"],
        )
        Sale.objects.filter(pk=sale.pk).update(created_at=when, updated_at=when)
        return sale

    def _pay(self, sale, total, when, seller):
        method = self.rng.choices(["knet", "card", "cash"], weights=[60, 15, 25])[0]
        Payment.objects.create(
            sale=sale,
            method=method,
            amount=total,
            reference="" if method == "cash" else f"T{self.rng.randint(100000, 999999)}",
            received_by=seller,
            received_at=when,
        )
        Sale.objects.filter(pk=sale.pk).update(subtotal=total, total=total)

    def _sales_history(self):
        """A sale behind every membership that started in the last five weeks, plus passes and equipment."""
        rng = self.rng
        sellers = {code: [self.users.get(f"admin.{code.lower()}"), self.users.get("support")] for code in self.branches}
        for m in Membership.objects.filter(
            start_date__gte=self.start, start_date__lt=self.today, sale_line__isnull=True
        ).select_related("branch", "pricing_option", "member"):
            if not self._open(m.branch, m.start_date):
                continue
            seller = rng.choice([s for s in sellers[m.branch.code] if s])
            when = self._moment(m.start_date)
            sale = self._new_sale(m.branch, when, seller, member=m.member)
            earlier = Membership.objects.filter(member=m.member, end_date__lt=m.start_date).exists()
            price = m.pricing_option.price
            line = SaleLine.objects.create(
                sale=sale,
                pricing_option=m.pricing_option,
                description=m.pricing_option.name,
                description_ar=m.pricing_option.name_ar,
                category="renew" if earlier or rng.random() < 0.55 else "new",
                unit_price=price,
                line_total=price,
            )
            Membership.objects.filter(pk=m.pk).update(sale_line=line)
            self._pay(sale, price, when, seller)
        # Trial and day passes, equipment
        for code, branch in self.branches.items():
            trial = PricingOption.objects.filter(branch=branch, kind="trial").first()
            day_pass = PricingOption.objects.filter(branch=branch, kind="day_pass").first()
            stock = list(BranchStock.objects.filter(branch=branch, quantity__gt=2).select_related("variant__product"))
            day = self.start
            while day < self.today:
                if self._open(branch, day):
                    for _ in range(rng.choice([0, 0, 1, 1, 2])):
                        option = trial if rng.random() < 0.7 else day_pass
                        if option is None:
                            continue
                        seller = rng.choice([s for s in sellers[code] if s])
                        when = self._moment(day)
                        sale = self._new_sale(
                            branch,
                            when,
                            seller,
                            customer_name=rng.choice(["Test Visitor", "Guest Test", "Walk-in Test"]),
                        )
                        SaleLine.objects.create(
                            sale=sale,
                            pricing_option=option,
                            description=option.name,
                            description_ar=option.name_ar,
                            category="trial" if option.kind == "trial" else "day_pass",
                            unit_price=option.price,
                            line_total=option.price,
                        )
                        self._pay(sale, option.price, when, seller)
                    if stock and rng.random() < 0.35:
                        item = rng.choice(stock)
                        member = Membership.objects.filter(branch=branch).order_by("?").first()
                        seller = rng.choice([s for s in sellers[code] if s])
                        when = self._moment(day)
                        sale = self._new_sale(branch, when, seller, member=member.member if member else None)
                        price = item.variant.product.price
                        SaleLine.objects.create(
                            sale=sale,
                            variant=item.variant,
                            description=f"{item.variant.product.name_en} ({item.variant.size})",
                            category="equipment",
                            unit_price=price,
                            line_total=price,
                        )
                        BranchStock.objects.filter(pk=item.pk).update(quantity=item.quantity - 1)
                        item.quantity -= 1
                        self._pay(sale, price, when, seller)
                day += datetime.timedelta(days=1)

    def _expenses(self):
        rng = self.rng
        items = [
            ("Water and cups for the dojo", "Sultan Center (test)", "hospitality", "3.750"),
            ("Mat cleaner", "Cleaning supplies shop (test)", "cleaning", "6.500"),
            ("Printer paper and receipt rolls", "Stationery shop (test)", "supplies", "4.200"),
            ("Light fitting repair", "Handyman (test)", "maintenance", "12.000"),
            ("Delivery of belts from Promenade", "Courier (test)", "transport", "2.500"),
            ("First aid kit refill", "Pharmacy (test)", "supplies", "8.900"),
        ]
        for code, branch in self.branches.items():
            admin = self.users.get(f"admin.{code.lower()}")
            day = self.start
            while day < self.today:
                if self._open(branch, day) and rng.random() < 0.28:
                    desc, to, cat, amount = rng.choice(items)
                    e = Expense(
                        branch=branch,
                        date=day,
                        description=desc,
                        paid_to=to,
                        category=cat,
                        amount=D(amount),
                        paid_from="drawer" if rng.random() < 0.8 else "card",
                        created_by=admin,
                        updated_by=admin,
                    )
                    if rng.random() < 0.9:
                        e.receipt.save(
                            "receipt", _receipt_image(f"{to}\n{desc}\n{amount} KD\n{day:%d/%m/%Y}"), save=False
                        )
                    else:
                        e.no_receipt_reason = "Shop gave no receipt (test)"
                    recent = day >= self.today - datetime.timedelta(days=4)
                    if not recent:
                        e.status = "approved"
                        e.decided_by = self.users.get("ops")
                        e.decided_at = timezone.make_aware(
                            datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(10))
                        )
                    e.save()
                day += datetime.timedelta(days=1)

    def _cash_ups(self):
        from apps.sales.services import _apply_expected

        rng = self.rng
        for code, branch in self.branches.items():
            admin = self.users.get(f"admin.{code.lower()}")
            day = self.start
            while day < self.today - datetime.timedelta(days=1):  # yesterday is left for the demo
                if self._open(branch, day):
                    c = CashUp(branch=branch, date=day, created_by=admin, updated_by=admin)
                    _apply_expected(c)
                    diff = D(rng.choice(["0", "0", "0", "0", "0.500", "-0.250", "-1.500"]))
                    c.counted_cash = c.expected_cash + diff
                    c.terminal_knet, c.terminal_card = c.expected_knet, c.expected_card
                    if abs(diff) > CashUp.REASON_THRESHOLD:
                        c.reason = "Change given twice to a parent; found at closing (test)."
                    c.status = "verified" if day < self.today - datetime.timedelta(days=3) else "submitted"
                    c.submitted_by = admin
                    c.submitted_at = timezone.make_aware(datetime.datetime.combine(day, datetime.time(22)))
                    if c.status == "verified":
                        c.verified_by = self.users.get("accounts")
                        c.verified_at = c.submitted_at + datetime.timedelta(hours=12)
                    c.save()
                day += datetime.timedelta(days=1)

    def _shift_openings(self):
        for code, branch in self.branches.items():
            admin = self.users.get(f"admin.{code.lower()}")
            day = self.today - datetime.timedelta(days=14)
            while day < self.today:
                if self._open(branch, day):
                    missing = [] if self.rng.random() < 0.85 else ["website"]
                    ShiftOpening.objects.create(
                        branch=branch,
                        date=day,
                        shift="evening",
                        done=[c for c in SHIFT_CHECK_CODES if c not in missing],
                        notes={"website": "Website was slow to load; checked again at 17:00 (test)."}
                        if missing
                        else {},
                        hazard="Loose mat edge near the door — taped (test)." if self.rng.random() < 0.08 else "",
                        completed_by=admin,
                        completed_at=timezone.make_aware(datetime.datetime.combine(day, datetime.time(15, 45))),
                        created_by=admin,
                    )
                day += datetime.timedelta(days=1)

    def _incidents_and_complaints(self):
        from apps.members.models import Member
        from apps.operations import services as ops

        bed, prm = self.branches.get("BED"), self.branches.get("PRM")
        child = Member.objects.filter(
            branch=bed, date_of_birth__gt=self.today - datetime.timedelta(days=365 * 12)
        ).first()
        coach = self.users.get("coach.bed1")
        now = timezone.now()
        inc = ops.report_incident(
            bed,
            coach,
            occurred_at=now - datetime.timedelta(hours=5),
            kind="injury",
            member=child,
            people="Sparring partner also shaken (test)",
            what_happened="Twisted ankle landing a jump kick during drills (test).",
            action_taken="Ice pack, rested, class continued for others (test).",
            guardian_informed_name="Mother (test guardian)",
            guardian_informed_at=now - datetime.timedelta(hours=4, minutes=45),
            witnesses="Assistant coach (test)",
            needs_ceo=True,
        )
        old = ops.report_incident(
            prm,
            self.users.get("coach.prm"),
            occurred_at=now - datetime.timedelta(days=9),
            kind="hazard",
            people="",
            what_happened="Water on the floor from the A/C unit (test).",
            action_taken="Area closed off; cleaned; maintenance called (test).",
            needs_ceo=False,
        )
        ops.update_incident_follow_up(
            old, self.users["ops"], owner=self.users.get("admin.prm"), due=self.today - datetime.timedelta(days=5)
        )
        ops.close_incident(old, self.users["ops"], "A/C drain pipe fixed by maintenance (test).")
        c1 = ops.log_complaint(
            bed,
            self.users.get("admin.bed"),
            contact_name="Test Parent",
            contact_mobile="",
            channel="whatsapp",
            category="money",
            details="Charged twice for the renewal on the KNET terminal (test).",
            received_at=now - datetime.timedelta(hours=30),
        )
        c2 = ops.log_complaint(
            prm,
            self.users.get("admin.prm"),
            contact_name="Test Member",
            channel="desk",
            category="classes",
            details="Evening class started 15 minutes late twice this week (test).",
            received_at=now - datetime.timedelta(days=3),
        )
        ops.record_reply(c2, self.users["admin.prm"], "Apologised; coach reminded to start on time (test).")
        ops.close_complaint(
            c2,
            self.users["admin.prm"],
            outcome="Member satisfied; classes on time since (test).",
            member_informed_at=now - datetime.timedelta(days=2),
        )
        self.incident, self.complaint = inc, c1

    def _weekly_reports(self):
        from apps.reports import services as rep

        last = week_start(self.today) - datetime.timedelta(days=7)
        for code, branch in self.branches.items():
            admin = self.users.get(f"admin.{code.lower()}")
            week = self.start
            while week < last:
                for kind in ("sales", "branch"):
                    report = rep.prepare_report(kind, branch, week, admin, facility_issues="", om_decisions="")
                    rep.verify_report(report, self.users["ops"])
                week += datetime.timedelta(days=7)
            # Last week: Bedaya's sales report prepared and waiting for the OM; the rest left to prepare.
            if code == "BED":
                rep.prepare_report("sales", branch, last, admin)

    def _snapshots(self):
        from apps.reports.services import snapshot_active_members

        friday = self.today - datetime.timedelta(days=(self.today.weekday() - 4) % 7 or 7)
        for i in range(4):
            snapshot_active_members(friday - datetime.timedelta(days=7 * i))

    def _vendors(self):
        acct, ops_user = self.users.get("accounts"), self.users.get("ops")
        v1 = Vendor.objects.create(name="Gulf Sports Supply (test)", country="Kuwait", created_by=acct)
        v2 = Vendor.objects.create(name="Overseas Gear Co. (test)", country="Pakistan", created_by=acct)
        rows = [
            (v1, "GSS-1042", 20, "Belts and stripes restock (test)", "185.500", "KWD", "1", "paid"),
            (v2, "OGC-2026-77", 12, "Gloves and shin guards, 40 sets (test)", "1250.00", "USD", "0.307", "approved"),
            (v1, "GSS-1057", 3, "Mat tape and first aid supplies (test)", "42.750", "KWD", "1", "recorded"),
        ]
        for vendor, number, days_ago, desc, amount, cur, rate, status in rows:
            inv = VendorInvoice.objects.create(
                vendor=vendor,
                number=number,
                date=self.today - datetime.timedelta(days=days_ago),
                description=desc,
                amount=D(amount),
                currency=cur,
                exchange_rate=D(rate),
                amount_kwd=(D(amount) * D(rate)).quantize(D("0.001")),
                status=status,
                created_by=acct,
                updated_by=acct,
            )
            if status in ("approved", "paid"):
                inv.approved_by, inv.approved_at = ops_user, timezone.now() - datetime.timedelta(days=days_ago - 1)
            if status == "paid":
                inv.paid_on, inv.paid_method, inv.paid_reference = (
                    self.today - datetime.timedelta(days=days_ago - 3),
                    "bank",
                    "TRF-TEST-01",
                )
            inv.save()

    def _older_classes(self):
        """Ten weeks of timetable history so last month's hourly and per-class pay has classes behind it."""
        from apps.classes.models import ClassSlot
        from apps.classes.services import generate_sessions

        start = self.today - datetime.timedelta(days=70)
        ClassSlot.objects.filter(valid_from__gt=start).update(valid_from=start)
        generate_sessions(start=start, days=42)

    # ------------------------------------------------------------------
    PAY = {
        # prefix: (kuwaiti, [(kind, amount, percent, name, extra)])
        "ceo": (True, [("salary", "2500.000", None, "", {})]),
        "ops": (True, [("salary", "1400.000", None, "", {}), ("allowance", "100.000", None, "Transport", {})]),
        "training": (
            False,
            [
                ("salary", "900.000", None, "", {}),
                ("per_class", "5.000", None, "", {"session_kinds": ["seminar", "camp"]}),
            ],
        ),
        "grappling": (False, [("salary", "750.000", None, "", {}), ("allowance", "50.000", None, "Transport", {})]),
        "striking": (False, [("salary", "750.000", None, "", {}), ("allowance", "50.000", None, "Transport", {})]),
        "coach.prm": (False, [("hourly", "12.000", None, "", {})]),
        "coach.bed1": (False, [("salary", "350.000", None, "", {}), ("per_class", "6.000", None, "", {})]),
        "coach.bed2": (False, [("per_class", "10.000", None, "", {})]),
        "coach.free": (False, [("per_class", "15.000", None, "", {})]),
        "marketing": (True, [("salary", "1100.000", None, "", {})]),
        "content": (False, [("salary", "550.000", None, "", {})]),
        "it": (True, [("salary", "1200.000", None, "", {})]),
        "admin.prm": (
            False,
            [
                ("salary", "450.000", None, "", {}),
                ("allowance", "40.000", None, "Transport", {}),
                ("commission", None, "2.00", "", {"sale_categories": ["new", "renew"]}),
            ],
        ),
        "admin.bed": (
            False,
            [
                ("salary", "450.000", None, "", {}),
                ("allowance", "40.000", None, "Transport", {}),
                ("commission", None, "2.00", "", {"sale_categories": ["new", "renew"]}),
            ],
        ),
        "support": (
            False,
            [
                ("salary", "420.000", None, "", {}),
                ("per_class", "6.000", None, "", {}),
                ("commission", None, "1.50", "", {}),
            ],
        ),
        "purchasing": (False, [("salary", "400.000", None, "", {})]),
        "accounts": (False, [("salary", "800.000", None, "", {})]),
    }

    def _payroll(self):
        from apps.payroll import services as pay

        rng, ops_user, acct = self.rng, self.users["ops"], self.users["accounts"]
        for d, name, name_ar in (
            (datetime.date(self.today.year, 1, 1), "New Year's Day", "رأس السنة الميلادية"),
            (datetime.date(self.today.year, 2, 25), "National Day", "العيد الوطني"),
            (datetime.date(self.today.year, 2, 26), "Liberation Day", "عيد التحرير"),
        ):
            PublicHoliday.objects.get_or_create(date=d, defaults={"name": name, "name_ar": name_ar})
        start_month = (self.today.replace(day=1) - datetime.timedelta(days=62)).replace(day=1)
        for prefix, (kuwaiti, comps) in self.PAY.items():
            user = self.users.get(prefix)
            staff = StaffProfile.objects.filter(user=user).first() if user else None
            if staff is None:
                continue
            if staff.start_date is None or staff.start_date > start_month:
                staff.start_date = start_month - datetime.timedelta(days=rng.randint(200, 2400))
                staff.save(update_fields=["start_date"])
            profile = PayProfile.objects.create(
                staff=staff,
                iban=f"KW{rng.randint(10, 99)}TEST{rng.randint(10**21, 10**22 - 1)}",
                bank_name="Test Bank of Kuwait",
                account_name=staff.user.full_name,
                is_kuwaiti=kuwaiti,
                created_by=ops_user,
                updated_by=ops_user,
            )
            for kind, amount, percent, cname, extra in comps:
                PayComponent.objects.create(
                    profile=profile,
                    kind=kind,
                    amount=D(amount) if amount else None,
                    percent=D(percent) if percent else None,
                    name=cname,
                    name_ar="بدل مواصلات" if cname == "Transport" else "",
                    valid_from=start_month,
                    created_by=ops_user,
                    updated_by=ops_user,
                    **extra,
                )
            for kind, days in (
                ("civil_id", rng.randint(90, 900)),
                ("residency", rng.randint(20, 400) if not kuwaiti else None),
            ):
                if days is None:
                    continue
                StaffDocument.objects.create(
                    staff=staff,
                    kind=kind,
                    number=f"TEST-{rng.randint(100000, 999999)}",
                    expires_on=self.today + datetime.timedelta(days=days),
                    created_by=ops_user,
                )
            if prefix.startswith("coach") or prefix in ("training", "grappling", "striking"):
                StaffDocument.objects.create(
                    staff=staff,
                    kind="first_aid",
                    title="First Aid & CPR (test)",
                    expires_on=self.today + datetime.timedelta(days=rng.choice([12, 45, 300])),
                    created_by=ops_user,
                )
        settings = PayrollSettings.get()
        settings.confirmed_by, settings.confirmed_at = acct, timezone.now()
        settings.confirmation_note = "Test environment only — values to be checked before the first real run."
        settings.save()

        last_month = (self.today.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
        this_month = self.today.replace(day=1)
        staff = {p: StaffProfile.objects.get(user=self.users[p]) for p in self.PAY if p in self.users}
        # Last month: an approved annual leave, overtime, a bonus, an advance being repaid.
        Leave.objects.create(
            staff=staff["coach.bed1"],
            kind="annual",
            start=last_month + datetime.timedelta(days=9),
            end=last_month + datetime.timedelta(days=12),
            days=pay.working_days(last_month + datetime.timedelta(days=9), last_month + datetime.timedelta(days=12)),
            status="approved",
            decided_by=ops_user,
            decided_at=timezone.now() - datetime.timedelta(days=40),
            created_by=staff["coach.bed1"].user,
        )
        PayAdjustment.objects.create(
            staff=staff["admin.bed"],
            month=last_month,
            kind="ot_normal",
            quantity=D("6"),
            note="Covered the Saturday morning desk (test).",
            created_by=ops_user,
        )
        PayAdjustment.objects.create(
            staff=staff["grappling"],
            month=last_month,
            kind="bonus",
            amount=D("50.000"),
            note="Instructor of the Month (test).",
            created_by=ops_user,
        )
        Advance.objects.create(
            staff=staff["support"],
            amount=D("300.000"),
            instalments=3,
            reason="Family expense (test)",
            first_month=last_month,
            status="approved",
            decided_by=ops_user,
            decided_at=timezone.now() - datetime.timedelta(days=45),
            created_by=staff["support"].user,
        )
        run = pay.build_run(last_month, ops_user)
        pay.submit_run(run, ops_user)
        pay.approve_run(run, acct)
        pay.mark_paid(run, acct)
        # This month: inputs waiting and a draft run.
        PayAdjustment.objects.create(
            staff=staff["admin.prm"],
            month=this_month,
            kind="absence",
            quantity=D("1"),
            note="Unauthorised absence (test).",
            created_by=ops_user,
        )
        PayAdjustment.objects.create(
            staff=staff["coach.bed2"],
            month=this_month,
            kind="extra",
            amount=D("30.000"),
            note="Ladies' self-defence workshop (test).",
            created_by=ops_user,
        )
        Leave.objects.create(
            staff=staff["coach.prm"],
            kind="unpaid",
            start=self.today + datetime.timedelta(days=5),
            end=self.today + datetime.timedelta(days=7),
            days=pay.working_days(self.today + datetime.timedelta(days=5), self.today + datetime.timedelta(days=7)),
            reason="Travel (test)",
            created_by=staff["coach.prm"].user,
        )
        Advance.objects.create(
            staff=staff["coach.bed1"],
            amount=D("150.000"),
            instalments=2,
            reason="Car repair (test)",
            first_month=(this_month + datetime.timedelta(days=32)).replace(day=1),
            created_by=staff["coach.bed1"].user,
        )
        pay.build_run(this_month, ops_user)

    def _handover_and_subscriptions(self):
        from apps.operations import services as ops

        bed = self.branches.get("BED")
        ops.name_cover(
            bed,
            self.users["ops"],
            outgoing=self.users["admin.bed"],
            incoming=self.users["support"],
            cover_from=self.today + datetime.timedelta(days=3),
            cover_to=self.today + datetime.timedelta(days=10),
            note="Annual leave cover (test).",
        )
        ReportSubscription.objects.create(
            user=self.users["ceo"], report="daily", format="pdf", created_by=self.users["ceo"]
        )
        ReportSubscription.objects.create(
            user=self.users["ops"], report="weekly_sales", branch=bed, format="xlsx", created_by=self.users["ops"]
        )
