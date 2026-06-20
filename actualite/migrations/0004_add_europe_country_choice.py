from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("actualite", "0003_newsitem_is_important_newsitem_is_urgent_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="newsitem",
            name="country_target",
            field=models.CharField(
                choices=[
                    ("US", "USA"),
                    ("CA", "Canada"),
                    ("DE", "Allemagne"),
                    ("EU", "Europe"),
                    ("IT", "Italie"),
                    ("FR", "France"),
                ],
                max_length=2,
            ),
        ),
    ]
