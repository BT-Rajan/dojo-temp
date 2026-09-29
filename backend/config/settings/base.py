"""
Base settings shared by every environment.

Security-relevant settings are commented with the ISO/IEC 27001:2022 Annex A control
they support. See docs/security/ISO27001_CONTROLS.md for the full mapping.
"""

from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

ENVIRONMENT = env("DJANGO_ENVIRONMENT", default="development")
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "axes",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "apps.core",
    "apps.accounts",
    "apps.rbac",
    "apps.audit",
    "apps.organization",
    "apps.staff",
    "apps.members",
    "apps.portal",
    "apps.testdata",
    "apps.website",
    "apps.shop",
    "apps.classes",
    "apps.sales",
    "apps.renewals",
    "apps.operations",
    "apps.finance",
    "apps.reports",
    "apps.payroll",
    "apps.desk",
    # Wagtail CMS (website content, gallery, events) — EA-SYS-SCOPE-01 M14
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.contrib.settings",
    "wagtail.contrib.routable_page",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "apps.website.middleware.SiteLocaleMiddleware",  # /en/ and /ar/ for the website only
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "apps.core.middleware.IdleSessionTimeoutMiddleware",
    "apps.core.middleware.RequestContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
    "apps.website.middleware.CmsAccessMiddleware",
    # Axes must be last: it records failed logins and locks out brute-force attempts (A.8.5).
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "wagtail.contrib.settings.context_processors.settings",
                "apps.website.context_processors.site",
                "apps.desk.context.desk",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database — MySQL 8, utf8mb4 for Arabic, READ COMMITTED for predictable
# behaviour under many simultaneous users (Django's recommended level for MySQL).
# ---------------------------------------------------------------------------
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"].setdefault("OPTIONS", {})
DATABASES["default"]["OPTIONS"].update(
    {
        "charset": "utf8mb4",
        "isolation_level": "read committed",
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES', time_zone='+03:00'",
    }
)
# Every API request runs in one transaction: all-or-nothing writes when many users act at once.
DATABASES["default"]["ATOMIC_REQUESTS"] = True
# Reuse database connections between requests; health-checked before reuse.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
DATABASES["default"].setdefault("TEST", {})
DATABASES["default"]["TEST"].update({"CHARSET": "utf8mb4", "COLLATION": "utf8mb4_0900_ai_ci"})

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache and sessions — Redis, shared by all application servers so any server
# can handle any user's next request (horizontal scaling for concurrent use).
# ---------------------------------------------------------------------------
REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "elite",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# ---------------------------------------------------------------------------
# Authentication (A.5.17, A.8.5)
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Brute-force protection: 5 failures per account + IP locks for 15 minutes.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_USERNAME_FORM_FIELD = "username"

# Two-factor authentication for privileged roles.
ENFORCE_PRIVILEGED_MFA = env.bool("ENFORCE_PRIVILEGED_MFA", default=False)
OTP_TOTP_ISSUER = "Elite Academy"

# Sessions: server-side, revocable, HttpOnly, 8-hour maximum, 30-minute idle timeout (A.8.5).
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_IDLE_TIMEOUT_SECONDS = env.int("SESSION_IDLE_TIMEOUT_SECONDS", default=30 * 60)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "elite_session"
CSRF_COOKIE_NAME = "elite_csrftoken"
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Transport and browser security headers (A.8.20, A.8.21, A.8.26)
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Cryptography for sensitive fields (A.8.24)
# ---------------------------------------------------------------------------
FIELD_ENCRYPTION_KEYS = env.list("FIELD_ENCRYPTION_KEYS", default=[])
BLIND_INDEX_KEY = env("BLIND_INDEX_KEY", default="")

# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.accounts.authentication.CsrfEnforcedSessionAuthentication"],
    # Deny by default: every endpoint must be logged in AND declare the RBAC permission it needs.
    "DEFAULT_PERMISSION_CLASSES": ["apps.rbac.drf.RBACPermission"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.exception_handler",
    # Rate limits protect the system for everyone when many users are online (A.8.6).
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="120/min"),
        "user": env("THROTTLE_USER", default="600/min"),
        "login": env("THROTTLE_LOGIN", default="20/min"),
    },
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Elite Academy API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# Language, time zone and money (Kuwait)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("ar", "العربية")]
TIME_ZONE = "Asia/Kuwait"
USE_I18N = True
USE_TZ = True
CURRENCY = "KWD"
CURRENCY_DECIMALS = 3

LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
# Member photos and signatures: outside MEDIA_ROOT, so the web server never publishes them (ISO 27001 A.8.3).
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))

ADMIN_URL = env("ADMIN_URL", default="admin/")

# ---------------------------------------------------------------------------
# Website CMS (Wagtail)
# ---------------------------------------------------------------------------
WAGTAIL_SITE_NAME = "Elite Academy"
WAGTAILADMIN_BASE_URL = env("SITE_BASE_URL", default="http://localhost:8000")
WAGTAIL_I18N_ENABLED = False  # one page tree; every block carries its own English and Arabic fields
WAGTAILIMAGES_MAX_UPLOAD_SIZE = 15 * 1024 * 1024
WAGTAILIMAGES_EXTENSIONS = ["jpg", "jpeg", "png", "webp", "avif"]
WAGTAILDOCS_EXTENSIONS = ["pdf"]
WAGTAIL_ENABLE_UPDATE_CHECK = False
WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.database"}}
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# Outgoing messages (WhatsApp / SMS). "console" logs messages instead of sending — the
# provider is chosen before launch (scope decision 6).
MESSAGING_BACKEND = env("MESSAGING_BACKEND", default="console")
# Online payments (KNET, Visa/Mastercard). "test" simulates the payment page — the
# provider is chosen before launch (scope decision 5).
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", default="test")
PORTAL_OTP_TTL_SECONDS = 300
PORTAL_OTP_MAX_ATTEMPTS = 5

# ---------------------------------------------------------------------------
# Background jobs (reminders, scheduled reports)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    # 06:00 Kuwait time: prices, sessions four weeks ahead, renewal reminders (scope M1, M4, M6)
    "daily-jobs": {"task": "apps.classes.tasks.daily_jobs", "schedule": crontab(hour=6, minute=0)},
    "hourly-no-shows": {"task": "apps.classes.tasks.hourly_jobs", "schedule": crontab(minute=5)},
    # Phase 2 (M9, M10, M20): CEO escalations and complaint replies, emailed reports, leavers, documents
    "p2-hourly": {"task": "apps.reports.tasks.hourly_jobs", "schedule": crontab(minute=15)},
    "p2-daily": {"task": "apps.reports.tasks.daily_jobs", "schedule": crontab(hour=6, minute=30)},
    "p2-active-members-snapshot": {
        "task": "apps.reports.tasks.friday_snapshot",
        "schedule": crontab(hour=23, minute=30, day_of_week="fri"),
    },
    "p2-weekly-reports-due": {
        "task": "apps.reports.tasks.weekly_reports_due",
        "schedule": crontab(hour=9, minute=0, day_of_week="sat"),
    },
}

# Email (receipts, scheduled reports). Development prints emails to the console.
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Elite Academy <no-reply@elitemaacademy.com>")

# ---------------------------------------------------------------------------
# Logging — security events go to their own logger (A.8.15)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "elite.security": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "axes": {"handlers": ["console"], "level": "WARNING"},
    },
}
