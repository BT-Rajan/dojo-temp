from django.apps import AppConfig


class MembersConfig(AppConfig):
    name = "apps.members"
    label = "members"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import EmergencyContact, Guardian, GuardianLink, Member

        for model in (Member, Guardian, GuardianLink, EmergencyContact):
            track_changes(model)
