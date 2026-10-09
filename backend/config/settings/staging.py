"""
Review (staging) server: the real system with fictional test data, for staff to try before go-live.
Production-like (no debug pages, real secrets, gunicorn), but the test payment page and console messaging stay on,
and search engines are told to stay away. Never holds real member data.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, env

ENVIRONMENT = "staging"
DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

if not FIELD_ENCRYPTION_KEYS or not BLIND_INDEX_KEY:  # noqa: F405
    raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS and BLIND_INDEX_KEY must be set on the review server.")
if len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be at least 50 characters on the review server.")

# Behind CloudPanel's nginx with a Let's Encrypt certificate (STAGING_HTTPS=true), or plain HTTP by IP for a quick look.
if env.bool("STAGING_HTTPS", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Test accounts are used by several reviewers; two-step sign-in is switched on with the live system.
ENFORCE_PRIVILEGED_MFA = env.bool("ENFORCE_PRIVILEGED_MFA", default=False)

# Static files served by the app itself (no separate web server needed for a review).
MIDDLEWARE = [*MIDDLEWARE]
MIDDLEWARE.insert(
    MIDDLEWARE.index("django.middleware.security.SecurityMiddleware") + 1, "whitenoise.middleware.WhiteNoiseMiddleware"
)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
