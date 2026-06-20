from django.db import migrations


SLIDES = [
    {
        "order": 1,
        "theme": "gold",
        "kicker": "Immigration assistée par IA",
        "title_before": "Votre projet d'immigration|devient un plan clair",
        "title_accent": "avec Immigration97",
        "subtitle": (
            "Études, travail, résidence permanente, CV et tests de langue : "
            "Immigration97 transforme votre objectif en étapes concrètes, "
            "priorisées et prêtes à exécuter."
        ),
        "primary_label": "Évaluer mon projet",
        "primary_url": "/billing/access/",
        "secondary_label": "Parler à un conseiller",
        "secondary_url": "/consultation/",
    },
    {
        "order": 2,
        "theme": "blue",
        "kicker": "Visa étudiant • Admissions • Bourses",
        "title_before": "Décrochez votre visa étudiant|et partez",
        "title_accent": "construire votre avenir",
        "subtitle": (
            "France, Canada, Allemagne, Belgique : préparez votre profil étudiant, "
            "vos preuves financières, vos lettres et votre plan d'action sans vous perdre."
        ),
        "primary_label": "Préparer mon visa étudiant",
        "primary_url": "/visa-etudes/",
        "secondary_label": "Voir les pays adaptés",
        "secondary_url": "/visa-etudes/pays/",
    },
    {
        "order": 3,
        "theme": "purple",
        "kicker": "CV adapté • Lettres • Offres",
        "title_before": "Postulez plus vite|avec un dossier",
        "title_accent": "adapté à chaque offre",
        "subtitle": (
            "Repérez les offres liées à votre profil, adaptez votre CV, votre lettre "
            "et votre email de candidature, puis postulez avec plus de confiance."
        ),
        "primary_label": "Créer mon profil candidat",
        "primary_url": "/profiles/me/",
        "secondary_label": "Voir les talents",
        "secondary_url": "/profiles/",
    },
    {
        "order": 4,
        "theme": "green",
        "kicker": "Canada • Résidence permanente",
        "title_before": "Découvrez vos chances|et votre stratégie",
        "title_accent": "pour immigrer au Canada",
        "subtitle": (
            "Analysez votre admissibilité, identifiez les risques de votre dossier "
            "et recevez une feuille de route claire pour avancer vers la résidence permanente."
        ),
        "primary_label": "Obtenir mon diagnostic",
        "primary_url": "/pr/eligibilite/",
        "secondary_label": "Voir les programmes",
        "secondary_url": "/pr/programmes/",
    },
    {
        "order": 5,
        "theme": "orange",
        "kicker": "Guides PDF • Checklists • Modèles",
        "title_before": "Préparez vos documents|comme un candidat",
        "title_accent": "organisé et crédible",
        "subtitle": (
            "Téléchargez les guides, checklists, modèles de lettres et ressources "
            "qui vous aident à construire un dossier propre, cohérent et professionnel."
        ),
        "primary_label": "Voir les guides",
        "primary_url": "/ressources/",
        "secondary_label": "Commencer les tests",
        "secondary_url": "/prep/",
    },
]


def seed_home_slides(apps, schema_editor):
    HomeSlide = apps.get_model("core", "HomeSlide")
    for item in SLIDES:
        HomeSlide.objects.update_or_create(
            order=item["order"],
            defaults={**item, "is_active": True},
        )


def unseed_home_slides(apps, schema_editor):
    HomeSlide = apps.get_model("core", "HomeSlide")
    HomeSlide.objects.filter(order__in=[item["order"] for item in SLIDES]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_homeslide"),
    ]

    operations = [
        migrations.RunPython(seed_home_slides, unseed_home_slides),
    ]
