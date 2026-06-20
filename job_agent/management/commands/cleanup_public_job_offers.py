from django.core.management.base import BaseCommand

from job_agent.models import PublicJobOffer
from outreach.ai_employer_scraper import is_direct_application_url


class Command(BaseCommand):
    help = "Désactive les offres publiques qui ne pointent pas vers une vraie page d'offre/candidature."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Afficher seulement les offres à désactiver.")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        disabled = 0
        kept = 0

        for offer in PublicJobOffer.objects.filter(is_active=True).order_by("-created_at"):
            if is_direct_application_url(offer.url):
                kept += 1
                continue

            disabled += 1
            self.stdout.write(f"Désactivation: #{offer.id} {offer.title} -> {offer.url}")
            if not dry_run:
                offer.is_active = False
                offer.save(update_fields=["is_active", "updated_at"])

        action = "seraient désactivées" if dry_run else "désactivées"
        self.stdout.write(self.style.SUCCESS(f"Nettoyage terminé: {disabled} offres {action}, {kept} gardées."))
