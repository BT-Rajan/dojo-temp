from django.apps import AppConfig


class TrainingConfig(AppConfig):
    name = "apps.training"
    label = "training"

    def ready(self):
        from apps.audit.services import track_changes

        from .models import Evaluation, MemberRank, Promotion, Rank, Skill, TestCandidate, TestDay

        for model in (Rank, Skill, MemberRank, Evaluation, TestDay, TestCandidate, Promotion):
            track_changes(model)
