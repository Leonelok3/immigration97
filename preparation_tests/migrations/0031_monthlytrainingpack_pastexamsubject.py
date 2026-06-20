from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("preparation_tests", "0030_detailederror"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonthlyTrainingPack",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(choices=[("fr", "Français"), ("de", "Allemand"), ("en", "Anglais")], db_index=True, default="fr", max_length=5)),
                ("section", models.CharField(choices=[("co", "Compréhension Orale"), ("ce", "Compréhension Écrite"), ("eo", "Expression Orale"), ("ee", "Expression Écrite")], db_index=True, max_length=2)),
                ("level", models.CharField(choices=[("A1", "A1"), ("A2", "A2"), ("B1", "B1"), ("B2", "B2"), ("C1", "C1"), ("C2", "C2")], db_index=True, default="B1", max_length=2)),
                ("exam_code", models.CharField(choices=[("cecr", "CECR"), ("tef", "TEF Canada"), ("tcf", "TCF Canada"), ("delf", "DELF"), ("dalf", "DALF")], db_index=True, default="cecr", max_length=10)),
                ("month", models.DateField(db_index=True)),
                ("title", models.CharField(max_length=220)),
                ("slug", models.SlugField(unique=True)),
                ("subtitle", models.CharField(blank=True, max_length=300)),
                ("objective", models.TextField(blank=True)),
                ("lesson_html", models.TextField(blank=True)),
                ("correction_html", models.TextField(blank=True)),
                ("recurring_theme", models.CharField(blank=True, max_length=220)),
                ("is_premium", models.BooleanField(default=False)),
                ("is_published", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("exercises", models.ManyToManyField(blank=True, related_name="monthly_packs", to="preparation_tests.courseexercise")),
                ("related_lesson", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="monthly_packs", to="preparation_tests.courselesson")),
            ],
            options={
                "verbose_name": "Pack mensuel",
                "verbose_name_plural": "Packs mensuels",
                "ordering": ["-month", "order", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PastExamSubject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("language", models.CharField(choices=[("fr", "Français"), ("de", "Allemand"), ("en", "Anglais")], db_index=True, default="fr", max_length=5)),
                ("exam_code", models.CharField(choices=[("cecr", "CECR"), ("tef", "TEF Canada"), ("tcf", "TCF Canada"), ("delf", "DELF"), ("dalf", "DALF")], db_index=True, max_length=10)),
                ("section", models.CharField(choices=[("co", "Compréhension Orale"), ("ce", "Compréhension Écrite"), ("eo", "Expression Orale"), ("ee", "Expression Écrite")], db_index=True, max_length=2)),
                ("level", models.CharField(choices=[("A1", "A1"), ("A2", "A2"), ("B1", "B1"), ("B2", "B2"), ("C1", "C1"), ("C2", "C2")], db_index=True, default="B1", max_length=2)),
                ("title", models.CharField(max_length=220)),
                ("slug", models.SlugField(unique=True)),
                ("source_label", models.CharField(blank=True, help_text="Ex: TEF Canada 2024, DELF B2 session exemple", max_length=160)),
                ("recurring_theme", models.CharField(blank=True, max_length=220)),
                ("frequency_score", models.PositiveIntegerField(default=50, help_text="0-100 : probabilité/récurrence du thème")),
                ("subject_html", models.TextField(blank=True)),
                ("correction_html", models.TextField(blank=True)),
                ("pdf_subject", models.FileField(blank=True, null=True, upload_to="past_exam_subjects/subjects/")),
                ("pdf_correction", models.FileField(blank=True, null=True, upload_to="past_exam_subjects/corrections/")),
                ("is_premium", models.BooleanField(default=True)),
                ("is_published", models.BooleanField(default=True)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("exercises", models.ManyToManyField(blank=True, related_name="past_exam_subjects", to="preparation_tests.courseexercise")),
                ("related_lesson", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="past_exam_subjects", to="preparation_tests.courselesson")),
            ],
            options={
                "verbose_name": "Ancien sujet d'examen",
                "verbose_name_plural": "Anciens sujets d'examen",
                "ordering": ["-frequency_score", "order", "-created_at"],
            },
        ),
    ]
