from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from apps.core.views import healthz
from apps.website.saqr import SaqrView
from apps.website.views import robots_txt, test_payment

api_v1 = [
    path("auth/", include("apps.accounts.urls")),
    path("rbac/", include("apps.rbac.urls")),
    path("audit/", include("apps.audit.urls")),
    path("", include("apps.organization.urls")),
    path("", include("apps.staff.urls")),
    path("", include("apps.members.urls")),
    path("portal/", include("apps.portal.urls")),
    path("website/", include("apps.website.urls")),
    path("", include("apps.classes.urls")),
    path("", include("apps.sales.urls")),
    path("saqr/", SaqrView.as_view(), name="saqr"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
]

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("robots.txt", robots_txt),
    path("api/v1/", include(api_v1)),
    path(settings.ADMIN_URL, admin.site.urls),
    path("cms/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("pay/test/<str:reference>/", test_payment, name="shop-test-payment"),
    path("", RedirectView.as_view(url="/en/", permanent=False)),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# The public website: /en/… and /ar/… (the last pattern catches every CMS page).
urlpatterns += i18n_patterns(
    path("desk/", include("apps.desk.urls")),  # the staff desk (Phase 1), in English and Arabic
    path("", include(wagtail_urls)),
    prefix_default_language=True,
)
