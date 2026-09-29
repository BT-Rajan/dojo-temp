"""Phase 2 rules: daily operations, finance, weekly reports, active members, exports and payroll."""

import datetime
from decimal import Decimal

import pytest
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.classes.models import ClassSession
from apps.core.messaging import OUTBOX_KEY
from apps.finance import services as fin
from apps.finance.models import Expense
from apps.members.models import Guardian, GuardianLink, Member
from apps.operations import services as ops
from apps.operations.models import SHIFT_CHECK_CODES, Complaint, Incident
from apps.organization.models import PricingOption, Program
from apps.payroll import services as pay
from apps.payroll.models import (
    Advance,
    Leave,
    PayAdjustment,
    PayComponent,
    PayProfile,
    PayrollRun,
    PayrollSettings,
    PublicHoliday,
)
from apps.reports import documents
from apps.reports import services as rep
from apps.reports.export import render
from apps.reports.models import ReportSubscription, WeeklyReport, week_start
from apps.reports.tasks import send_subscriptions
from apps.sales import services as sal
from apps.sales.models import CashUp, Membership, Sale, SaleLine
from apps.staff.models import StaffProfile

D = Decimal
TODAY = timezone.localdate()


@pytest.fixture(autouse=True)
def _run_on_commit(monkeypatch):
    """Messages are sent after the transaction commits; in tests, send them straight away."""
    from django.db import transaction

    monkeypatch.setattr(transaction, "on_commit", lambda fn, *a, **k: fn())


@pytest.fixture
def s(branches, make_user):
    for b in branches.values():
        b.open_days = list(range(7))
        b.save()
    prm, bed = branches["PRM"], branches["BED"]
    program = Program.objects.create(branch=prm, name="Grappling", name_ar="المصارعة")
    monthly = PricingOption.objects.create(
        branch=prm, name="Monthly", kind="membership", price=D("85"), duration_days=30, approval="approved"
    )
    monthly.programs.add(program)
    trial = PricingOption.objects.create(
        branch=prm, name="Trial", kind="trial", price=D("10"), duration_days=1, approval="approved"
    )
    users = {
        "om": make_user("operations_manager"),
        "ceo": make_user("ceo"),
        "acct": make_user("accountant"),
        "desk": make_user("branch_admin", branch=prm),
        "desk2": make_user("branch_admin", branch=prm),
        "bed_desk": make_user("branch_admin", branch=bed),
        "coach": make_user("instructor"),
    }
    for i, u in enumerate(users.values()):
        u.mobile = f"+9655000{i:04d}"
        u.save()
    return {"prm": prm, "bed": bed, "program": program, "monthly": monthly, "trial": trial, **users}


def child(branch, first="Salem"):
    m = Member.objects.create(
        branch=branch, first_name=first, last_name="Phaseii", date_of_birth=datetime.date(2016, 5, 10), gender="male"
    )
    g = Guardian.objects.create(full_name="Parent Phaseii", mobile="+96560001234")
    GuardianLink.objects.create(member=m, guardian=g, relationship="father", is_primary=True)
    return m


def adult(branch, first="Khaled"):
    return Member.objects.create(
        branch=branch,
        first_name=first,
        last_name="Adult",
        date_of_birth=datetime.date(1990, 1, 1),
        gender="male",
        mobile="+96599001122",
    )


def sell(s, member, option, method="cash", user=None, category=None):
    return sal.sell(
        branch=s["prm"],
        user=user or s["desk"],
        cart=sal.Cart(
            items=[sal.Item(pricing_option=option)],
            payments=[sal.Pay(method, option.price, "T1" if method != "cash" else "")],
        ),
        member=member,
    )


def outbox():
    return cache.get(OUTBOX_KEY, [])


# ---------------------------------------------------------------------------
# M9 daily operations
# ---------------------------------------------------------------------------
def test_shift_opening_needs_every_check_or_a_note_and_hazards_reach_the_om(s):
    with pytest.raises(ValidationError):
        ops.complete_shift_opening(s["prm"], TODAY, "evening", s["desk"], done=SHIFT_CHECK_CODES[:8], confirmed=True)
    with pytest.raises(ValidationError):
        ops.complete_shift_opening(s["prm"], TODAY, "evening", s["desk"], done=SHIFT_CHECK_CODES, confirmed=False)
    cache.clear()
    ops.complete_shift_opening(
        s["prm"], TODAY, "evening", s["desk"], done=SHIFT_CHECK_CODES, hazard="Loose mat", confirmed=True
    )
    assert any("HAZARD" in m["text"] and m["to"] == s["om"].mobile for m in outbox())
    with pytest.raises(ValidationError):  # once per shift
        ops.complete_shift_opening(s["prm"], TODAY, "evening", s["desk"], done=SHIFT_CHECK_CODES, confirmed=True)
    with pytest.raises(PermissionDenied):  # other branch
        ops.complete_shift_opening(s["prm"], TODAY, "morning", s["bed_desk"], done=SHIFT_CHECK_CODES, confirmed=True)


def test_child_incident_needs_the_guardian_and_the_ceo_is_told_within_24_hours(s):
    kid = child(s["prm"])
    base = dict(occurred_at=timezone.now(), kind="injury", what_happened="Fell", action_taken="Ice", needs_ceo=True)
    with pytest.raises(ValidationError):
        ops.report_incident(s["prm"], s["coach"], member=kid, **base)
    cache.clear()
    inc = ops.report_incident(
        s["prm"], s["coach"], member=kid, guardian_informed_name="Father", guardian_informed_at=timezone.now(), **base
    )
    assert inc.reference == f"FRM-09-PRM-{TODAY.year}-001"
    assert any(m["to"] == s["om"].mobile for m in outbox())  # OM the same day
    with pytest.raises(ValidationError):  # can't close before the CEO knows
        ops.close_incident(inc, s["om"], "done")
    with pytest.raises(PermissionDenied):
        ops.escalate_to_ceo(inc, s["coach"])
    # Nobody escalates: after 24 hours the system sends it to the CEO.
    assert ops.auto_escalate_overdue(timezone.now() + datetime.timedelta(hours=23)) == 0
    cache.clear()
    assert ops.auto_escalate_overdue(timezone.now() + datetime.timedelta(hours=25)) == 1
    inc.refresh_from_db()
    assert inc.ceo_auto_escalated and inc.ceo_escalated_at
    assert any(m["to"] == s["ceo"].mobile for m in outbox())
    ops.close_incident(inc, s["om"], "Physio visit arranged")
    assert Incident.objects.get(pk=inc.pk).status == "closed"


def test_complaints_escalate_by_topic_and_close_only_when_the_member_is_told(s):
    cache.clear()
    money = ops.log_complaint(
        s["prm"], s["desk"], contact_name="A Parent", channel="whatsapp", category="money", details="x"
    )
    assert money.escalated and any(m["to"] == s["om"].mobile for m in outbox())
    assert money.reply_due_at - money.received_at == datetime.timedelta(hours=24)
    other = ops.log_complaint(s["prm"], s["desk"], contact_name="B", channel="desk", category="classes", details="y")
    assert not other.escalated
    with pytest.raises(ValidationError):
        ops.close_complaint(other, s["desk"], outcome="sorted", member_informed_at=None)
    with pytest.raises(PermissionDenied):  # escalated: only the OM closes
        ops.close_complaint(money, s["desk"], outcome="refunded", member_informed_at=timezone.now())
    ops.close_complaint(other, s["desk"], outcome="sorted", member_informed_at=timezone.now())
    assert Complaint.objects.get(pk=other.pk).status == "closed"
    # The 24-hour reminder goes once.
    later = timezone.now() + datetime.timedelta(hours=25)
    assert ops.remind_overdue_complaints(later) == 1
    assert ops.remind_overdue_complaints(later) == 0


def test_handover_is_accepted_item_by_item_and_a_leaver_loses_access(s):
    StaffProfile.objects.create(user=s["desk"], job_title="Branch Admin", employment_type="full_time")
    last_day = TODAY + datetime.timedelta(days=2)
    h = ops.name_cover(
        s["prm"], s["om"], outgoing=s["desk"], incoming=s["desk2"], cover_from=TODAY, leaving=True, last_day=last_day
    )
    assert len(h.items) == 9 and h.items_left == 9
    with pytest.raises(PermissionDenied):
        ops.accept_handover_item(h, s["om"], "cash")
    for item in h.items:
        h = ops.accept_handover_item(h, s["desk2"], item["code"])
    assert h.status == "accepted"
    assert not s["desk"].role_assignments.filter(ends_on__isnull=True).exists()
    assert ops.close_leaver_accounts(last_day) == 0
    assert ops.close_leaver_accounts(last_day + datetime.timedelta(days=1)) == 1
    s["desk"].refresh_from_db()
    assert not s["desk"].is_active


# ---------------------------------------------------------------------------
# M11 finance
# ---------------------------------------------------------------------------
def receipt():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(buf, "PNG")
    return SimpleUploadedFile("r.png", buf.getvalue(), content_type="image/png")


def test_drawer_expenses_come_off_the_cash_up_and_need_a_receipt_or_reason(s):
    m = adult(s["prm"])
    sell(s, m, s["monthly"], "cash")
    with pytest.raises(ValidationError):
        fin.record_expense(
            s["prm"], s["desk"], date=TODAY, description="Water", paid_to="Shop", category="hospitality", amount=D("3")
        )
    e = fin.record_expense(
        s["prm"],
        s["desk"],
        date=TODAY,
        description="Water",
        paid_to="Shop",
        category="hospitality",
        amount=D("3.500"),
        receipt=receipt(),
    )
    assert e.receipt.name.endswith(".jpg")  # re-encoded
    c = sal.open_cash_up(s["prm"], TODAY, s["desk"])
    assert c.cash_paid_out == D("3.500") and c.expected_cash == D("81.500")
    with pytest.raises(PermissionDenied):
        fin.decide_expense(e, s["desk"], True)  # not the recorder
    with pytest.raises(ValidationError):
        fin.decide_expense(e, s["om"], False)  # a reason is needed to reject
    fin.decide_expense(e, s["acct"], True)
    sal.submit_cash_up(c, s["desk"], counted_cash=D("81.500"), terminal_knet=D("0"), terminal_card=D("0"))
    with pytest.raises(ValidationError):  # the day is closed
        fin.record_expense(
            s["prm"],
            s["desk"],
            date=TODAY,
            description="x",
            paid_to="y",
            category="other",
            amount=D("1"),
            no_receipt_reason="lost",
        )


def test_vendor_invoice_record_approve_pay(s):
    from apps.finance.models import Vendor

    v = Vendor.objects.create(name="Test Vendor")
    inv = fin.record_invoice(
        s["acct"],
        vendor=v,
        number="A1",
        date=TODAY,
        description="Belts",
        amount=D("100"),
        currency="USD",
        exchange_rate=D("0.3"),
    )
    assert inv.amount_kwd == D("30.000")
    with pytest.raises(ValidationError):
        fin.record_invoice(s["acct"], vendor=v, number="A1", date=TODAY, description="dup", amount=D("1"))
    with pytest.raises(ValidationError):
        fin.pay_invoice(inv, s["acct"], paid_on=TODAY, method="bank")
    fin.approve_invoice(inv, s["om"])
    fin.pay_invoice(inv, s["acct"], paid_on=TODAY, method="bank", reference="TRF1")
    assert inv.__class__.objects.get(pk=inv.pk).status == "paid"


# ---------------------------------------------------------------------------
# M10 reports
# ---------------------------------------------------------------------------
def backdate(sale, day):
    when = timezone.make_aware(datetime.datetime.combine(day, datetime.time(18)))
    Sale.objects.filter(pk=sale.pk).update(created_at=when)
    sale.payments.update(received_at=when)


def test_weekly_sales_report_totals_matching_and_frozen_copy(s):
    start = week_start(TODAY) - datetime.timedelta(days=7)
    day = start + datetime.timedelta(days=1)
    m = adult(s["prm"])
    s1 = sell(s, m, s["monthly"], "knet")
    s2 = sal.sell(
        branch=s["prm"],
        user=s["desk"],
        cart=sal.Cart(items=[sal.Item(pricing_option=s["trial"])], payments=[sal.Pay("cash", D("10"))]),
        customer_name="Visitor",
        customer_mobile="+96566001122",
    )
    backdate(s1, day)
    backdate(s2, day)
    Expense.objects.create(
        branch=s["prm"],
        date=day,
        description="Water",
        paid_to="Shop",
        category="hospitality",
        amount=D("2"),
        paid_from="drawer",
        no_receipt_reason="n/a",
        created_by=s["desk"],
    )
    c = CashUp(branch=s["prm"], date=day, created_by=s["desk"])
    sal._apply_expected(c)
    c.counted_cash, c.terminal_knet, c.terminal_card, c.status, c.submitted_by = (
        c.expected_cash,
        D("85"),
        D("0"),
        "submitted",
        s["desk"],
    )
    c.save()
    data = rep.weekly_sales(s["prm"], start)
    assert data["total_sales"] == D("95") and data["total_expenses"] == D("2") and data["net"] == D("93")
    by = {m["code"]: m for m in data["by_method"]}
    assert by["knet"]["total"] == D("85") and by["cash"]["total"] == D("10")
    assert by["knet"]["difference"] == 0 and by["cash"]["difference"] == 0
    assert data["missing_cash_ups"]  # other days have no cash-up
    # Prepare → verify, never by the same person.
    with pytest.raises(PermissionDenied):
        rep.prepare_report("sales", s["prm"], start, s["bed_desk"])
    report = rep.prepare_report("sales", s["prm"], start, s["desk"])
    assert report.reference == f"FRM-06-PRM-{start.year}-001"
    with pytest.raises(PermissionDenied):
        rep.verify_report(report, s["desk"])
    rep.verify_report(report, s["om"])
    assert not rep.changed_since_frozen(report)
    late = sell(s, adult(s["prm"], "Late"), s["monthly"], "cash")
    backdate(late, day)
    assert rep.changed_since_frozen(report)
    assert WeeklyReport.objects.get(pk=report.pk).data["total_sales"] == "95.000"
    with pytest.raises(ValidationError):  # this week hasn't ended
        rep.prepare_report("sales", s["prm"], TODAY, s["desk"])


def test_active_members_rule_and_weekly_branch_measures(s):
    paid, free, trial_only = adult(s["prm"], "Paid"), adult(s["prm"], "Free"), adult(s["prm"], "Trial")
    sell(s, paid, s["monthly"])
    Membership.objects.create(
        member=free, branch=s["prm"], pricing_option=s["monthly"], start_date=TODAY, end_date=TODAY
    )
    line = SaleLine.objects.create(
        sale=Sale.objects.create(branch=s["prm"], number=999, created_by=s["desk"]),
        pricing_option=s["monthly"],
        description="free",
        category="new",
        unit_price=0,
        line_total=0,
    )
    Membership.objects.filter(member=free).update(sale_line=line)
    sell(s, trial_only, s["trial"])
    imported = adult(s["prm"], "Imported")  # no sale behind it (e.g. brought over from Mindbody): counts
    Membership.objects.create(
        member=imported, branch=s["prm"], pricing_option=s["monthly"], start_date=TODAY, end_date=TODAY
    )
    data = rep.active_members(TODAY, s["prm"])
    assert data["total"] == 2  # paid + imported; a 0 KD membership and a trial pass never count
    names = [r["name"] for r in data["roster"]]
    assert not any("Trial" in n for n in names)
    assert data["programs"][0]["label"] == "Grappling"
    assert rep.snapshot_active_members(TODAY) == 2
    # Weekly branch: a member whose membership ended 15+ days ago without renewing is lost.
    lost = adult(s["prm"], "Lost")
    start = week_start(TODAY) - datetime.timedelta(days=7)
    Membership.objects.create(
        member=lost,
        branch=s["prm"],
        pricing_option=s["monthly"],
        start_date=start - datetime.timedelta(days=45),
        end_date=start - datetime.timedelta(days=15),
    )
    measures = rep._week_measures(s["prm"], start)
    assert measures["lost"] == 1


def test_exports_in_both_languages(s):
    sell(s, adult(s["prm"]), s["monthly"])
    data = rep.active_members(TODAY, None)
    for lang in ("en", "ar"):
        doc = documents.active_members_doc(data, "Both", None, lang)
        pdf, ctype, ext = render(doc, "pdf", lang)
        assert pdf[:5] == b"%PDF-" and ext == "pdf"
        xlsx, _, ext = render(doc, "xlsx", lang)
        assert xlsx[:2] == b"PK" and ext == "xlsx"


def test_emailed_reports_stop_when_access_ends(s, mailoutbox):
    sub = ReportSubscription.objects.create(user=s["desk"], report="daily", branch=s["prm"], created_by=s["desk"])
    at = timezone.make_aware(datetime.datetime.combine(TODAY, datetime.time(8)))
    assert send_subscriptions(at) == 1 and len(mailoutbox) == 1
    assert mailoutbox[0].attachments[0][0].endswith(".pdf")
    assert send_subscriptions(at) == 0  # once a day
    s["desk"].role_assignments.update(ends_on=TODAY)
    ReportSubscription.objects.filter(pk=sub.pk).update(last_sent_at=None)
    assert send_subscriptions(at) == 0
    assert not ReportSubscription.objects.get(pk=sub.pk).is_active


# ---------------------------------------------------------------------------
# M20 payroll
# ---------------------------------------------------------------------------
@pytest.fixture
def payroll(s):
    month = (TODAY.replace(day=1) - datetime.timedelta(days=1)).replace(day=1)
    staff = {}
    for key, etype, start in (
        ("desk", "full_time", month - datetime.timedelta(days=4 * 365)),
        ("coach", "freelance", month - datetime.timedelta(days=100)),
        ("om", "full_time", month - datetime.timedelta(days=11 * 365)),
    ):
        sp = StaffProfile.objects.create(
            user=s[key], job_title=key, employment_type=etype, start_date=start, primary_branch=s["prm"]
        )
        staff[key] = sp
    desk = PayProfile.objects.create(staff=staff["desk"], iban="KW00TEST0001", is_kuwaiti=True)
    PayComponent.objects.create(profile=desk, kind="salary", amount=D("520"), valid_from=month)
    PayComponent.objects.create(profile=desk, kind="allowance", name="Transport", amount=D("40"), valid_from=month)
    PayComponent.objects.create(
        profile=desk, kind="commission", percent=D("2"), sale_categories=["new", "renew"], valid_from=month
    )
    coach = PayProfile.objects.create(staff=staff["coach"], iban="KW00TEST0002")
    PayComponent.objects.create(profile=coach, kind="per_class", amount=D("15"), program=s["program"], valid_from=month)
    PayComponent.objects.create(
        profile=coach, kind="hourly", amount=D("10"), session_kinds=["seminar"], valid_from=month
    )
    om = PayProfile.objects.create(staff=staff["om"], iban="KW00TEST0003", is_kuwaiti=True)
    PayComponent.objects.create(profile=om, kind="salary", amount=D("3000"), valid_from=month)
    settings = PayrollSettings.get()
    settings.confirmed_at, settings.confirmed_by = timezone.now(), s["acct"]
    settings.save()
    return {"month": month, "staff": staff}


def lines(slip):
    return {line.code: line for line in slip.lines.all()}


def test_payroll_builds_from_classes_sales_leave_and_adjustments(s, payroll):
    month, staff = payroll["month"], payroll["staff"]
    period_start, period_end = pay.period_for(month)
    day = period_start + datetime.timedelta(days=2)
    # Coach: two grappling classes (per class), one other class (not paid), one 90-minute seminar (hourly).
    for i, (kind, program, minutes) in enumerate(
        [("class", s["program"], 60), ("class", s["program"], 60), ("class", None, 60), ("seminar", None, 90)]
    ):
        sess = ClassSession.objects.create(
            branch=s["prm"],
            kind=kind,
            program=program,
            title_en="X",
            date=day + datetime.timedelta(days=i),
            start=datetime.time(17),
            end=(datetime.datetime.combine(day, datetime.time(17)) + datetime.timedelta(minutes=minutes)).time(),
        )
        sess.instructors.add(s["coach"])
    ClassSession.objects.create(
        branch=s["prm"],
        program=s["program"],
        title_en="Cancelled",
        date=day,
        start=datetime.time(19),
        end=datetime.time(20),
        status="cancelled",
    ).instructors.add(s["coach"])
    # Desk: a sale of 85 (new) and a refund of 20 of it inside the period → commission on 65.
    sale = sell(s, adult(s["prm"]), s["monthly"])
    backdate(sale, day)
    refund = Sale.objects.create(
        branch=s["prm"], number=5000, kind="refund", refund_of=sale, total=D("-20"), created_by=s["om"]
    )
    SaleLine.objects.create(sale=refund, description="Refund", category="new", unit_price=D("-20"), line_total=D("-20"))
    backdate(refund, day + datetime.timedelta(days=1))
    # Inputs
    PayAdjustment.objects.create(staff=staff["desk"], month=month, kind="ot_rest", quantity=D("4"), note="Saturday")
    PayAdjustment.objects.create(staff=staff["desk"], month=month, kind="absence", quantity=D("1"), note="Absent")
    unpaid_start = month + datetime.timedelta(days=13)
    Leave.objects.create(
        staff=staff["desk"], kind="unpaid", start=unpaid_start, end=unpaid_start, days=1, status="approved"
    )
    Advance.objects.create(
        staff=staff["desk"], amount=D("90"), instalments=3, reason="x", first_month=month, status="approved"
    )

    run = pay.build_run(month, s["om"])
    desk_slip = run.payslips.get(staff=staff["desk"])
    L = lines(desk_slip)
    daily = D("560") / 26
    assert L["salary"].amount == D("520.000") and L["allowance"].amount == D("40.000")
    assert L["commission"].amount == D("1.300")  # 2% of (85 − 20)
    assert L["ot_rest"].amount == pay.kd(D(4) * (D("520") / 26 / 8) * D("1.5"))
    assert L["absence"].amount == pay.kd(daily)
    unpaid_days = pay.working_days(unpaid_start, unpaid_start)
    assert L.get("unpaid_leave") is None or L["unpaid_leave"].amount == pay.kd(daily * unpaid_days)
    assert L["advance"].amount == D("30.000")
    assert L["pifss"].amount == pay.kd(D("560") * D("10.5") / 100)
    assert "pifss_employer" in L and "eos_accrual" in L
    coach_slip = run.payslips.get(staff=staff["coach"])
    C = lines(coach_slip)
    assert C["per_class"].quantity == 2 and C["per_class"].amount == D("30.000")
    assert C["hourly"].quantity == D("1.50") and C["hourly"].amount == D("15.000")
    assert "pifss" not in C and "eos_accrual" not in C  # freelance
    # PIFSS is capped.
    om_slip = run.payslips.get(staff=staff["om"])
    assert lines(om_slip)["pifss"].amount == pay.kd(D("2750") * D("10.5") / 100)

    # Segregation of duties: the OM submits; only someone else with approval rights approves.
    pay.submit_run(run, s["om"])
    with pytest.raises(PermissionDenied):
        pay.approve_run(run, s["om"])
    with pytest.raises(PermissionDenied):
        pay.approve_run(run, s["ceo"])  # the CEO sees the summary but does not approve
    with pytest.raises(ValidationError):  # no more adjustments once submitted
        pay.add_adjustment(staff["desk"], s["om"], month=month, kind="bonus", amount=D("5"), note="late")
    run = pay.approve_run(run, s["acct"])
    assert Advance.objects.get(staff=staff["desk"]).repaid == D("30.000")
    rows = pay.bank_rows(run)
    assert {r["iban"] for r in rows} == {"KW00TEST0001", "KW00TEST0002", "KW00TEST0003"}
    with pytest.raises(ValidationError):  # approved runs can't be rebuilt
        pay.build_run(month, s["om"])


def test_payroll_rules_must_be_confirmed_and_nobody_sets_their_own_pay(s, payroll):
    settings = PayrollSettings.get()
    settings.confirmed_at = None
    settings.save()
    run = pay.build_run(payroll["month"], s["om"])
    assert any(w["code"] == "settings" for w in run.warnings)
    pay.submit_run(run, s["om"])
    with pytest.raises(ValidationError):
        pay.approve_run(run, s["acct"])
    with pytest.raises(PermissionDenied):
        pay.confirm_settings(s["om"])
    pay.confirm_settings(s["acct"], note="checked")
    pay.approve_run(run, s["acct"])
    staff = payroll["staff"]
    assert not pay.can_edit_pay(s["om"], staff["om"])
    assert pay.can_edit_pay(s["om"], staff["desk"])
    assert pay.can_edit_pay(s["ceo"], staff["om"])
    assert not pay.can_edit_pay(s["acct"], staff["desk"])
    with pytest.raises(PermissionDenied):
        pay.add_adjustment(staff["om"], s["om"], month=TODAY, kind="bonus", amount=D("100"), note="me")


def test_end_of_service_and_leave(s, payroll):
    staff = payroll["staff"]
    om = staff["om"].pay  # 11 years, 3000 KD
    full = pay.end_of_service(om, TODAY, "termination")
    wage, years = D("3000"), pay.years_of_service(staff["om"].start_date, TODAY)
    expected = min(wage / 26 * (5 * 15 + (years - 5) * 30), wage * 18)
    assert full["amount"] == pay.kd(expected)
    desk = staff["desk"].pay  # 4 years → half on resignation
    t = pay.end_of_service(desk, TODAY, "termination")
    r = pay.end_of_service(desk, TODAY, "resignation")
    assert r["amount"] == pay.kd(t["amount"] * D("0.5"))
    assert pay.end_of_service(staff["coach"].pay, TODAY, "termination")["amount"] == 0  # freelance
    # Sick leave tiers: day 16 onwards is on ¾ pay.
    settings = PayrollSettings.get()
    assert pay.sick_pay_share(15, settings) == 1 and pay.sick_pay_share(16, settings) == D("0.75")
    assert pay.sick_pay_share(45, settings) == D("0.25") and pay.sick_pay_share(46, settings) == 0
    # Leave: Fridays and public holidays are not counted; nobody decides their own.
    friday = TODAY + datetime.timedelta(days=(4 - TODAY.weekday()) % 7 + 7)
    PublicHoliday.objects.create(date=friday + datetime.timedelta(days=1), name="Test holiday")
    leave = pay.request_leave(
        staff["desk"],
        s["desk"],
        kind="annual",
        start=friday - datetime.timedelta(days=1),
        end=friday + datetime.timedelta(days=2),
    )
    assert leave.days == 2
    with pytest.raises(ValidationError):
        pay.request_leave(
            staff["coach"], s["coach"], kind="annual", start=friday, end=friday + datetime.timedelta(days=3)
        )
    with pytest.raises(PermissionDenied):
        pay.decide_leave(leave, s["desk"], True)
    pay.decide_leave(leave, s["om"], True)
    assert Leave.objects.get(pk=leave.pk).status == "approved"


def test_payslips_are_private(s, payroll, client_for):
    run = pay.build_run(payroll["month"], s["om"])
    slip = run.payslips.get(staff=payroll["staff"]["desk"])
    other = run.payslips.get(staff=payroll["staff"]["coach"])
    c = client_for(s["desk"])
    assert c.get(f"/en/desk/payroll/payslips/{slip.pk}/").status_code == 404  # not released yet
    pay.submit_run(run, s["om"])
    pay.approve_run(run, s["acct"])
    assert c.get(f"/en/desk/payroll/payslips/{slip.pk}/").status_code == 200
    assert c.get(f"/en/desk/payroll/payslips/{other.pk}/").status_code == 404
    assert c.get(f"/en/desk/payroll/payslips/{slip.pk}/?format=pdf")["Content-Type"] == "application/pdf"
    assert client_for(s["acct"]).get(f"/en/desk/payroll/payslips/{other.pk}/").status_code == 200
    assert c.get(f"/en/desk/payroll/runs/{run.pk}/").status_code == 403
    bank = client_for(s["acct"]).get(f"/en/desk/payroll/runs/{run.pk}/?format=bank&as=csv")
    assert bank.status_code == 200 and b"KW00TEST0001" in bank.content
    assert PayrollRun.objects.get(pk=run.pk).status == "approved"
