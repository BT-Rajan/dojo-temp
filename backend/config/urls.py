from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView

from apps.core.views import healthz

api_v1 = [
    path("auth/", include("apps.accounts.urls")),
    path("rbac/", include("apps.rbac.urls")),
    path("audit/", include("apps.audit.urls")),
    path("", include("apps.organization.urls")),
    path("", include("apps.staff.urls")),
    path("", include("apps.members.urls")),
    path("portal/", include("apps.portal.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("api/v1/", include(api_v1)),
    path(settings.ADMIN_URL, admin.site.urls),
]
