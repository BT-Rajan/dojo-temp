import time

from django.conf import settings
from django.contrib.auth import logout

from .context import RequestContext, new_request_id, reset_context, set_context


def client_ip(request) -> str | None:
    # Behind a trusted reverse proxy the real client is the first X-Forwarded-For entry.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


class RequestContextMiddleware:
    """Records who is making each request so every change can be attributed (ISO 27001 A.8.15)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-ID") or new_request_id()
        user = getattr(request, "user", None)
        ctx = RequestContext(
            user_id=user.pk if user is not None and user.is_authenticated else None,
            ip_address=client_ip(request),
            user_agent=request.headers.get("User-Agent", "")[:255],
            request_id=request.request_id,
        )
        token = set_context(ctx)
        try:
            response = self.get_response(request)
            self._flush_security_events(request)
        finally:
            reset_context(token)
        response["X-Request-ID"] = request.request_id
        return response

    @staticmethod
    def _flush_security_events(request):
        # Runs after the view's transaction has committed or rolled back, so these always persist.
        events = getattr(request, "_security_events", None)
        if not events:
            return
        from apps.audit.services import record_event

        for event in events:
            record_event(**event)


class IdleSessionTimeoutMiddleware:
    """Logs a user out after a period of inactivity (ISO 27001 A.8.5)."""

    session_key = "_last_activity"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = int(time.time())
            last = request.session.get(self.session_key)
            if last is not None and now - last > settings.SESSION_IDLE_TIMEOUT_SECONDS:
                logout(request)
            else:
                request.session[self.session_key] = now
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Adds headers that Django does not set by default (ISO 27001 A.8.26)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.path.startswith("/api/"):
            # API responses may contain personal data: never cache them in browsers or proxies.
            response["Cache-Control"] = "no-store"
            response.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        return response
