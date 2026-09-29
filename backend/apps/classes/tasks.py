"""Scheduled jobs for Phase 1 (Celery beat; also runnable with `python manage.py run_daily_jobs`)."""

from celery import shared_task


@shared_task
def daily_jobs():
    from apps.classes.services import generate_sessions, mark_no_shows
    from apps.organization.services import apply_due_price_changes
    from apps.renewals.services import send_reminders

    return {
        "prices_applied": apply_due_price_changes(),
        "sessions_created": generate_sessions(),
        "reminders_sent": send_reminders(),
        "no_shows": mark_no_shows(),
    }


@shared_task
def hourly_jobs():
    from apps.classes.services import mark_no_shows

    return {"no_shows": mark_no_shows()}
