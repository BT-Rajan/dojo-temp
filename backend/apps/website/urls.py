from rest_framework.routers import DefaultRouter

from .api import ContactMessageViewSet, TrialRequestViewSet

router = DefaultRouter()
router.register("trial-requests", TrialRequestViewSet, basename="trial-request")
router.register("contact-messages", ContactMessageViewSet, basename="contact-message")

urlpatterns = router.urls
