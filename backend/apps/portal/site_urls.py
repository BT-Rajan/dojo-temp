from django.urls import path

from . import site_views

urlpatterns = [
    path("", site_views.account, name="portal-account"),
    path("<int:pk>/", site_views.member_page, name="portal-member"),
    path("<int:pk>/renew/", site_views.renew, name="portal-renew"),
    path("renewal/<str:reference>/", site_views.renew_return, name="portal-renew-return"),
]
