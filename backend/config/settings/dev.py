"""Local development settings. Never used in production."""

from .base import *  # noqa: F401,F403
from .base import env

ENVIRONMENT = "development"
DEBUG = env.bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Development-only keys, used only when .env does not provide them.
if not FIELD_ENCRYPTION_KEYS:  # noqa: F405
    FIELD_ENCRYPTION_KEYS = ["bG9jYWwtZGV2LW9ubHkta2V5LTMyLWJ5dGVzLWxvbmc="]
if not BLIND_INDEX_KEY:  # noqa: F405
    BLIND_INDEX_KEY = "local-dev-only-blind-index-key"

# Show the messages the console backend "sends" (e.g. portal sign-in codes) in the terminal.
LOGGING["loggers"]["elite.messaging"] = {"handlers": ["console"], "level": "INFO", "propagate": False}  # noqa: F405
