from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_protect_append_only_records"),
        ("operations", "0002_queueticket_late_by_minutes_queueticket_was_late"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="appointment",
            constraint=models.UniqueConstraint(
                fields=("patient", "start_at"),
                condition=Q(status="confirmed"),
                name="unique_patient_confirmed_start",
            ),
        ),
        migrations.RunSQL(
            """
            CREATE TRIGGER protect_operations_appointmenthistory_append_only
            BEFORE UPDATE OR DELETE ON operations_appointmenthistory
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();

            CREATE TRIGGER protect_operations_queueevent_append_only
            BEFORE UPDATE OR DELETE ON operations_queueevent
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();

            CREATE TRIGGER protect_operations_queueestimaterecord_append_only
            BEFORE UPDATE OR DELETE ON operations_queueestimaterecord
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();

            CREATE TRIGGER protect_operations_paymenthistory_append_only
            BEFORE UPDATE OR DELETE ON operations_paymenthistory
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();
            """,
            """
            DROP TRIGGER IF EXISTS protect_operations_paymenthistory_append_only ON operations_paymenthistory;
            DROP TRIGGER IF EXISTS protect_operations_queueestimaterecord_append_only ON operations_queueestimaterecord;
            DROP TRIGGER IF EXISTS protect_operations_queueevent_append_only ON operations_queueevent;
            DROP TRIGGER IF EXISTS protect_operations_appointmenthistory_append_only ON operations_appointmenthistory;
            """,
        ),
    ]
