import time

from django.conf import settings
from django.core.management.base import BaseCommand

from communications.services import process_one_outbox
from core.retention import cleanup_expired_control_records


class Command(BaseCommand):
    help = "Deliver committed email outbox items."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="Keep polling for new work.")
        parser.add_argument("--once", action="store_true", help="Process available work and exit. This is the default.")

    def handle(self, *args, **options):
        last_cleanup_at = 0.0
        while True:
            monotonic_now = time.monotonic()
            if monotonic_now - last_cleanup_at >= 3600:
                cleanup_expired_control_records()
                last_cleanup_at = monotonic_now
            processed = process_one_outbox()
            if not options["loop"]:
                if not processed:
                    break
                continue
            if not processed:
                time.sleep(settings.OUTBOX_POLL_SECONDS)
