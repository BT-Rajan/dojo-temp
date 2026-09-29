"""Phase 7 scheduled jobs (Celery beat)."""

from celery import shared_task


@shared_task
def hourly_jobs():
    from .services import hourly_jobs as run

    return run()


@shared_task
def daily_jobs():
    from .services import daily_jobs as run

    return run()
