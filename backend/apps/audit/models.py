from django.conf import settings
from django.db import models


class AuditEventQuerySet(models.QuerySet):
    def delete(self):
        raise PermissionError("Audit events cannot be deleted.")


class AuditEvent(models.Model):
    """
    Append-only record of who did what, when and from where (ISO 27001 A.8.15).

    Events are written freely (no locking, so busy periods stay fast) and are then
    *sealed* in order into a SHA-256 hash chain by apps.audit.chain.seal_pending().
    Any later edit, deletion or insertion breaks the chain and is reported by
    `python manage.py verify_audit`.
    """

    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    actor_label = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=40, db_index=True)
    object_type = models.CharField(max_length=80, blank=True, db_index=True)
    object_id = models.CharField(max_length=64, blank=True, db_index=True)
    branch_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    seal_seq = models.BigIntegerField(null=True, blank=True, unique=True)
    prev_hash = models.CharField(max_length=64, blank=True)
    hash = models.CharField(max_length=64, blank=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return f"#{self.id} {self.action} {self.object_type}:{self.object_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionError("Audit events cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit events cannot be deleted.")
