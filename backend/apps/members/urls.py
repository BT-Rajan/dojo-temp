from rest_framework.routers import DefaultRouter

from .views import GuardianViewSet, MemberViewSet

router = DefaultRouter()
router.register("members", MemberViewSet, basename="member")
router.register("guardians", GuardianViewSet, basename="guardian")

urlpatterns = router.urls
