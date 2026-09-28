import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions
from rest_framework.views import exception_handler as drf_exception_handler

security_log = logging.getLogger("elite.security")


def exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages)

    response = drf_exception_handler(exc, context)

    if isinstance(exc, (exceptions.PermissionDenied, exceptions.NotAuthenticated)):
        request = context.get("request")
        view = context.get("view")
        # Denied access attempts are security events (ISO 27001 A.8.15, A.8.16).
        # The request's transaction is rolled back on errors, so the event is queued and written by
        # RequestContextMiddleware after the transaction has ended — it is never lost.
        if request is not None:
            django_request = getattr(request, "_request", request)
            events = getattr(django_request, "_security_events", None)
            if events is None:
                events = django_request._security_events = []
            events.append(
                {
                    "action": "access_denied",
                    "object_type": type(view).__name__ if view else "",
                    "changes": {"path": request.path, "method": request.method},
                }
            )
        security_log.warning(
            "access denied path=%s user=%s", request.path if request else "", getattr(request, "user", None)
        )
    return response
