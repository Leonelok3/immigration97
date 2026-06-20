from django.core.management.base import BaseCommand

from outreach.scholarship_scraper import discover_scholarships
from visaetude.models import PublicScholarshipOffer


class Command(BaseCommand):
    help = "Scrape et publie des bourses d'études vérifiées avec lien direct de candidature."

    def add_arguments(self, parser):
        parser.add_argument("--country", default="", help="Pays cible, ex: CA, FR, DE, GB, AU.")
        parser.add_argument("--level", default="", help="Niveau: licence, master, doctorat, postdoc.")
        parser.add_argument("--query", default="", help="Requête personnalisée.")
        parser.add_argument("--source-url", action="append", default=[], help="Source précise à explorer. Peut être répété.")
        parser.add_argument("--limit", type=int, default=80)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 300))
        candidates = discover_scholarships(
            country=options["country"].strip(),
            level=options["level"].strip(),
            query=options["query"].strip(),
            source_urls=options["source_url"],
            limit=limit,
        )

        created = updated = skipped = 0
        for item in candidates:
            self.stdout.write(
                f"[{item.confidence_score}] {item.organization or 'Organisme'} | "
                f"{item.title} | {item.country} | {item.url}"
            )
            if options["dry_run"]:
                skipped += 1
                continue
            _offer, was_created = PublicScholarshipOffer.objects.update_or_create(
                url=item.url,
                defaults={
                    "source": item.source[:80],
                    "title": item.title[:260],
                    "organization": item.organization[:220],
                    "country": item.country[:120],
                    "region": item.region[:120],
                    "study_level": item.study_level,
                    "funding_type": item.funding_type,
                    "amount": item.amount[:180],
                    "eligible_countries": item.eligible_countries[:260],
                    "deadline": item.deadline[:100],
                    "requirements": item.requirements,
                    "description_text": item.description_text,
                    "confidence_score": item.confidence_score,
                    "verification_label": item.verification_label[:80],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Bourses: {created} créées, {updated} mises à jour, {skipped} ignorées/dry-run."
            )
        )
