from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from directory.models import Hospital


class Command(BaseCommand):
    help = "Create the single production hospital configuration before administrator setup."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--short-name")
        parser.add_argument("--code")
        parser.add_argument("--timezone", default="Asia/Dhaka")
        parser.add_argument("--currency", default="BDT")
        parser.add_argument("--email", default="")
        parser.add_argument("--phone", default="")
        parser.add_argument("--address", default="")

    @transaction.atomic
    def handle(self, *args, **options):
        if Hospital.objects.exists():
            raise CommandError("Hospital configuration already exists. Use the protected settings API for later changes.")
        short_name = options.get("short_name") or options.get("code")
        if not short_name:
            raise CommandError("Provide --short-name or --code.")
        hospital = Hospital.objects.create(
            display_name=options["name"],
            short_name=short_name,
            timezone=options["timezone"],
            currency=options["currency"],
            email=options["email"],
            phone=options["phone"],
            address=options["address"],
        )
        try:
            hospital.full_clean()
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Created hospital configuration {hospital.pk}."))
        self.stdout.write(
            "Next: bootstrap an administrator, sign in with MFA, then create and activate the approved privacy notice through /api/v1/admin/privacy-notices/."
        )
