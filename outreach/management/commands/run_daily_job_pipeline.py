from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Pipeline quotidien Immigration97: scrape, vérifie, anti-arnaque, publie les offres."

    def add_arguments(self, parser):
        parser.add_argument("--countries", default="CA,NZ,AU,EU")
        parser.add_argument("--sector", default="autre")
        parser.add_argument("--limit", type=int, default=80)
        parser.add_argument("--publish-limit", type=int, default=60)
        parser.add_argument("--email-to", default="")
        parser.add_argument("--include-review", action="store_true")

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 300))
        publish_limit = max(1, min(int(options["publish_limit"]), 300))

        self.stdout.write(self.style.WARNING("1/4 Agent web: recherche de nouvelles offres..."))
        scrape_kwargs = {
            "countries": options["countries"],
            "sector": options["sector"],
            "limit": limit,
        }
        if options["email_to"]:
            scrape_kwargs["email_to"] = options["email_to"]
        call_command("scrape_employer_opportunities", **scrape_kwargs)

        self.stdout.write(self.style.WARNING("2/4 Agent vérification: qualification des offres..."))
        call_command("verify_employer_opportunities", limit=limit, include_reviewed=True)

        self.stdout.write(self.style.WARNING("3/4 Agent anti-arnaque: contrôle des risques..."))
        call_command("assess_employer_scams", limit=limit, include_assessed=True)

        self.stdout.write(self.style.WARNING("4/4 Publication: offres visibles aux utilisateurs..."))
        call_command(
            "publish_verified_job_offers",
            limit=publish_limit,
            include_review=bool(options["include_review"]),
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Pipeline quotidien terminé. Vérifiez /jobs/offres-publiques/ pour les offres publiées."
            )
        )
