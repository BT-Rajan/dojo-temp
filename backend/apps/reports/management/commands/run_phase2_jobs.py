from django.core.management.base import BaseCommand

from apps.reports.tasks import daily_jobs, friday_snapshot, hourly_jobs, weekly_reports_due


class Command(BaseCommand):
    help = "Run the Phase 2 jobs now: escalations, complaint reminders, emailed reports, leavers, documents."

    def add_arguments(self, parser):
        parser.add_argument("--snapshot", action="store_true", help="Also take the active-members snapshot.")
        parser.add_argument("--remind-reports", action="store_true", help="Also send the weekly-report reminders.")

    def handle(self, *args, **opts):
        self.stdout.write(str(hourly_jobs()))
        self.stdout.write(str(daily_jobs()))
        if opts["snapshot"]:
            self.stdout.write(str(friday_snapshot()))
        if opts["remind_reports"]:
            self.stdout.write(str(weekly_reports_due()))
