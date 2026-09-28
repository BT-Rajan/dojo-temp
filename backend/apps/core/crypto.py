"""
Encryption for sensitive personal data (Civil IDs, medical notes) — ISO 27001 A.8.24.

- EncryptedTextField stores Fernet (AES-128-CBC + HMAC-SHA256) ciphertext.
  MultiFernet allows key rotation: the first key encrypts, every key can decrypt.
- blind_index() produces a keyed HMAC fingerprint so encrypted values can still be
  checked for uniqueness and searched by exact match without decrypting the table.
"""

import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    keys = settings.FIELD_ENCRYPTION_KEYS
    if not keys:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS is not set.")
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:  # wrong key or tampered data
        raise ValueError("Encrypted value could not be decrypted.") from exc


def blind_index(value: str) -> str:
    key = settings.BLIND_INDEX_KEY
    if not key:
        raise ImproperlyConfigured("BLIND_INDEX_KEY is not set.")
    normalized = "".join(value.split()).upper()
    return hmac.new(key.encode(), normalized.encode(), hashlib.sha256).hexdigest()


class EncryptedTextField(models.TextField):
    """A text field that is encrypted at rest and decrypted transparently in Python."""

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return decrypt(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        return encrypt(value)


def mask(value: str | None, visible: int = 4) -> str | None:
    """Show only the last few characters, e.g. ********1234 (ISO 27001 A.8.11 data masking)."""
    if not value:
        return value
    return "*" * max(len(value) - visible, 0) + value[-visible:]
