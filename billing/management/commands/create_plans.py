# billing/management/commands/create_plans.py
from django.core.management.base import BaseCommand
from billing.models import SubscriptionPlan


class Command(BaseCommand):
    help = "Crée / met à jour les plans d'abonnement Immigration97"

    def handle(self, *args, **options):
        plans_data = [
            # ── PLANS CANDIDATS ──────────────────────────────────────
            {
                "name": "Premium Mensuel",
                "slug": "premium-mensuel",
                "description": "Accès complet à tous les outils Immigration97 pendant 30 jours.",
                "duration_days": 30,
                "price_usd": "15.00",
                "price_xaf": 9500,
                "is_popular": True,
                "order": 1,
                "plan_type": "candidate",
                "features": [
                    "Job Agent : offres accessibles aux étrangers et alertes utiles",
                    "Bourses d'études vérifiées avec liens officiels",
                    "Examens blancs TEF, TCF, IELTS, DELF, DALF",
                    "Génération et export CV international ATS",
                    "Lettres de motivation, emails et dossiers IA",
                    "Guides, vidéos et ressources premium ajoutés depuis l'admin",
                    "Plans visa, études, travail et immigration personnalisés",
                    "Support prioritaire WhatsApp",
                ],
            },
            {
                "name": "Premium Plus — Accompagnement",
                "slug": "premium-plus-annuel",
                "description": "Accès complet + accompagnement personnalisé dans toute votre procédure d'immigration.",
                "duration_days": 365,
                "price_usd": "200.00",
                "price_xaf": 130000,
                "is_popular": False,
                "order": 2,
                "plan_type": "candidate",
                "features": [
                    "Tout du plan Premium Mensuel (1 an)",
                    "Suivi personnalisé de votre dossier immigration",
                    "Consultations mensuelles avec un conseiller",
                    "Vérification de vos documents officiels",
                    "Préparation aux entretiens consulaires",
                    "Alertes et mises à jour réglementaires",
                    "Accès VIP aux nouvelles fonctionnalités",
                    "Garantie satisfaction ou remboursé",
                ],
            },
            # ── PLAN RECRUTEUR ───────────────────────────────────────
            {
                "name": "Recruteur Annuel",
                "slug": "recruteur-annuel",
                "description": "Accès annuel pour les entreprises souhaitant recruter des profils africains qualifiés.",
                "duration_days": 365,
                "price_usd": "100.00",
                "price_xaf": 65000,
                "is_popular": False,
                "order": 10,
                "plan_type": "recruiter",
                "features": [
                    "Accès illimité aux profils candidats publics",
                    "Envoi d'invitations aux candidats",
                    "Messagerie interne avec les candidats acceptés",
                    "Liste de favoris illimitée",
                    "Tableau de bord analytics recruteur",
                    "Filtres avancés : secteur, niveau, localisation",
                    "Badge entreprise vérifiée",
                    "Support dédié recruteurs",
                ],
            },
        ]

        # Désactiver les anciens plans obsolètes
        old_slugs = ["decouverte-24h", "hebdo-7j", "mensuel-30j", "annuel-365j", "month"]
        SubscriptionPlan.objects.filter(slug__in=old_slugs).update(is_active=False)
        self.stdout.write(self.style.WARNING("Anciens plans desactives."))

        for plan_data in plans_data:
            plan, created = SubscriptionPlan.objects.update_or_create(
                slug=plan_data["slug"],
                defaults=plan_data,
            )
            action = "créé" if created else "mis à jour"
            self.stdout.write(self.style.SUCCESS(f"Plan '{plan.name}' {action}"))

        self.stdout.write(self.style.SUCCESS(f"\n{len(plans_data)} plans configures."))
