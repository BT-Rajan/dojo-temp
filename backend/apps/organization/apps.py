from django.apps import AppConfig


class OrganizationConfig(AppConfig):
    name = "apps.organization"
    label = "organization"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Branch, Discipline, PricingOption, Program

        for model in (Branch, Discipline, Program, PricingOption):
            track_changes(model)
