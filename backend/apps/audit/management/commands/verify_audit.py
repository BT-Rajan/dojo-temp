from django.core.management.base import BaseCommand, CommandError

from apps.audit.chain import seal_pending, verify_chain


class Command(BaseCommand):
    help = "Seal pending audit events, then verify the whole hash chain."

    def handle(self, *args, **opts):
        sealed = seal_pending(batch_size=100000)
        result = verify_chain()
        if not result["ok"]:
            raise CommandError(f"Audit chain BROKEN after {result['checked']} events: {result['problem']}")
        self.stdout.write(self.style.SUCCESS(f"Sealed {sealed} new events. Chain OK: {result['checked']} events."))
