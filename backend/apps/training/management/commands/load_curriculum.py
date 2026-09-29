from django.core.management.base import BaseCommand

from apps.training.curriculum import load_curriculum


class Command(BaseCommand):
    help = "Load the Kajukenbo curriculum and the other arts' belt lists (safe to run again)."

    def handle(self, *args, **opts):
        made = load_curriculum()
        self.stdout.write(self.style.SUCCESS(f"Curriculum loaded: {made}"))
