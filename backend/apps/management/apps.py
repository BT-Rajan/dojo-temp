from django.apps import AppConfig


class ManagementConfig(AppConfig):
    name = "apps.management"
    label = "management"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Escalation, Handoff, Meeting, Procedure, ProcedureVersion, QuarterlyReport

        for model in (Escalation, Handoff, Meeting, Procedure, ProcedureVersion, QuarterlyReport):
            track_changes(model)
