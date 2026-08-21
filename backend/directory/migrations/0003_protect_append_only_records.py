from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_protect_append_only_records"),
        ("directory", "0002_location_code_location_unique_location_code"),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE TRIGGER protect_directory_privacynotice_append_only
            BEFORE UPDATE OR DELETE ON directory_privacynoticeversion
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();

            CREATE TRIGGER protect_directory_consentrecord_append_only
            BEFORE UPDATE OR DELETE ON directory_consentrecord
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();
            """,
            """
            DROP TRIGGER IF EXISTS protect_directory_consentrecord_append_only ON directory_consentrecord;
            DROP TRIGGER IF EXISTS protect_directory_privacynotice_append_only ON directory_privacynoticeversion;
            """,
        ),
    ]
