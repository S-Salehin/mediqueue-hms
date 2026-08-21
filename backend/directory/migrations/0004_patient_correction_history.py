import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("directory", "0003_protect_append_only_records"),
    ]

    operations = [
        migrations.CreateModel(
            name="PatientCorrectionHistory",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "event",
                    models.CharField(
                        choices=[("corrected", "Corrected"), ("deactivated", "Deactivated")],
                        max_length=20,
                    ),
                ),
                ("reason", models.CharField(max_length=500)),
                ("previous_values", models.JSONField(default=dict)),
                ("new_values", models.JSONField(default=dict)),
                ("request_id", models.UUIDField(db_index=True)),
                (
                    "actor",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="correction_history",
                        to="directory.patientprofile",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.RunSQL(
            """
            CREATE TRIGGER protect_directory_patientcorrectionhistory_append_only
            BEFORE UPDATE OR DELETE ON directory_patientcorrectionhistory
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();
            """,
            "DROP TRIGGER IF EXISTS protect_directory_patientcorrectionhistory_append_only ON directory_patientcorrectionhistory;",
        ),
    ]
