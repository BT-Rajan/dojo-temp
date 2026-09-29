from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("branches", views.BranchViewSet, basename="branch")
router.register("disciplines", views.DisciplineViewSet, basename="discipline")
router.register("programs", views.ProgramViewSet, basename="program")
router.register("pricing-options", views.PricingOptionViewSet, basename="pricing-option")
router.register("price-changes", views.PriceChangeViewSet, basename="price-change")
router.register("rooms", views.RoomViewSet, basename="room")

urlpatterns = router.urls
