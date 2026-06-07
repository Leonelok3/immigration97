from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.text import slugify


def populate_slugs(apps, schema_editor):
    Resource = apps.get_model("resources", "Resource")
    seen = {}
    for resource in Resource.objects.all():
        base = slugify(resource.title) or f"resource-{resource.pk}"
        slug = base
        n = 1
        while slug in seen:
            slug = f"{base}-{n}"
            n += 1
        seen[slug] = True
        resource.slug = slug
        resource.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("resources", "0002_resource_cover_price"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="resource",
            name="slug",
            field=models.SlugField(blank=True, max_length=255, default="", verbose_name="Slug"),
        ),

        migrations.RunPython(populate_slugs, migrations.RunPython.noop),

        migrations.AlterField(
            model_name="resource",
            name="slug",
            field=models.SlugField(blank=True, max_length=255, unique=True, verbose_name="Slug"),
        ),

        # ── Autres nouveaux champs Resource ──
        migrations.AddField(
            model_name="resource",
            name="long_description",
            field=models.TextField(blank=True, help_text="HTML simple ou markdown. Affiché sur la page produit.", verbose_name="Description longue (page détail)"),
        ),
        migrations.AddField(
            model_name="resource",
            name="what_inside",
            field=models.TextField(blank=True, help_text="Une ligne par point. Ex : ✅ 50 questions d'entraînement", verbose_name="Ce que contient le fichier (bullet points)"),
        ),
        migrations.AddField(
            model_name="resource",
            name="is_featured",
            field=models.BooleanField(default=False, verbose_name="Mis en avant (hero)"),
        ),
        migrations.AddField(
            model_name="resource",
            name="downloads",
            field=models.PositiveIntegerField(default=0, editable=False, verbose_name="Nb téléchargements"),
        ),

        # ── Mise à jour des choices ──
        migrations.AlterField(
            model_name="resource",
            name="category",
            field=models.CharField(
                choices=[
                    ("guides_pdf", "Guides PDF"),
                    ("tableaux_excel", "Tableaux Excel"),
                    ("preparation_tcf", "Préparation TCF/TEF"),
                    ("visa_immigration", "Visa & Immigration"),
                    ("emploi_international", "Emploi International"),
                    ("lettres_modeles", "Lettres & Modèles"),
                    ("formation_langue", "Formation Langue"),
                ],
                max_length=50,
                verbose_name="Catégorie",
            ),
        ),
        migrations.AlterField(
            model_name="resource",
            name="destination",
            field=models.CharField(
                choices=[
                    ("canada", "Canada"),
                    ("france", "France"),
                    ("italie", "Italie"),
                    ("allemagne", "Allemagne"),
                    ("uk", "Royaume-Uni"),
                    ("belgique", "Belgique"),
                    ("espagne", "Espagne"),
                    ("europe", "Europe"),
                    ("japon", "Japon"),
                    ("maroc", "Maroc"),
                    ("international", "International"),
                ],
                default="international",
                max_length=50,
                verbose_name="Destination",
            ),
        ),
        migrations.AlterField(
            model_name="resource",
            name="resource_type",
            field=models.CharField(
                choices=[
                    ("pdf", "PDF"),
                    ("xls", "Excel"),
                    ("doc", "Word"),
                    ("zip", "ZIP"),
                    ("other", "Autre"),
                ],
                default="pdf",
                max_length=10,
                verbose_name="Type de fichier",
            ),
        ),
        migrations.AlterField(
            model_name="resource",
            name="description",
            field=models.TextField(verbose_name="Description courte"),
        ),
        migrations.AlterField(
            model_name="resource",
            name="preview_url",
            field=models.URLField(blank=True, default="", help_text="Lien Google Drive, Canva ou PDF partiel visible avant achat.", verbose_name="Aperçu / extrait (lien externe)"),
        ),
        migrations.AlterField(
            model_name="resource",
            name="is_premium",
            field=models.BooleanField(default=False, help_text="Si coché, les abonnés Premium téléchargent gratuitement.", verbose_name="Inclus abonnement Premium"),
        ),

        # ── Nouveau modèle ResourcePurchase ──
        migrations.CreateModel(
            name="ResourcePurchase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount_paid_xaf", models.PositiveIntegerField(default=0, verbose_name="Montant payé (XAF)")),
                ("payment_method", models.CharField(blank=True, help_text="Ex : Wave, MTN MoMo, Orange Money, PayPal…", max_length=50, verbose_name="Méthode de paiement")),
                ("payment_ref", models.CharField(blank=True, max_length=100, verbose_name="Référence paiement")),
                ("purchased_at", models.DateTimeField(auto_now_add=True, verbose_name="Date d'achat")),
                ("notes", models.TextField(blank=True, verbose_name="Notes admin")),
                ("is_active", models.BooleanField(default=True, help_text="Décocher pour désactiver l'accès (remboursement, etc.)", verbose_name="Accès actif")),
                ("resource", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="purchases", to="resources.resource")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="resource_purchases", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Achat ressource",
                "verbose_name_plural": "Achats ressources",
                "ordering": ["-purchased_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="resourcepurchase",
            constraint=models.UniqueConstraint(fields=["user", "resource"], name="unique_user_resource_purchase"),
        ),
    ]
