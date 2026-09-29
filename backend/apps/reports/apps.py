from django.apps import AppConfig


class ReportsConfig(AppConfig):
    name = "apps.reports"
    label = "reports"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import ReportSubscription, WeeklyReport

        for model in (WeeklyReport, ReportSubscription):
            track_changes(model)
