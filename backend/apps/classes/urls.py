from rest_framework.routers import DefaultRouter

from .api import BookingViewSet, CheckInViewSet, SessionViewSet

router = DefaultRouter()
router.register("class-sessions", SessionViewSet, basename="class-session")
router.register("bookings", BookingViewSet, basename="booking")
router.register("check-ins", CheckInViewSet, basename="check-in")
urlpatterns = router.urls
