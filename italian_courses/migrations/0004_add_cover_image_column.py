from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("italian_courses", "0003_alter_lesson_cover_image"),
    ]

    operations = [
        migrations.RunSQL(sql=migrations.RunSQL.noop, reverse_sql=migrations.RunSQL.noop)
    ]
