from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_seed_home_slides"),
    ]

    operations = [
        migrations.CreateModel(
            name="ImmigrationAlertSubscriber",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Email")),
                ("whatsapp", models.CharField(blank=True, max_length=40, verbose_name="WhatsApp")),
                ("country", models.CharField(blank=True, max_length=80, verbose_name="Pays visé")),
                (
                    "project_type",
                    models.CharField(
                        choices=[
                            ("study", "Visa études"),
                            ("work", "Travail"),
                            ("scholarship", "Bourses"),
                            ("language", "Tests de langue"),
                            ("documents", "Documents"),
                            ("news", "Actualités immigration"),
                        ],
                        db_index=True,
                        default="news",
                        max_length=30,
                        verbose_name="Projet",
                    ),
                ),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("email", "Email"),
                            ("whatsapp", "WhatsApp"),
                            ("both", "Email + WhatsApp"),
                        ],
                        default="email",
                        max_length=20,
                        verbose_name="Canal",
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Actif")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Abonné alerte immigration",
                "verbose_name_plural": "Abonnés alertes immigration",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="immigrationalertsubscriber",
            constraint=models.UniqueConstraint(
                fields=("email", "whatsapp", "project_type", "country"),
                name="uniq_core_alert_subscriber_contact_project_country",
            ),
        ),
    ]
