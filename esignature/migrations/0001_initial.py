from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContractDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("original_file", models.FileField(upload_to="esignature/contracts/%Y/%m/%d")),
                ("signed_file", models.FileField(blank=True, null=True, upload_to="esignature/signed/%Y/%m/%d")),
                ("created_at", models.DateTimeField(default=models.functions.Now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_signed", models.BooleanField(default=False)),
                ("is_locked", models.BooleanField(default=False)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="esignature_contracts",
                        to="auth.user",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SigningRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("recipient_email", models.EmailField(max_length=254)),
                ("token", models.CharField(editable=False, max_length=128, unique=True)),
                ("is_completed", models.BooleanField(default=False)),
                ("is_expired", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=models.functions.Now)),
                ("expires_at", models.DateTimeField()),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signing_requests",
                        to="esignature.contractdocument",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="SignatureEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("full_name", models.CharField(max_length=255)),
                ("signature_data", models.TextField()),
                ("signed_at", models.DateTimeField(default=models.functions.Now)),
                ("ip_address", models.GenericIPAddressField()),
                ("user_agent", models.TextField()),
                ("audit_log", models.JSONField(default=dict)),
                (
                    "signing_request",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="signature_event",
                        to="esignature.signingrequest",
                    ),
                ),
            ],
            options={"ordering": ["-signed_at"]},
        ),
    ]
