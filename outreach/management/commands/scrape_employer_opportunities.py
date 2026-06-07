from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.conf import settings

from outreach.ai_employer_scraper import discover_employers
from outreach.models import ScrapedEmployerLead, ScamAssessment
from outreach.opportunity_verifier import verify_employer_lead
from outreach.scam_guard import assess_scam_risk


class Command(BaseCommand):
    help = (
        "Scrape le web pour trouver des employeurs/offres avec signaux visa "
        "pour candidats africains/internationaux."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--countries",
            default="CA,NZ,AU,EU",
            help="Codes pays séparés par virgule. EU étend vers FR,DE,BE,CH,GB,IE,NL,IT,ES,PT.",
        )
        parser.add_argument("--sector", default="autre", help="Secteur outreach, ex: agriculture, sante, tech.")
        parser.add_argument("--query", default="", help="Requête web personnalisée.")
        parser.add_argument(
            "--source-url",
            action="append",
            default=[],
            help="URL source précise à explorer. Peut être répété.",
        )
        parser.add_argument("--limit", type=int, default=60, help="Nombre maximum de leads à traiter.")
        parser.add_argument("--dry-run", action="store_true", help="Affiche sans enregistrer.")
        parser.add_argument("--skip-verification", action="store_true", help="Ne pas lancer l'Agent Opportunités Vérifiées.")
        parser.add_argument("--skip-scam-check", action="store_true", help="Ne pas lancer l'Agent Anti-Arnaque.")
        parser.add_argument("--email-to", default="", help="Adresse email pour recevoir le rapport.")

    def handle(self, *args, **options):
        countries = [c.strip().upper() for c in options["countries"].split(",") if c.strip()]
        sector = options["sector"].strip().lower() or "autre"
        query = options["query"].strip()
        source_urls = options["source_url"]
        limit = max(1, min(options["limit"], 300))
        dry_run = options["dry_run"]
        skip_verification = options["skip_verification"]
        skip_scam_check = options["skip_scam_check"]
        email_to = options["email_to"].strip()

        self.stdout.write(
            f"Agent web employeurs: countries={countries}, sector={sector}, limit={limit}, dry_run={dry_run}"
        )

        leads = discover_employers(
            countries=countries,
            sector=sector,
            query=query,
            source_urls=source_urls,
            limit=limit,
        )

        created = updated = skipped = 0
        report_lines = [
            "Rapport agent web Immigration97",
            f"Pays: {', '.join(countries)}",
            f"Secteur: {sector}",
            f"Leads detectes: {len(leads)}",
            "",
        ]

        for lead in leads:
            report_lines.append(
                f"- [{lead.country}] {lead.company_name or 'Employeur a verifier'} | "
                f"{lead.title} | score={lead.confidence_score} | {lead.job_url}"
            )

            if dry_run:
                skipped += 1
                continue

            obj, was_created = ScrapedEmployerLead.objects.update_or_create(
                job_url=lead.job_url,
                defaults={
                    "title": lead.title[:240],
                    "company_name": lead.company_name[:220],
                    "country": lead.country,
                    "sector": lead.sector,
                    "location": lead.location[:180],
                    "source_url": lead.source_url[:600],
                    "website": lead.website[:400],
                    "contact_email": lead.contact_email,
                    "visa_signal": lead.visa_signal[:180],
                    "evidence_text": lead.evidence_text,
                    "confidence_score": lead.confidence_score,
                    "raw_data": lead.raw_data,
                },
            )
            if not skip_verification:
                verification = verify_employer_lead(obj)
                obj.verification_score = verification.score
                obj.verification_decision = verification.decision
                obj.verification_notes = verification.notes
                obj.verification_signals = verification.signals
                if verification.decision == "verified":
                    obj.status = "reviewed"
                elif verification.decision == "weak":
                    obj.status = "rejected"
                obj.save(
                    update_fields=[
                        "verification_score",
                        "verification_decision",
                        "verification_notes",
                        "verification_signals",
                        "status",
                        "updated_at",
                    ]
                )
            if not skip_scam_check:
                scam = assess_scam_risk(obj)
                ScamAssessment.objects.update_or_create(
                    lead=obj,
                    defaults={
                        "risk_score": scam.risk_score,
                        "risk_level": scam.risk_level,
                        "flags": scam.flags,
                        "recommendation": scam.recommendation,
                    },
                )
            if was_created:
                created += 1
            else:
                updated += 1

        summary = f"Termine: {created} crees, {updated} mis a jour, {skipped} ignores/dry-run."
        self.stdout.write(self.style.SUCCESS(summary))
        report_lines.append("")
        report_lines.append(summary)

        if email_to:
            send_mail(
                subject="Rapport quotidien agent employeurs Immigration97",
                message="\n".join(report_lines),
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[email_to],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS(f"Rapport envoye a {email_to}"))

        self.stdout.write("")
        self.stdout.write("Commande cron exemple:")
        self.stdout.write(
            "0 6 * * * /path/to/venv/bin/python /path/to/project/manage.py "
            "scrape_employer_opportunities --countries CA,NZ,AU,EU --limit 80 "
            "--email-to contact@immigration97.com"
        )
