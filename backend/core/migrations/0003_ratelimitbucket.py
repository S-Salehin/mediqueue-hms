from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0002_protect_append_only_records")]

    operations = [
        migrations.CreateModel(
            name="RateLimitBucket",
            fields=[
                ("key_digest", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("scope", models.CharField(max_length=40)),
                ("request_count", models.PositiveIntegerField(default=0)),
                ("expires_at", models.DateTimeField(db_index=True)),
            ],
            options={
                "indexes": [models.Index(fields=["scope", "expires_at"], name="core_rateli_scope_e2bbf3_idx")],
            },
        ),
    ]
