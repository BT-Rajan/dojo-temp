from django.core.management.base import BaseCommand

from apps.classes.tasks import daily_jobs


class Command(BaseCommand):
    help = "Apply approved prices, create sessions 4 weeks ahead, send renewal reminders, record no-shows."

    def handle(self, *args, **options):
        self.stdout.write(str(daily_jobs()))
