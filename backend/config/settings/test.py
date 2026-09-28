"""Settings for the automated test suite (runs against a real MySQL database)."""

from .base import *  # noqa: F401,F403

ENVIRONMENT = "test"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

FIELD_ENCRYPTION_KEYS = ["dGVzdC1vbmx5LWtleS1mb3ItZmllbGQtZW5jcnlwdCE="]
BLIND_INDEX_KEY = "test-only-blind-index-key"

# Fast hashing in tests only.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # fast hashing, tests only

# Isolated in-memory cache so tests don't share state through Redis.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SESSION_ENGINE = "django.contrib.sessions.backends.db"

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"anon": "10000/min", "user": "10000/min", "login": "10000/min"},
}
