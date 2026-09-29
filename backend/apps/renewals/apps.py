from django.apps import AppConfig


class RenewalsConfig(AppConfig):
    name = "apps.renewals"
    label = "renewals"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import FollowUp, InstructorHandoff

        for model in (FollowUp, InstructorHandoff):
            track_changes(model)
