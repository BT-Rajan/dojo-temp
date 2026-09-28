"""Celery app for background jobs (renewal reminders, scheduled reports, escalation timers)."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("elite")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
