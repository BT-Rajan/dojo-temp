from django.apps import AppConfig


class AssistantConfig(AppConfig):
    name = "apps.assistant"
    label = "assistant"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Article

        track_changes(Article)
