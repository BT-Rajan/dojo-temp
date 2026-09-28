"""
Outgoing WhatsApp / SMS messages (EA-SYS-SCOPE-01 M17).

The provider is chosen before launch (decision 6). Everything that sends a message calls
send_message(); only this module knows which provider is used.

- "console": development/test — logs the message and keeps the last few in the cache so
  the developer can read test codes. Never used in production.
"""

import logging

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger("elite.messaging")
OUTBOX_KEY = "messaging:outbox"


def send_message(to: str, text: str, channel: str = "whatsapp") -> bool:
    backend = settings.MESSAGING_BACKEND
    if backend == "console":
        outbox = cache.get(OUTBOX_KEY, [])
        outbox = ([{"to": to, "text": text, "channel": channel}] + outbox)[:20]
        cache.set(OUTBOX_KEY, outbox, 3600)
        log.info("[%s to %s] %s", channel, to, text)
        return True
    raise NotImplementedError(f"Messaging backend '{backend}' is not configured yet.")


def last_message_to(to: str):
    for message in cache.get(OUTBOX_KEY, []):
        if message["to"] == to:
            return message
    return None
