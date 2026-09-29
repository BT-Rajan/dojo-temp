from django.apps import AppConfig


class StaffConfig(AppConfig):
    name = "apps.staff"
    label = "staff"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import StaffDocument, StaffProfile

        track_changes(StaffProfile)
        track_changes(StaffDocument)
