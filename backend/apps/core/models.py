from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """
    Base for business records.

    `version` supports optimistic concurrency: when two people edit the same record at
    the same time, the second save is rejected with HTTP 409 instead of silently
    overwriting the first person's changes (see apps.core.concurrency).
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    version = models.PositiveIntegerField(default=1, editable=False)

    # Field names whose values must never appear in the audit log.
    AUDIT_REDACT: tuple[str, ...] = ()

    class Meta:
        abstract = True
