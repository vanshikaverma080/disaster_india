from django.db import migrations, models
import uuid

class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="AlertSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("district", models.CharField(blank=True, max_length=160)),
                ("hazards", models.JSONField(default=list)),
                ("threshold", models.FloatField(default=0.75)),
                ("active", models.BooleanField(default=True)),
                ("unsubscribe_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("last_alert_key", models.CharField(blank=True, max_length=255)),
                ("last_alert_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"indexes": [models.Index(fields=["email", "active"], name="core_alertsu_email_9bdb4e_idx")]},
        ),
    ]
