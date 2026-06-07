from django.core.management.base import BaseCommand

from outreach.models import ScrapedEmployerLead, ScamAssessment
from outreach.scam_guard import assess_scam_risk


class Command(BaseCommand):
    help = "Analyse les leads employeurs avec l'Agent Anti-Arnaque."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--country", default="", help="Filtrer par pays, ex: CA, NZ, AU.")
        parser.add_argument("--include-assessed", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 1000))
        qs = ScrapedEmployerLead.objects.all().order_by("-last_seen_at")
        if options["country"]:
            qs = qs.filter(country=options["country"].upper())
        if not options["include_assessed"]:
            qs = qs.filter(scam_assessment__isnull=True)

        low = medium = high = 0
        for lead in qs[:limit]:
            result = assess_scam_risk(lead)
            ScamAssessment.objects.update_or_create(
                lead=lead,
                defaults={
                    "risk_score": result.risk_score,
                    "risk_level": result.risk_level,
                    "flags": result.flags,
                    "recommendation": result.recommendation,
                },
            )
            if result.risk_level == "high":
                high += 1
            elif result.risk_level == "medium":
                medium += 1
            else:
                low += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Agent Anti-Arnaque: {low} faible, {medium} moyen, {high} élevé."
            )
        )
