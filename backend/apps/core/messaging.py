"""
Outgoing WhatsApp / SMS messages (EA-SYS-SCOPE-01 M17, decisions P6-7 and P6-8).

The provider is chosen before launch (open item O-7). Everything that sends a message calls
send_message(); only this module knows which provider is used. Every message is logged with its
category; service messages a family has turned off are logged as skipped and not sent.

- "console": development/test — logs the message and keeps the last few in the cache so
  the developer can read test codes. Never used in production.
"""

import logging

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("elite.messaging")
OUTBOX_KEY = "messaging:outbox"
CATEGORIES = ("essential", "service", "marketing", "staff")


def _log(to, text, channel, category, kind, member, status, error=""):
    try:
        from apps.notifications.models import MessageLog

        MessageLog.objects.create(
            to=to or "",
            channel=channel,
            category=category,
            kind=kind[:40],
            text=text,
            member=member,
            status=status,
            error=error[:255],
        )
    except Exception:  # noqa: BLE001 - logging must never stop a message
        log.exception("Could not write the message log")


def send_message(
    to: str, text: str, channel: str = "whatsapp", *, category: str = "essential", kind: str = "", member=None
) -> bool:
    if category not in CATEGORIES:
        raise ValueError(f"Unknown message category {category}")
    if category == "service":
        from apps.notifications.services import service_messages_on

        if not service_messages_on(to):
            _log(to, text, channel, category, kind, member, "skipped")
            return False
    backend = settings.MESSAGING_BACKEND
    if backend == "console":
        outbox = cache.get(OUTBOX_KEY, [])
        outbox = ([{"to": to, "text": text, "channel": channel}] + outbox)[:20]
        cache.set(OUTBOX_KEY, outbox, 3600)
        log.info("[%s to %s] %s", channel, to, text)
        _log(to, text, channel, category, kind, member, "sent")
        return True
    _log(to, text, channel, category, kind, member, "failed", f"Backend '{backend}' not configured")
    raise NotImplementedError(f"Messaging backend '{backend}' is not configured yet.")


def last_message_to(to: str):
    for message in cache.get(OUTBOX_KEY, []):
        if message["to"] == to:
            return message
    return None
