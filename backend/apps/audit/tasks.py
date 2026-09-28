from celery import shared_task

from .chain import seal_pending


@shared_task
def seal_audit_events():
    """Schedule every minute with Celery beat so new events are sealed promptly."""
    return seal_pending()
