from django.apps import AppConfig


class PayrollConfig(AppConfig):
    name = "apps.payroll"
    label = "payroll"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import (
            Advance,
            Leave,
            PayAdjustment,
            PayComponent,
            PayProfile,
            PayrollRun,
            PayrollSettings,
            PublicHoliday,
        )

        for model in (
            PayrollSettings,
            PublicHoliday,
            PayProfile,
            PayComponent,
            Leave,
            Advance,
            PayAdjustment,
            PayrollRun,
        ):
            track_changes(model)
