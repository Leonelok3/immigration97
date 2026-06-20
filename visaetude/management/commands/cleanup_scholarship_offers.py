from django.core.management.base import BaseCommand
from django.db import IntegrityError

from outreach.scholarship_scraper import is_direct_scholarship_url
from visaetude.models import PublicScholarshipOffer


class Command(BaseCommand):
    help = "Désactive les bourses publiques qui ne pointent pas vers une source directe sérieuse."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        disabled = 0
        kept = 0
        for offer in PublicScholarshipOffer.objects.filter(is_active=True).order_by("-created_at"):
            if "#" in offer.url:
                canonical_url = offer.url.split("#", 1)[0]
                duplicate = PublicScholarshipOffer.objects.filter(url=canonical_url).exclude(pk=offer.pk).first()
                if duplicate:
                    disabled += 1
                    self.stdout.write(f"Désactivation doublon: #{offer.id} {offer.title} -> {offer.url}")
                    if not dry_run:
                        offer.is_active = False
                        offer.save(update_fields=["is_active", "updated_at"])
                    continue
                if not dry_run:
                    offer.url = canonical_url
                    try:
                        offer.save(update_fields=["url", "updated_at"])
                    except IntegrityError:
                        offer.is_active = False
                        offer.save(update_fields=["is_active", "updated_at"])
                        disabled += 1
                        continue
            if is_direct_scholarship_url(offer.url):
                kept += 1
                continue
            disabled += 1
            self.stdout.write(f"Désactivation: #{offer.id} {offer.title} -> {offer.url}")
            if not dry_run:
                offer.is_active = False
                offer.save(update_fields=["is_active", "updated_at"])

        action = "seraient désactivées" if dry_run else "désactivées"
        self.stdout.write(self.style.SUCCESS(f"Nettoyage bourses: {disabled} {action}, {kept} gardées."))
