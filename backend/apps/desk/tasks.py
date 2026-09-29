"""
"My tasks" (scope M9): every open item assigned to the signed-in person, with due dates —
follow-ups, approvals, handoffs, escalations, reports, payroll and expiring documents.
"""

import datetime

from django.urls import reverse
from django.utils import timezone

from .access import can


def _task(en, ar, url, due=None, count=None, urgent=False):
    now = timezone.now()
    due_dt = due
    if isinstance(due, datetime.date) and not isinstance(due, datetime.datetime):
        due_dt = timezone.make_aware(datetime.datetime.combine(due, datetime.time(23, 59)))
    if isinstance(due, datetime.datetime):
        label = timezone.localtime(due).strftime("%d/%m %H:%M")
    elif isinstance(due, datetime.date):
        label = due.strftime("%d/%m")
    else:
        label = ""
    return {
        "en": en,
        "ar": ar,
        "url": url,
        "due": due,
        "due_label": label,
        "count": count,
        "overdue": bool(due_dt and due_dt < now),
        "urgent": urgent,
    }


def my_tasks(request) -> list[dict]:
    from apps.classes.models import ClassChange
    from apps.finance.models import Expense
    from apps.operations.models import Complaint, Handover, Incident, ShiftOpening
    from apps.organization.models import PriceChange, PricingOption
    from apps.payroll.models import Advance, Leave, PayrollRun, PayrollSettings
    from apps.renewals.models import InstructorHandoff
    from apps.renewals.services import follow_up_list
    from apps.reports.models import WeeklyReport, week_start
    from apps.reports.services import _python_open_days
    from apps.sales.models import AccountRequest, CashUp
    from apps.staff.models import StaffDocument

    user, branch, today = request.user, request.branch, timezone.localdate()
    out = []

    if branch is not None and can(request, "ops.shift") and today.weekday() in _python_open_days(branch):
        if not ShiftOpening.objects.filter(branch=branch, date=today).exists():
            out.append(
                _task(
                    "Complete the shift opening checklist",
                    "أكمل قائمة فتح النوبة",
                    reverse("desk:shift"),
                    today,
                    urgent=True,
                )
            )
    if branch is not None and can(request, "renewals.follow_up"):
        n = len(follow_up_list(branch, today))
        if n:
            out.append(_task("Renewal follow-ups", "متابعات التجديد", reverse("desk:renewals"), today, n))
    if branch is not None and can(request, "sales.cashup"):
        yesterday = today - datetime.timedelta(days=1)
        if yesterday.weekday() in _python_open_days(branch):
            done = CashUp.objects.filter(branch=branch, date=yesterday).exclude(status=CashUp.Status.DRAFT).exists()
            if not done:
                out.append(
                    _task(
                        f"Cash-up for {yesterday:%d/%m} not submitted",
                        f"الإغلاق اليومي لـ {yesterday:%d/%m} لم يُرسل",
                        reverse("desk:cashup") + f"?date={yesterday:%Y-%m-%d}",
                        yesterday,
                        urgent=True,
                    )
                )
    handoffs = InstructorHandoff.objects.filter(instructor=user, done_at__isnull=True).count()
    if handoffs:
        out.append(
            _task("Members handed to you (3 no-answers)", "أعضاء محوّلون إليك", reverse("desk:home"), None, handoffs)
        )

    # Approvals
    approvals = 0
    if can(request, "sales.approve_refund"):
        approvals += AccountRequest.objects.filter(status="pending").count()
    if can(request, "pricing.approve"):
        approvals += PriceChange.objects.filter(status="pending").count()
        approvals += PricingOption.objects.filter(approval="pending").count()
    if can(request, "classes.change_approve"):
        approvals += ClassChange.objects.filter(status="pending").count()
    if can(request, "reports.verify") or can(request, "finance.manage"):
        approvals += CashUp.objects.filter(status="submitted").exclude(submitted_by=user).count()
    if approvals:
        out.append(_task("Approvals waiting", "موافقات بانتظارك", reverse("desk:approvals"), None, approvals))
    if can(request, "finance.expense_approve"):
        n = Expense.objects.filter(status="pending").exclude(created_by=user).count()
        if n:
            out.append(
                _task("Expenses to approve", "مصروفات للاعتماد", reverse("desk:expenses") + "?status=pending", None, n)
            )

    # Incidents and complaints
    for i in Incident.objects.filter(follow_up_owner=user, status="open"):
        out.append(
            _task(
                f"Incident follow-up {i.reference}",
                f"متابعة الحادثة {i.reference}",
                reverse("desk:incident", args=[i.pk]),
                i.follow_up_due,
            )
        )
    if branch is not None and can(request, "ops.manage"):
        for i in Incident.objects.filter(branch=branch, needs_ceo=True, ceo_escalated_at__isnull=True):
            out.append(
                _task(
                    f"Tell the CEO about incident {i.reference}",
                    f"أبلغ الرئيس التنفيذي بالحادثة {i.reference}",
                    reverse("desk:incident", args=[i.pk]),
                    i.ceo_due_at,
                    urgent=True,
                )
            )
        for c in Complaint.objects.filter(branch=branch, status="open", escalated=True).exclude(handled_by=user):
            out.append(
                _task(
                    f"Escalated complaint {c.reference}",
                    f"شكوى مصعّدة {c.reference}",
                    reverse("desk:complaint", args=[c.pk]),
                    c.reply_due_at,
                )
            )
    for c in Complaint.objects.filter(handled_by=user, status="open"):
        en = f"Reply to complaint {c.reference}" if not c.replied_at else f"Close complaint {c.reference}"
        ar = f"الرد على الشكوى {c.reference}" if not c.replied_at else f"إغلاق الشكوى {c.reference}"
        out.append(_task(en, ar, reverse("desk:complaint", args=[c.pk]), None if c.replied_at else c.reply_due_at))
    for h in Handover.objects.filter(incoming=user, status="open"):
        out.append(
            _task(
                f"Accept handover from {h.outgoing.full_name}",
                f"استلام المهام من {h.outgoing.full_name}",
                reverse("desk:handover", args=[h.pk]),
                h.cover_from,
                h.items_left,
            )
        )

    # Weekly reports: due Saturday 12:00
    last_week = week_start(today) - datetime.timedelta(days=7)
    if branch is not None and can(request, "reports.branch"):
        for kind, en, ar in (
            ("sales", "Weekly Sales Report (FRM-06)", "تقرير المبيعات الأسبوعي"),
            ("branch", "Weekly Branch Report (FRM-07)", "التقرير الأسبوعي للفرع"),
        ):
            report = WeeklyReport.objects.filter(kind=kind, branch=branch, week_start=last_week).first()
            if report is None or report.status == "returned":
                due = timezone.make_aware(
                    datetime.datetime.combine(last_week + datetime.timedelta(days=7), datetime.time(12))
                )
                url = reverse("desk:weekly_report", args=[kind, branch.code, last_week.isoformat()])
                out.append(_task(f"Prepare the {en}", f"أعدّ {ar}", url, due))
    if can(request, "reports.verify"):
        from apps.rbac.services import branch_scope

        scope = branch_scope(user, "reports.verify")
        qs = WeeklyReport.objects.filter(status="prepared").exclude(prepared_by=user)
        if scope is not None:
            qs = qs.filter(branch_id__in=scope)
        n = qs.count()
        if n:
            out.append(
                _task("Weekly reports to verify", "تقارير أسبوعية للتحقق", reverse("desk:weekly_reports"), None, n)
            )

    # Payroll
    if can(request, "payroll.prepare"):
        month = today.replace(day=1)
        run = PayrollRun.objects.filter(month=month).first()
        from apps.payroll.services import pay_day

        pay = pay_day(month)
        if (run is None or run.status == "draft") and today >= pay - datetime.timedelta(days=7):
            out.append(
                _task(
                    f"Prepare and submit payroll {month:%m/%Y}",
                    f"أعدّ رواتب {month:%m/%Y} وأرسلها",
                    reverse("desk:payroll"),
                    pay - datetime.timedelta(days=3),
                )
            )
        n = Advance.objects.filter(status="pending").exclude(staff__user=user).count()
        if n:
            out.append(_task("Salary advances to decide", "سلف بانتظار القرار", reverse("desk:advances"), None, n))
    if can(request, "leave.approve"):
        n = Leave.objects.filter(status="pending").exclude(staff__user=user).count()
        if n:
            out.append(_task("Leave requests to decide", "طلبات إجازة بانتظار القرار", reverse("desk:leave"), None, n))
    if can(request, "payroll.approve"):
        for run in PayrollRun.objects.filter(status="submitted").exclude(submitted_by=user):
            out.append(
                _task(
                    f"Approve payroll {run.month:%m/%Y}",
                    f"اعتمد رواتب {run.month:%m/%Y}",
                    reverse("desk:payroll_run", args=[run.pk]),
                    run.pay_date,
                )
            )
        if not PayrollSettings.get().confirmed:
            out.append(
                _task(
                    "Confirm the payroll rules",
                    "اعتمد قواعد الرواتب",
                    reverse("desk:payroll_settings"),
                    None,
                    urgent=True,
                )
            )

    # Documents
    horizon = today + datetime.timedelta(days=30)
    for doc in StaffDocument.objects.filter(
        staff__user=user, expires_on__lte=horizon, expires_on__gte=today - datetime.timedelta(days=30)
    ):
        out.append(
            _task(
                f"Renew your {doc.get_kind_display().lower()}",
                f"جدّد {doc.get_kind_display()}",
                reverse("desk:my_pay"),
                doc.expires_on,
            )
        )
    if can(request, "staff.manage"):
        n = (
            StaffDocument.objects.filter(expires_on__lte=horizon, staff__user__is_active=True)
            .exclude(staff__user=user)
            .count()
        )
        if n:
            out.append(
                _task(
                    "Staff documents expiring within 30 days",
                    "مستندات موظفين تنتهي خلال 30 يوماً",
                    reverse("desk:staff_list") + "?expiring=1",
                    None,
                    n,
                )
            )

    # Inventory (M8), online orders (M19), Mindbody (M18)
    from apps.inventory.models import Discrepancy, PurchaseRequest, StockCount, Transfer
    from apps.shop.models import Order

    if can(request, "inventory.approve"):
        for req in PurchaseRequest.objects.filter(status="submitted").exclude(created_by=user):
            out.append(
                _task(
                    f"Decide purchase request {req.reference}",
                    f"قرّر طلب الشراء {req.reference}",
                    reverse("desk:purchase_request", args=[req.pk]),
                    req.due_at,
                )
            )
        for c in StockCount.objects.filter(status="submitted").exclude(recorded_by=user).exclude(counted_by=user):
            out.append(
                _task(
                    f"Approve stock count {c.reference}",
                    f"اعتمد الجرد {c.reference}",
                    reverse("desk:stock_count", args=[c.pk]),
                    c.due_date,
                )
            )
        n = Discrepancy.objects.filter(status="open").count()
        if n:
            out.append(_task("Open delivery discrepancies", "فروقات استلام مفتوحة", reverse("desk:receipts"), None, n))
    if can(request, "inventory.purchase"):
        n = PurchaseRequest.objects.filter(status__in=PurchaseRequest.OPEN_FOR_ORDER).count()
        if n:
            out.append(
                _task(
                    "Approved purchase requests to order",
                    "طلبات شراء معتمدة للطلب",
                    reverse("desk:purchase_orders"),
                    None,
                    n,
                )
            )
    if branch is not None and can(request, "inventory.manage"):
        for t in Transfer.objects.filter(to_branch=branch, status="sent").exclude(sent_by=user):
            out.append(
                _task(
                    f"Count and accept transfer {t.reference}",
                    f"عدّ واستلم التحويل {t.reference}",
                    reverse("desk:transfer", args=[t.pk]),
                    t.sent_at,
                    urgent=True,
                )
            )
        for c in StockCount.objects.filter(branch=branch, status__in=["counting", "returned"]):
            out.append(
                _task(
                    f"Monthly stock count {c.reference}",
                    f"الجرد الشهري {c.reference}",
                    reverse("desk:stock_count", args=[c.pk]),
                    c.due_date,
                )
            )
        n = Order.objects.filter(status__in=["paid", "ready"], items__branch=branch).distinct().count()
        if n:
            out.append(
                _task("Online orders to hand over", "طلبات إلكترونية للتسليم", reverse("desk:online_orders"), None, n)
            )
    if can(request, "data.import"):
        from apps.mindbody.services import unmapped_options

        n = unmapped_options().count()
        if n:
            out.append(
                _task(
                    "Map Mindbody pricing options", "اربط خيارات أسعار مايندبودي", reverse("desk:option_map"), None, n
                )
            )

    # Training (M7)
    from apps.training.models import ProgressNote, Promotion, TestCandidate

    if branch is not None and can(request, "sales.sell"):
        n = Promotion.objects.filter(branch=branch, belt_status="to_issue").count()
        if n:
            out.append(_task("Belts to hand over", "أحزمة للتسليم", reverse("desk:belts"), None, n, urgent=True))
    if can(request, "training.teach") or can(request, "training.manage"):
        n = ProgressNote.objects.filter(instructor=user, status="draft").count()
        if n:
            out.append(
                _task(
                    "Monthly progress notes to send",
                    "تقارير التقدم الشهرية للإرسال",
                    reverse("desk:progress_notes"),
                    today.replace(day=1) + datetime.timedelta(days=6),
                    n,
                )
            )
    if branch is not None and can(request, "training.manage"):
        pending = TestCandidate.objects.filter(
            test_day__branch=branch, test_day__date__lte=today, test_day__status="planned"
        )
        for td_id, td_date in pending.values_list("test_day_id", "test_day__date").distinct():
            out.append(
                _task(
                    "Record test day results and promotions",
                    "سجّل نتائج يوم الاختبار والترقيات",
                    reverse("desk:test_day", args=[td_id]),
                    td_date,
                )
            )

    if branch is not None and can(request, "leads.manage"):
        from apps.assistant.models import Conversation
        from apps.leads.models import Lead
        from apps.leads.services import overdue_leads

        n = Lead.objects.filter(branch=branch, stage="new", owner__isnull=True).count()
        if n:
            out.append(
                _task("New leads to contact", "عملاء محتملون جدد للتواصل", reverse("desk:leads"), None, n, urgent=True)
            )
        n = overdue_leads(user).count()
        if n:
            url = reverse("desk:leads") + "?show=overdue"
            out.append(_task("Your overdue leads", "عملاؤك المحتملون المتأخرون", url, None, n, urgent=True))
        n = Conversation.objects.filter(channel="saqr", handed_off_at__isnull=False, taken_at__isnull=True).count()
        if n:
            out.append(
                _task(
                    "SAQR chats waiting for a person", "محادثات صقر بانتظار موظف", reverse("desk:saqr"), None, n, True
                )
            )
    if can(request, "marketing.approve"):
        from apps.leads.models import Broadcast

        n = Broadcast.objects.filter(status="draft").exclude(created_by=user).count()
        if n:
            out.append(_task("Broadcasts to approve", "رسائل جماعية للاعتماد", reverse("desk:broadcasts"), None, n))

    def key(t):
        due = t["due"]
        if isinstance(due, datetime.datetime):
            due = timezone.localtime(due).date()
        return (not t["overdue"], not t["urgent"], due or datetime.date.max)

    return sorted(out, key=key)
