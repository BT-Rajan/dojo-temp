from django.apps import AppConfig


class MindbodyConfig(AppConfig):
    name = "apps.mindbody"
    label = "mindbody"
    verbose_name = "Mindbody migration"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import CutoverStep, ImportBatch, OptionMap, ParallelRunCheck

        for model in (ImportBatch, OptionMap, ParallelRunCheck, CutoverStep):
            track_changes(model)
