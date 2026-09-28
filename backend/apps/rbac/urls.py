from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("permissions", views.PermissionViewSet, basename="rbac-permission")
router.register("roles", views.RoleViewSet, basename="rbac-role")
router.register("assignments", views.RoleAssignmentViewSet, basename="rbac-assignment")

urlpatterns = router.urls
