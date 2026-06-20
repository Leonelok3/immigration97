from django.core.management.base import BaseCommand
from django.utils.text import slugify

from job_agent.models import PublicJobOffer
from profiles.models import Category


OFFERS = [
    {
        "category": "Développement Web & IT",
        "title": "Développeur Full Stack Python/Django",
        "company": "Maple Cloud Services",
        "location": "Remote / Canada",
        "source": "Immigration97",
        "url": "https://immigration97.com/offres/demo-fullstack-python-django/",
        "skills": "Python, Django, REST API, PostgreSQL, AWS, HTML, CSS",
        "description": (
            "Entreprise canadienne recherche un développeur full stack capable de créer "
            "des applications web modernes avec Python/Django, APIs REST, PostgreSQL, "
            "HTML/CSS et déploiement cloud. Expérience Git, sécurité, performance et "
            "documentation appréciée. Travail remote possible."
        ),
    },
    {
        "category": "Développement Web & IT",
        "title": "Technicien support web et WordPress",
        "company": "Nord Digital",
        "location": "Montréal, Canada",
        "source": "Immigration97",
        "url": "https://immigration97.com/offres/demo-support-wordpress/",
        "skills": "WordPress, HTML, CSS, support client, hébergement, maintenance",
        "description": (
            "Poste support web pour accompagner des clients sur WordPress, hébergement, "
            "maintenance, corrections HTML/CSS et suivi des tickets. Bonne communication "
            "et sens du service client requis."
        ),
    },
    {
        "category": "Aide-soignant & Santé",
        "title": "Aide-soignant en résidence pour personnes âgées",
        "company": "Résidence Bellevue",
        "location": "Québec, Canada",
        "source": "Immigration97",
        "url": "https://immigration97.com/offres/demo-aide-soignant-residence/",
        "skills": "Soins aux personnes âgées, hygiène hospitalière, accompagnement, empathie",
        "description": (
            "Résidence recherche aide-soignant pour l'accompagnement quotidien de personnes "
            "âgées: hygiène, aide aux repas, mobilité, observation et communication avec "
            "l'équipe médicale. Expérience en soins appréciée."
        ),
    },
    {
        "category": "BTP & Construction",
        "title": "Maçon coffreur bâtiment",
        "company": "Atlas Construction",
        "location": "Lyon, France",
        "source": "Immigration97",
        "url": "https://immigration97.com/offres/demo-macon-coffreur/",
        "skills": "Béton armé, coffrage, ferraillage, lecture de plan, chantier",
        "description": (
            "Entreprise BTP recherche maçon coffreur pour travaux de coffrage, ferraillage, "
            "coulage béton et préparation chantier. Respect des consignes de sécurité exigé."
        ),
    },
    {
        "category": "Hôtellerie & Service client",
        "title": "Réceptionniste hôtel bilingue",
        "company": "Hotel Saint-Laurent",
        "location": "Bruxelles, Belgique",
        "source": "Immigration97",
        "url": "https://immigration97.com/offres/demo-receptionniste-bilingue/",
        "skills": "Accueil client, réservation, relation client, français, anglais",
        "description": (
            "Hôtel recherche réceptionniste pour accueil des clients, gestion des réservations, "
            "check-in/check-out, facturation simple et traitement des demandes. Anglais apprécié."
        ),
    },
    {
        "category": "Comptabilité & Finance",
        "title": "Assistant comptable Excel",
        "company": "Finance Pro Services",
        "location": "Paris, France",
        "source": "Immigration97",
        "url": "https://immigration97.com/offres/demo-assistant-comptable-excel/",
        "skills": "Comptabilité, Excel, facturation, rapprochement bancaire, reporting",
        "description": (
            "Cabinet recherche assistant comptable pour saisie, facturation, rapprochements "
            "bancaires et tableaux de suivi Excel. Rigueur, organisation et confidentialité requises."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed public job offers linked to Immigration97 profile categories."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for item in OFFERS:
            category, _ = Category.objects.get_or_create(
                slug=slugify(item["category"]),
                defaults={"name": item["category"]},
            )
            offer, created = PublicJobOffer.objects.update_or_create(
                url=item["url"],
                defaults={
                    "source": item["source"],
                    "title": item["title"],
                    "company": item["company"],
                    "location": item["location"],
                    "category": category,
                    "skills_keywords": item["skills"],
                    "description_text": item["description"],
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Public job offers ready: {created_count} created, {updated_count} updated."
            )
        )
