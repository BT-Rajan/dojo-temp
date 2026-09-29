from rest_framework.routers import DefaultRouter

from .api import MembershipViewSet, SaleViewSet

router = DefaultRouter()
router.register("sales", SaleViewSet, basename="sale")
router.register("memberships", MembershipViewSet, basename="membership")
urlpatterns = router.urls
