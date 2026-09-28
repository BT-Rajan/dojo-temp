"""
Safe editing when many people use the system at the same time.

Optimistic locking: every record carries a `version`. A client must send the version it
read when it saves. If someone else saved in the meantime, the versions differ and the
save is rejected with 409 Conflict, so no one's changes are silently overwritten.

For counters that many people change at once (stock quantities, class places), use
`lock_for_update()` which takes a row lock inside the current transaction.
"""

from django.db.models import F
from rest_framework import serializers, status
from rest_framework.exceptions import APIException


class EditConflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "This record was changed by someone else. Reload it and try again."
    default_code = "edit_conflict"


class VersionedSerializerMixin(serializers.Serializer):
    """Exposes `version` on reads and requires it on updates."""

    version = serializers.IntegerField(required=False)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance is None:
            attrs.pop("version", None)  # new records always start at version 1
        elif "version" not in attrs:
            raise serializers.ValidationError({"version": "Send the version you loaded so edits don't collide."})
        return attrs


class OptimisticLockMixin:
    """For DRF model viewsets: applies the version check atomically on update."""

    def perform_update(self, serializer):
        expected = serializer.validated_data.pop("version")
        instance = serializer.instance
        model = type(instance)
        # Atomic compare-and-bump in one UPDATE statement: exactly one of two
        # simultaneous saves can win; the other sees 0 rows and gets a conflict.
        bumped = model.objects.filter(pk=instance.pk, version=expected).update(version=F("version") + 1)
        if bumped == 0:
            raise EditConflict()
        instance.version = expected + 1
        serializer.save(updated_by=self.request.user)


def lock_for_update(queryset, **lookup):
    """Row-level lock (SELECT ... FOR UPDATE) for the rest of the current transaction."""
    return queryset.select_for_update().get(**lookup)
