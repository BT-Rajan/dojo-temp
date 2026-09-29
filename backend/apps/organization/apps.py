from django.apps import AppConfig


class OrganizationConfig(AppConfig):
    name = "apps.organization"
    label = "organization"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Branch, Discipline, PriceChange, PricingOption, Program, Room

        for model in (Branch, Discipline, Program, PricingOption, PriceChange, Room):
            track_changes(model)
