"""Phase 2 scheduled jobs (Celery beat; also `python manage.py run_phase2_jobs`)."""

import datetime

from celery import shared_task
from django.core.mail import EmailMessage
from django.utils import timezone


@shared_task
def hourly_jobs():
    from apps.inventory.services import remind_overdue_requests
    from apps.operations.services import auto_escalate_overdue, remind_overdue_complaints

    return {
        "incidents_escalated": auto_escalate_overdue(),
        "complaint_reminders": remind_overdue_complaints(),
        "purchase_requests_overdue": remind_overdue_requests(),
        "reports_emailed": send_subscriptions(),
    }


@shared_task
def daily_jobs():
    from apps.inventory.services import auto_create_counts
    from apps.operations.services import close_leaver_accounts
    from apps.payroll.services import remind_expiring_documents
    from apps.training.services import daily_jobs as training_jobs

    return {
        "leavers_closed": close_leaver_accounts(),
        "document_reminders": remind_expiring_documents(),
        "stock_counts_created": auto_create_counts(),
        **training_jobs(),
    }


@shared_task
def friday_snapshot():
    from .services import snapshot_active_members

    return {"snapshots": snapshot_active_members()}


@shared_task
def weekly_reports_due():
    from .services import remind_due_reports

    return {"reminders": remind_due_reports()}


# ---------------------------------------------------------------------------
# "Email me this report"
# ---------------------------------------------------------------------------
def _due(sub, now) -> bool:
    """Daily 07:00 · Friday 21:00 (active members) · Saturday 12:30 (weekly) · 1st 07:00 (monthly)."""
    last = timezone.localtime(sub.last_sent_at) if sub.last_sent_at else None
    today = now.date()
    if sub.report == "daily":
        return now.hour >= 7 and (last is None or last.date() < today)
    if sub.report == "active_members":
        return now.weekday() == 4 and now.hour >= 21 and (last is None or last.date() < today)
    if sub.report in ("weekly_sales", "weekly_branch"):
        return now.weekday() == 5 and (now.hour, now.minute) >= (12, 30) and (last is None or last.date() < today)
    if sub.report == "monthly":
        return today.day == 1 and now.hour >= 7 and (last is None or last.date() < today)
    return False


def allowed(sub) -> bool:
    from apps.rbac.services import has_perm

    user = sub.user
    if not user.is_active:
        return False
    if sub.branch_id is None:
        return has_perm(user, "reports.all")
    return has_perm(user, "reports.branch", sub.branch_id) or has_perm(user, "reports.all")


def build_attachment(sub, now):
    """Returns (subject, filename, content, content type) for one subscription."""
    from apps.organization.models import Branch

    from . import documents, services
    from .export import render
    from .models import WeeklyReport, week_start

    lang = sub.language
    branches = [sub.branch] if sub.branch_id else list(Branch.objects.filter(is_active=True).order_by("-code"))
    scope = (
        (sub.branch.name_ar if lang == "ar" else sub.branch.name)
        if sub.branch_id
        else ("الفرعان" if lang == "ar" else "Both branches")
    )
    today = now.date()
    if sub.report == "daily":
        doc = documents.daily_doc(services.daily_dashboard(branches, today - datetime.timedelta(days=1)), lang)
    elif sub.report == "monthly":
        from apps.payroll.services import previous_month

        doc = documents.monthly_doc(services.monthly_dashboard(branches, previous_month(today.replace(day=1))), lang)
    elif sub.report == "active_members":
        data = services.active_members(today, sub.branch, lang)
        doc = documents.active_members_doc(data, scope, services.active_change(sub.branch, today), lang)
    else:
        kind = WeeklyReport.Kind.SALES if sub.report == "weekly_sales" else WeeklyReport.Kind.BRANCH
        start = week_start(today) - datetime.timedelta(days=7)
        branch = branches[0]
        report = WeeklyReport.objects.filter(kind=kind, branch=branch, week_start=start).first()
        data = report.data if report else services.jsonable(services.build(kind, branch, start, lang))
        maker = documents.weekly_sales_doc if kind == WeeklyReport.Kind.SALES else documents.weekly_branch_doc
        doc = maker(data, branch, report, lang)
    content, ctype, ext = render(doc, sub.format, lang)
    filename = f"elite-{sub.report}-{today:%Y%m%d}.{ext}"
    return doc["title"], filename, content, ctype


def send_subscriptions(now=None) -> int:
    from .models import ReportSubscription

    now = timezone.localtime(now) if now else timezone.localtime()
    sent = 0
    for sub in ReportSubscription.objects.filter(is_active=True).select_related("user", "branch"):
        if not _due(sub, now):
            continue
        if sub.report in ("weekly_sales", "weekly_branch") and sub.branch_id is None:
            sub.is_active = False  # weekly forms are per branch
            sub.save(update_fields=["is_active", "updated_at"])
            continue
        if not allowed(sub):
            sub.is_active = False  # access removed since subscribing: stop sending (ISO 27001 A.5.15)
            sub.save(update_fields=["is_active", "updated_at"])
            continue
        subject, filename, content, ctype = build_attachment(sub, now)
        msg = EmailMessage(subject=f"Elite Academy · {subject}", body=subject, to=[sub.user.email])
        msg.attach(filename, content, ctype)
        msg.send(fail_silently=False)
        sub.last_sent_at = now
        sub.save(update_fields=["last_sent_at", "updated_at"])
        sent += 1
    return sent
