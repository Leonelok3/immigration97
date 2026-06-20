from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from profiles.models import Category, Profile, ProfileSkill, Skill


CATEGORIES = [
    "Administration & Secrétariat",
    "Agriculture & Agroalimentaire",
    "Aide-soignant & Santé",
    "BTP & Construction",
    "Chauffeur & Logistique",
    "Commerce & Vente",
    "Comptabilité & Finance",
    "Cuisine & Restauration",
    "Développement Web & IT",
    "Électricité & Maintenance",
    "Enseignement & Formation",
    "Hôtellerie & Service client",
    "Marketing digital & Communication",
    "Mécanique auto & Engins",
    "Menuiserie & Ameublement",
    "Nettoyage & Entretien",
    "Plomberie & Froid",
    "Sécurité & Gardiennage",
    "Soudure & Métallerie",
    "Transport maritime & Portuaire",
]

SKILLS = [
    "Accueil client",
    "Administration",
    "Agriculture maraîchère",
    "Béton armé",
    "Bureautique",
    "Carrelage",
    "Chaudronnerie",
    "Conduite poids lourd",
    "Cuisine collective",
    "Django",
    "Électricité bâtiment",
    "Excel",
    "Gestion de caisse",
    "Gestion de stock",
    "Hygiène hospitalière",
    "Maintenance industrielle",
    "Marketing Facebook",
    "Menuiserie bois",
    "Microsoft Office",
    "Peinture bâtiment",
    "Plomberie sanitaire",
    "Prospection commerciale",
    "Python",
    "Réception hôtel",
    "Relation client",
    "Sécurité incendie",
    "Soins aux personnes âgées",
    "Soudure MIG/MAG",
    "WordPress",
]

DEMO_PROFILES = [
    {
        "username": "demo_marius_btp",
        "first_name": "Marius",
        "last_name": "Ngono",
        "email": "marius.btp@example.com",
        "category": "BTP & Construction",
        "headline": "Maçon coffreur • 6 ans d'expérience",
        "location": "Douala, Cameroun",
        "level": "B1",
        "bio": "Maçon coffreur habitué aux chantiers de logements, fondations, ferraillage et coulage béton. Disponible pour projets BTP au Canada, en Europe ou en Afrique centrale.",
        "skills": ["Béton armé", "Carrelage", "Peinture bâtiment"],
    },
    {
        "username": "demo_aicha_sante",
        "first_name": "Aicha",
        "last_name": "Diallo",
        "email": "aicha.sante@example.com",
        "category": "Aide-soignant & Santé",
        "headline": "Aide-soignante • soins aux personnes âgées",
        "location": "Dakar, Sénégal",
        "level": "B2",
        "bio": "Profil santé orienté accompagnement, hygiène, suivi quotidien et assistance aux personnes âgées. Sérieuse, ponctuelle et ouverte à la mobilité internationale.",
        "skills": ["Soins aux personnes âgées", "Hygiène hospitalière", "Relation client"],
    },
    {
        "username": "demo_joel_it",
        "first_name": "Joel",
        "last_name": "Kouassi",
        "email": "joel.it@example.com",
        "category": "Développement Web & IT",
        "headline": "Développeur web Python/Django",
        "location": "Abidjan, Côte d'Ivoire",
        "level": "B2",
        "bio": "Développeur junior avec projets Django, WordPress et automatisation. Recherche opportunités remote ou mobilité professionnelle.",
        "skills": ["Python", "Django", "WordPress"],
    },
    {
        "username": "demo_angele_hotel",
        "first_name": "Angele",
        "last_name": "Tchoumi",
        "email": "angele.hotel@example.com",
        "category": "Hôtellerie & Service client",
        "headline": "Réceptionniste bilingue • hôtel & service client",
        "location": "Yaoundé, Cameroun",
        "level": "B2",
        "bio": "Réception, accueil, réservations, gestion des clients et résolution rapide des demandes. Bonne présentation et sens du service.",
        "skills": ["Réception hôtel", "Accueil client", "Relation client"],
    },
    {
        "username": "demo_ibrahim_logistique",
        "first_name": "Ibrahim",
        "last_name": "Traoré",
        "email": "ibrahim.logistique@example.com",
        "category": "Chauffeur & Logistique",
        "headline": "Chauffeur livreur • logistique & stock",
        "location": "Bamako, Mali",
        "level": "A2",
        "bio": "Chauffeur livreur expérimenté en tournée urbaine, suivi de colis, gestion de stock et respect des délais.",
        "skills": ["Conduite poids lourd", "Gestion de stock", "Relation client"],
    },
    {
        "username": "demo_sandra_finance",
        "first_name": "Sandra",
        "last_name": "Mbarga",
        "email": "sandra.finance@example.com",
        "category": "Comptabilité & Finance",
        "headline": "Assistante comptable • Excel & caisse",
        "location": "Libreville, Gabon",
        "level": "B1",
        "bio": "Assistante comptable avec expérience en saisie, caisse, suivi factures et tableaux Excel. Rigoureuse et organisée.",
        "skills": ["Excel", "Gestion de caisse", "Administration"],
    },
]


class Command(BaseCommand):
    help = "Ajoute les métiers/catégories, compétences et profils candidats de démonstration."

    def handle(self, *args, **options):
        created_categories = 0
        for name in CATEGORIES:
            _, created = Category.objects.get_or_create(
                slug=slugify(name),
                defaults={"name": name},
            )
            created_categories += int(created)

        created_skills = 0
        for name in SKILLS:
            _, created = Skill.objects.get_or_create(name=name)
            created_skills += int(created)

        created_profiles = 0
        for item in DEMO_PROFILES:
            user, user_created = User.objects.get_or_create(
                username=item["username"],
                defaults={
                    "email": item["email"],
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "is_active": True,
                },
            )
            if user_created:
                user.set_password("DemoImmigration97!")
                user.save(update_fields=["password"])

            category = Category.objects.get(slug=slugify(item["category"]))
            profile, profile_created = Profile.objects.update_or_create(
                user=user,
                defaults={
                    "category": category,
                    "headline": item["headline"],
                    "location": item["location"],
                    "level": item["level"],
                    "bio": item["bio"],
                    "is_public": True,
                },
            )
            created_profiles += int(profile_created)

            for index, skill_name in enumerate(item["skills"], start=1):
                skill = Skill.objects.get(name=skill_name)
                ProfileSkill.objects.update_or_create(
                    profile=profile,
                    skill=skill,
                    defaults={"level": max(3, 6 - index), "years": 2 + index},
                )

        self.stdout.write(self.style.SUCCESS(
            f"Marketplace profils prêt: {created_categories} catégories, "
            f"{created_skills} compétences, {created_profiles} profils créés."
        ))
