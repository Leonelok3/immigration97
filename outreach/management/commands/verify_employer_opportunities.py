from django.core.management.base import BaseCommand

from outreach.models import ScrapedEmployerLead
from outreach.opportunity_verifier import verify_employer_lead


class Command(BaseCommand):
    help = "Qualifie les leads employeurs avec l'Agent Opportunités Vérifiées."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200)
        parser.add_argument("--country", default="", help="Filtrer par pays, ex: CA, NZ, AU.")
        parser.add_argument("--include-reviewed", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 1000))
        qs = ScrapedEmployerLead.objects.all().order_by("-last_seen_at")
        if options["country"]:
            qs = qs.filter(country=options["country"].upper())
        if not options["include_reviewed"]:
            qs = qs.exclude(verification_decision__in=["verified", "review", "weak"])

        verified = review = weak = 0
        for lead in qs[:limit]:
            result = verify_employer_lead(lead)
            lead.verification_score = result.score
            lead.verification_decision = result.decision
            lead.verification_notes = result.notes
            lead.verification_signals = result.signals
            if result.decision == "verified":
                lead.status = "reviewed"
                verified += 1
            elif result.decision == "review":
                review += 1
            else:
                lead.status = "rejected"
                weak += 1
            lead.save(
                update_fields=[
                    "verification_score",
                    "verification_decision",
                    "verification_notes",
                    "verification_signals",
                    "status",
                    "updated_at",
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Agent Opportunités Vérifiées: {verified} vérifiés, {review} à revoir, {weak} faibles."
            )
        )
