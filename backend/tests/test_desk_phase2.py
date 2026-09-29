"""Phase 2 desk screens, driven as each role would use them (fictional seed data)."""

import datetime
import io

import pytest
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from PIL import Image

from apps.finance.models import Expense
from apps.operations.models import Complaint, Handover, Incident, ShiftOpening
from apps.payroll.models import Leave, PayrollRun
from apps.reports.models import WeeklyReport, week_start
from apps.staff.models import StaffProfile

TODAY = timezone.localdate()


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
    "admin.prm": [
        "tasks/",
        "shift/",
        "incidents/",
        "incidents/new/",
        "complaints/",
        "complaints/new/",
        "expenses/",
        "weekly-reports/",
        "active-members/",
        "dashboards/",
        "dashboards/?tab=weekly",
        "report-emails/",
        "my-pay/",
    ],
    "ops": [
        "tasks/",
        "handovers/",
        "handovers/new/",
        "payroll/",
        "payroll/staff/",
        "payroll/leave/",
        "payroll/advances/",
        "payroll/holidays/",
        "payroll/rules/",
        "dashboards/?tab=monthly",
        "dashboards/?tab=training",
        "dashboards/?tab=marketing",
        "finance/income-statement/",
        "finance/revenue/",
        "finance/reconciliation/",
        "finance/invoices/",
        "expenses/?status=pending",
    ],
    "accounts": [
        "payroll/",
        "finance/income-statement/?kind=quarter",
        "finance/reconciliation/",
        "expenses/",
        "active-members/?branch=all",
    ],
    "coach.bed1": ["tasks/", "incidents/", "incidents/new/", "my-pay/"],
    "ceo": ["payroll/", "dashboards/", "active-members/", "finance/income-statement/", "payroll/staff/"],
}


def test_every_phase2_screen_renders_in_both_languages(data):
    for who, paths in SCREENS.items():
        client = desk(who)
        for path in paths:
            for lang in ("en", "ar"):
                response = client.get(url(path, lang))
                assert response.status_code == 200, (who, path, lang, response.status_code)
                if lang == "ar":
                    assert 'dir="rtl"' in response.content.decode()[:400]


def test_detail_pages_render(data):
    ops = desk("ops")
    run = PayrollRun.objects.order_by("month").first()
    slip = run.payslips.first()
    staff = StaffProfile.objects.get(user__email="coach.bed1@test.elite.local")
    for path in [
        f"payroll/runs/{run.pk}/",
        f"payroll/payslips/{slip.pk}/",
        f"payroll/staff/{staff.pk}/",
        f"incidents/{Incident.objects.filter(branch__code='BED').first().pk}/",
        f"handovers/{Handover.objects.first().pk}/",
    ]:
        for lang in ("en", "ar"):
            assert ops.get(url(path, lang)).status_code == 200, path
    bed = desk("admin.bed")
    report = WeeklyReport.objects.filter(branch__code="BED", kind="sales").order_by("week_start").first()
    assert bed.get(url(f"weekly-reports/sales/BED/{report.week_start:%Y-%m-%d}/")).status_code == 200
    assert bed.get(url(f"weekly-reports/branch/BED/{report.week_start:%Y-%m-%d}/", "ar")).status_code == 200
    assert bed.get(url(f"complaints/{Complaint.objects.filter(branch__code='BED').first().pk}/")).status_code == 200


def test_who_can_see_what(data):
    coach = desk("coach.bed1")
    for path in [
        "payroll/",
        "expenses/",
        "finance/income-statement/",
        "weekly-reports/",
        "payroll/staff/",
        "complaints/",
    ]:
        assert coach.get(url(path)).status_code == 403, path
    admin = desk("admin.prm")
    for path in ["payroll/", "finance/income-statement/", "payroll/leave/", "handovers/new/"]:
        assert admin.get(url(path)).status_code == 403, path
    # A branch admin can't open the other branch's weekly report.
    last = week_start(TODAY) - datetime.timedelta(days=7)
    assert admin.get(url(f"weekly-reports/sales/BED/{last:%Y-%m-%d}/")).status_code == 403
    # The coach only sees incidents they reported.
    other = Incident.objects.exclude(created_by__email="coach.bed1@test.elite.local").first()
    assert coach.get(url(f"incidents/{other.pk}/")).status_code == 404
    # Staff documents and receipts are served only to those allowed.
    expense = Expense.objects.exclude(receipt="").filter(branch__code="BED").first()
    assert admin.get(url(f"expenses/{expense.pk}/receipt/")).status_code == 404
    assert desk("admin.bed").get(url(f"expenses/{expense.pk}/receipt/")).status_code == 200


def test_front_desk_day_in_phase2(data):
    admin = desk("admin.prm")
    # Shift opening
    from apps.operations.models import SHIFT_CHECK_CODES

    r = admin.post(url("shift/"), {"shift": "morning", "done": SHIFT_CHECK_CODES, "confirm": "1"})
    assert (
        r.status_code == 302 and ShiftOpening.objects.filter(branch__code="PRM", date=TODAY, shift="morning").exists()
    )
    # Expense with a receipt photo
    buf = io.BytesIO()
    Image.new("RGB", (30, 30), "white").save(buf, "PNG")
    buf.seek(0)
    buf.name = "receipt.png"
    r = admin.post(
        url("expenses/new/"),
        {
            "date": TODAY.isoformat(),
            "amount": "4.250",
            "description": "Water",
            "paid_to": "Shop",
            "category": "hospitality",
            "paid_from": "drawer",
            "receipt": buf,
        },
    )
    assert r.status_code == 302 and Expense.objects.filter(description="Water", amount="4.250").exists()
    # Complaint
    r = admin.post(
        url("complaints/new/"),
        {"contact_name": "A Visitor", "channel": "desk", "category": "refund", "details": "Wants a refund"},
    )
    c = Complaint.objects.get(details="Wants a refund")
    assert r.status_code == 302 and c.escalated
    # Prepare last week's FRM-07; the OM verifies it.
    last = week_start(TODAY) - datetime.timedelta(days=7)
    r = admin.post(
        url(f"weekly-reports/branch/PRM/{last:%Y-%m-%d}/"), {"action": "prepare", "facility_issues": "A/C noisy"}
    )
    report = WeeklyReport.objects.get(kind="branch", branch__code="PRM", week_start=last)
    assert r.status_code == 302 and report.status == "prepared" and report.facility_issues == "A/C noisy"
    desk("ops").post(url(f"weekly-reports/branch/PRM/{last:%Y-%m-%d}/"), {"action": "verify"})
    assert WeeklyReport.objects.get(pk=report.pk).status == "verified"
    # Exports
    for fmt, magic in (("pdf", b"%PDF-"), ("xlsx", b"PK")):
        r = admin.get(url(f"weekly-reports/branch/PRM/{last:%Y-%m-%d}/?format={fmt}", "ar"))
        assert r.status_code == 200 and r.content[: len(magic)] == magic
        r = admin.get(url(f"active-members/?format={fmt}"))
        assert r.status_code == 200 and r.content[: len(magic)] == magic


def test_payroll_through_the_desk(data):
    ops, acct = desk("ops"), desk("accounts")
    run = PayrollRun.objects.get(status="draft")
    assert ops.post(url(f"payroll/runs/{run.pk}/"), {"action": "rebuild"}).status_code == 302
    ops.post(url(f"payroll/runs/{run.pk}/"), {"action": "submit"})
    assert PayrollRun.objects.get(pk=run.pk).status == "submitted"
    ops.post(url(f"payroll/runs/{run.pk}/"), {"action": "approve"})  # the OM can't approve
    assert PayrollRun.objects.get(pk=run.pk).status == "submitted"
    acct.post(url(f"payroll/runs/{run.pk}/"), {"action": "approve"})
    assert PayrollRun.objects.get(pk=run.pk).status == "approved"
    bank = acct.get(url(f"payroll/runs/{run.pk}/?format=bank"))
    assert bank.status_code == 200 and bank.content[:2] == b"PK"
    # A coach asks for leave; the OM decides.
    coach = desk("coach.bed2")
    start = TODAY + datetime.timedelta(days=20)
    coach.post(
        url("my-pay/"), {"action": "leave", "kind": "unpaid", "start": start.isoformat(), "end": start.isoformat()}
    )
    leave = Leave.objects.get(staff__user__email="coach.bed2@test.elite.local", start=start)
    ops.post(url("payroll/leave/"), {"leave": leave.pk, "decision": "approve"})
    assert Leave.objects.get(pk=leave.pk).status == "approved"
