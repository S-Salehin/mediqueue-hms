from django.core.management.base import BaseCommand

from core.retention import cleanup_expired_control_records


class Command(BaseCommand):
    help = "Remove expired sessions, rate limits, idempotency records, and account tokens."

    def handle(self, *args, **options):
        counts = cleanup_expired_control_records()
        summary = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
        self.stdout.write(self.style.SUCCESS(f"Expired control data removed: {summary}"))
