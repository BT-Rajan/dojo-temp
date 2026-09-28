"""
Production settings. Everything secret comes from the environment; the app refuses
to start if a required secret is missing (ISO 27001 A.8.9 secure configuration).
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env

ENVIRONMENT = "production"
DEBUG = False

if not FIELD_ENCRYPTION_KEYS or not BLIND_INDEX_KEY:  # noqa: F405
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS and BLIND_INDEX_KEY must be set in production.")
if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 50 characters in production.")

# HTTPS everywhere (A.8.20, A.8.24).
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

ENFORCE_PRIVILEGED_MFA = env.bool("ENFORCE_PRIVILEGED_MFA", default=True)

if PAYMENT_GATEWAY == "test":  # noqa: F405
    raise ImproperlyConfigured("Choose a real PAYMENT_GATEWAY before going live; 'test' is for development only.")
