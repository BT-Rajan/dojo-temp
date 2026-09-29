from django.apps import AppConfig


class LeadsConfig(AppConfig):
    name = "apps.leads"
    label = "leads"

    def ready(self):
        from django.db.models.signals import post_save

        from apps.audit.services import track_changes
        from apps.members.models import MediaConsent

        from . import services
        from .models import Broadcast, Campaign, GroupDeal, Lead

        for model in (Lead, GroupDeal, Campaign, Broadcast):
            track_changes(model)
        post_save.connect(services.on_media_consent, sender=MediaConsent, dispatch_uid="leads_consent_withdrawn")
