from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """Liveness/readiness probe for the load balancer. Reveals no internal details."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:  # noqa: BLE001 - any database failure means "not ready"
        return JsonResponse({"status": "unavailable"}, status=503)
