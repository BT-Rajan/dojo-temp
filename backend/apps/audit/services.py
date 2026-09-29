"""
Recording audit events, and automatic change tracking for registered models.

Register a model with `track_changes(Model)` and every create, update and delete is
logged with the changed fields. Fields listed in the model's AUDIT_REDACT (e.g. Civil
IDs, medical notes) are logged only as "changed", never with their values.
"""

import datetime
import decimal

from django.db.models.signals import post_delete, post_save, pre_save

from apps.core.context import get_context

from .models import AuditEvent

REDACTED = "[redacted]"
IGNORED_FIELDS = {"updated_at", "created_at", "version", "updated_by", "created_by"}


def _plain(value):
    from django.db.models.fields.files import FieldFile

    if isinstance(value, (datetime.date, datetime.datetime, datetime.time, decimal.Decimal)):
        return str(value)
    if isinstance(value, FieldFile):
        return value.name or ""  # the stored file name, never the contents
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def record_event(action, instance=None, object_type="", object_id="", changes=None, actor=None, branch_id=None):
    ctx = get_context()
    if instance is not None:
        object_type = object_type or type(instance).__name__
        object_id = object_id or str(instance.pk)
        if branch_id is None:
            branch_id = getattr(instance, "branch_id", None)
    actor_id = actor.pk if actor is not None else ctx.user_id
    actor_label = ""
    if actor is not None:
        actor_label = actor.email
    elif actor_id is not None:
        from django.contrib.auth import get_user_model

        actor_label = get_user_model().objects.filter(pk=actor_id).values_list("email", flat=True).first() or ""
    return AuditEvent.objects.create(
        actor_id=actor_id,
        actor_label=actor_label,
        action=action,
        object_type=object_type,
        object_id=str(object_id)[:64],
        branch_id=branch_id,
        changes=changes or {},
        ip_address=ctx.ip_address,
        user_agent=ctx.user_agent,
        request_id=ctx.request_id,
    )


def _snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        data[field.name] = _plain(getattr(instance, field.attname))
    return data


def _redact(model, diff):
    redact = set(getattr(model, "AUDIT_REDACT", ()))
    return {k: (REDACTED if k in redact else v) for k, v in diff.items()}


def _pre_save(sender, instance, **kwargs):
    if instance.pk is None:
        instance._audit_before = None
        return
    old = sender.objects.filter(pk=instance.pk).first()
    instance._audit_before = _snapshot(old) if old else None


def _post_save(sender, instance, created, **kwargs):
    after = _snapshot(instance)
    before = getattr(instance, "_audit_before", None)
    if created or before is None:
        diff = {k: [None, v] for k, v in after.items() if v not in (None, "")}
        action = "create"
    else:
        diff = {k: [before.get(k), v] for k, v in after.items() if before.get(k) != v}
        action = "update"
        if not diff:
            return
    redact = set(getattr(sender, "AUDIT_REDACT", ()))
    diff = {k: (REDACTED if k in redact else v) for k, v in diff.items()}
    record_event(action=action, instance=instance, changes=diff)


def _post_delete(sender, instance, **kwargs):
    record_event(action="delete", instance=instance, changes=_redact(sender, _snapshot(instance)))


def track_changes(model):
    uid = f"audit_{model._meta.label_lower}"
    pre_save.connect(_pre_save, sender=model, dispatch_uid=uid + "_pre")
    post_save.connect(_post_save, sender=model, dispatch_uid=uid + "_post")
    post_delete.connect(_post_delete, sender=model, dispatch_uid=uid + "_del")
    return model
