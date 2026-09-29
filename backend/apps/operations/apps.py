from django.apps import AppConfig


class OperationsConfig(AppConfig):
    name = "apps.operations"
    label = "operations"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Complaint, Handover, Incident, ShiftOpening

        for model in (ShiftOpening, Incident, Complaint, Handover):
            track_changes(model)
