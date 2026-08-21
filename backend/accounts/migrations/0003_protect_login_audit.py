from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_failed_login_count_user_locked_until"),
        ("core", "0002_protect_append_only_records"),
    ]

    operations = [
        migrations.RunSQL(
            """
            CREATE TRIGGER protect_accounts_loginaudit_append_only
            BEFORE UPDATE OR DELETE ON accounts_loginaudit
            FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();
            """,
            "DROP TRIGGER IF EXISTS protect_accounts_loginaudit_append_only ON accounts_loginaudit;",
        ),
    ]
