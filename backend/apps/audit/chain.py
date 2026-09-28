import hashlib
import json

from django.db import transaction
from django.db.models import Max

from .models import AuditEvent

GENESIS = "0" * 64
SEAL_LOCK = "elite_audit_seal"


def event_digest(event: AuditEvent, prev_hash: str) -> str:
    body = {
        "id": event.id,
        "occurred_at": event.occurred_at.isoformat(),
        "actor": event.actor_id,
        "actor_label": event.actor_label,
        "action": event.action,
        "object_type": event.object_type,
        "object_id": event.object_id,
        "branch_id": event.branch_id,
        "changes": event.changes,
        "ip": event.ip_address,
        "request_id": event.request_id,
        "prev": prev_hash,
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def seal_pending(batch_size: int = 1000) -> int:
    """Seals committed, unsealed events into the chain. Only one sealer runs at a time (MySQL named lock)."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, 10)", [SEAL_LOCK])
        if cursor.fetchone()[0] != 1:
            return 0
    try:
        with transaction.atomic():
            last = AuditEvent.objects.filter(seal_seq__isnull=False).order_by("-seal_seq").first()
            seq = last.seal_seq if last else 0
            prev = last.hash if last else GENESIS
            sealed = 0
            for event in AuditEvent.objects.filter(seal_seq__isnull=True).order_by("id")[:batch_size]:
                seq += 1
                digest = event_digest(event, prev)
                # queryset.update bypasses the model's "no changes" guard; only the sealer does this.
                AuditEvent.objects.filter(pk=event.pk, seal_seq__isnull=True).update(
                    seal_seq=seq, prev_hash=prev, hash=digest
                )
                prev = digest
                sealed += 1
        return sealed
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", [SEAL_LOCK])


def verify_chain() -> dict:
    """Recomputes every hash. Returns the first broken link, if any."""
    prev = GENESIS
    expected_seq = 1
    checked = 0
    for event in AuditEvent.objects.filter(seal_seq__isnull=False).order_by("seal_seq").iterator():
        if event.seal_seq != expected_seq:
            return {"ok": False, "checked": checked, "problem": f"Missing event before seal #{event.seal_seq}"}
        if event.prev_hash != prev or event_digest(event, prev) != event.hash:
            return {"ok": False, "checked": checked, "problem": f"Event #{event.id} was altered"}
        prev = event.hash
        expected_seq += 1
        checked += 1
    top = AuditEvent.objects.aggregate(m=Max("seal_seq"))["m"] or 0
    return {"ok": True, "checked": checked, "last_seal": top}
