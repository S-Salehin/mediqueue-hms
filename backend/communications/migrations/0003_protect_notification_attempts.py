from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("communications", "0002_alter_notificationpreference_appointment_email_and_more"),
        ("core", "0002_protect_append_only_records"),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE TRIGGER protect_communications_notificationattempt_append_only
            BEFORE UPDATE OR DELETE ON communications_notificationattempt
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();
            """,
            "DROP TRIGGER IF EXISTS protect_communications_notificationattempt_append_only ON communications_notificationattempt;",
        ),
    ]
