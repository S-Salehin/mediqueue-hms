from django.db import migrations


CREATE_FUNCTION_AND_TRIGGER = """
CREATE OR REPLACE FUNCTION mediqueue_reject_append_only_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'append-only table % does not permit %', TG_TABLE_NAME, TG_OP
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER protect_core_auditevent_append_only
BEFORE UPDATE OR DELETE ON core_auditevent
FOR EACH ROW EXECUTE FUNCTION mediqueue_reject_append_only_mutation();
"""

DROP_TRIGGER_AND_FUNCTION = """
DROP TRIGGER IF EXISTS protect_core_auditevent_append_only ON core_auditevent;
DROP FUNCTION IF EXISTS mediqueue_reject_append_only_mutation();
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.RunSQL(CREATE_FUNCTION_AND_TRIGGER, DROP_TRIGGER_AND_FUNCTION),
    ]
