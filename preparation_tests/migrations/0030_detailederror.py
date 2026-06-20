from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("preparation_tests", "0029_featuredcontent"),
    ]

    operations = [
        migrations.CreateModel(
            name="DetailedError",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("grammar", "Grammaire"), ("lexical", "Lexique"), ("comprehension", "Compréhension"), ("listening", "Écoute"), ("strategy", "Stratégie d'examen"), ("writing", "Expression écrite"), ("speaking", "Expression orale")], db_index=True, default="comprehension", max_length=20)),
                ("source", models.CharField(blank=True, db_index=True, default="lesson", max_length=30)),
                ("selected_answer", models.CharField(blank=True, default="", max_length=10)),
                ("correct_answer", models.CharField(blank=True, default="", max_length=10)),
                ("explanation", models.TextField(blank=True)),
                ("occurrences", models.PositiveIntegerField(default=1)),
                ("status", models.CharField(choices=[("active", "À revoir"), ("resolved", "Maîtrisée")], db_index=True, default="active", max_length=12)),
                ("ease_factor", models.FloatField(default=2.5)),
                ("interval_days", models.PositiveIntegerField(default=1)),
                ("repetitions", models.PositiveIntegerField(default=0)),
                ("lapses", models.PositiveIntegerField(default=0)),
                ("last_reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("next_review_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("exercise", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="detailed_errors", to="preparation_tests.courseexercise")),
                ("lesson", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="detailed_errors", to="preparation_tests.courselesson")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="detailed_errors", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Erreur détaillée",
                "verbose_name_plural": "Erreurs détaillées",
                "ordering": ["next_review_at", "-occurrences", "-updated_at"],
                "unique_together": {("user", "exercise")},
            },
        ),
        migrations.AddIndex(
            model_name="detailederror",
            index=models.Index(fields=["user", "status", "next_review_at"], name="preparation_user_id_45e480_idx"),
        ),
        migrations.AddIndex(
            model_name="detailederror",
            index=models.Index(fields=["user", "category", "status"], name="preparation_user_id_27c770_idx"),
        ),
        migrations.AddIndex(
            model_name="detailederror",
            index=models.Index(fields=["user", "lesson"], name="preparation_user_id_48f30f_idx"),
        ),
    ]
