from django.apps import AppConfig


class WebsiteConfig(AppConfig):
    name = "apps.website"
    label = "website"
    verbose_name = "Website"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import ContactMessage, TrialRequest

        for model in (TrialRequest, ContactMessage):
            track_changes(model)
