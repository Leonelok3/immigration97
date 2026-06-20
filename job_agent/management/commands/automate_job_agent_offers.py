from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from job_agent.models import JobLead, PublicJobOffer
from outreach.ai_employer_scraper import is_direct_application_url


class Command(BaseCommand):
    help = "Automatisation Job Agent: publie les offres vérifiées et synchronise les offres utiles vers la vitrine publique."

    def add_arguments(self, parser):
        parser.add_argument("--publish-verified", action="store_true", help="Publier les ScrapedEmployerLead vérifiés.")
        parser.add_argument("--sync-private", action="store_true", help="Publier aussi les JobLead existants dans PublicJobOffer.")
        parser.add_argument("--seed-demo-if-empty", action="store_true", help="Créer des offres de démonstration si la vitrine publique est vide.")
        parser.add_argument("--include-review", action="store_true", help="Inclure les leads vérifiés à revoir.")
        parser.add_argument("--limit", type=int, default=80)

    @transaction.atomic
    def _sync_private_leads(self):
        created = 0
        updated = 0
        skipped = 0

        qs = JobLead.objects.exclude(url="").order_by("-created_at")
        for lead in qs:
            title = (lead.title or "").strip()
            if not title or not is_direct_application_url(lead.url):
                skipped += 1
                continue

            _offer, was_created = PublicJobOffer.objects.update_or_create(
                url=lead.url,
                defaults={
                    "source": lead.source or "Job Agent",
                    "title": title[:220],
                    "company": (lead.company or "Entreprise")[:220],
                    "location": (lead.location or "International")[:220],
                    "description_text": lead.description_text or title,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return created, updated, skipped

    def handle(self, *args, **options):
        public_before = PublicJobOffer.objects.filter(is_active=True).count()

        if options["seed_demo_if_empty"] and public_before == 0:
            self.stdout.write(self.style.WARNING("Aucune offre publique: création des offres de départ..."))
            call_command("seed_public_job_offers")

        if options["publish_verified"]:
            self.stdout.write(self.style.WARNING("Publication des offres vérifiées par l'agent web..."))
            call_command(
                "publish_verified_job_offers",
                limit=max(1, min(int(options["limit"]), 300)),
                include_review=bool(options["include_review"]),
            )

        private_created = private_updated = private_skipped = 0
        if options["sync_private"]:
            self.stdout.write(self.style.WARNING("Synchronisation des offres privées utiles vers les offres publiques..."))
            private_created, private_updated, private_skipped = self._sync_private_leads()

        public_after = PublicJobOffer.objects.filter(is_active=True).count()

        self.stdout.write(
            self.style.SUCCESS(
                "Automatisation Job Agent terminée: "
                f"{public_before} offres publiques actives avant, {public_after} après. "
                f"Privées synchronisées: {private_created} créées, {private_updated} mises à jour, {private_skipped} ignorées."
            )
        )
