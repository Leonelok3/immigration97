from django.core.management.base import BaseCommand
from django.utils.text import slugify
from urllib.parse import urlparse

from job_agent.models import PublicJobOffer
from outreach.ai_employer_scraper import is_direct_application_url
from outreach.models import ScrapedEmployerLead
from profiles.models import Category


SECTOR_CATEGORY = {
    "agriculture": "Agriculture & Agroalimentaire",
    "construction": "BTP & Construction",
    "tech": "Développement Web & IT",
    "sante": "Aide-soignant & Santé",
    "logistique": "Transport & Logistique",
    "hotellerie": "Hôtellerie & Service client",
    "education": "Éducation & Formation",
    "finance": "Comptabilité & Finance",
    "industrie": "Industrie & Manufacture",
    "commerce": "Commerce & Vente",
    "services": "Services aux entreprises",
    "autre": "Autres métiers",
}

TRUSTED_BOARD_COMPANY_LABELS = {
    "jobbank.gc.ca": "Employeur vérifié Job Bank",
    "guichetemplois.gc.ca": "Employeur vérifié Job Bank",
    "arbeitsagentur.de": "Employeur via Bundesagentur für Arbeit",
    "make-it-in-germany.com": "Employeur via Make it in Germany",
    "ausbildung.de": "Employeur Ausbildung",
    "azubiyo.de": "Employeur Ausbildung",
    "aubi-plus.de": "Employeur Ausbildung",
    "eures.europa.eu": "Employeur via EURES Espagne",
    "sepe.es": "Employeur via SEPE",
    "empleate.gob.es": "Employeur via Empléate",
    "sistemanacionalempleo.es": "Employeur via Sistema Nacional de Empleo",
    "infojobs.net": "Employeur via InfoJobs Espagne",
    "turijobs.com": "Employeur via Turijobs Espagne",
    "hosteleo.com": "Employeur via Hosteleo Espagne",
}

COUNTRY_LOCATION_FALLBACKS = {
    "CA": "Canada",
    "DE": "Allemagne",
    "ES": "Espagne",
    "FR": "France",
    "BE": "Belgique",
    "AU": "Australie",
    "NZ": "Nouvelle-Zélande",
    "GB": "Royaume-Uni",
}


def _usable_company_name(value: str) -> str:
    value = (value or "").strip()
    polluted_terms = (
        "alta candidato",
        "alta empresa",
        "accede blog",
        "seleciona una provincia",
        "buscar ofertas",
    )
    if any(term in value.lower() for term in polluted_terms):
        return ""
    return value


def _category_for_sector(sector: str):
    name = SECTOR_CATEGORY.get((sector or "autre").strip().lower(), SECTOR_CATEGORY["autre"])
    existing = Category.objects.filter(name=name).first()
    if existing:
        return existing
    return Category.objects.get_or_create(slug=slugify(name)[:100], defaults={"name": name})[0]


class Command(BaseCommand):
    help = "Publie les leads employeurs vérifiés en offres publiques visibles aux utilisateurs."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=80)
        parser.add_argument("--country", default="", help="Filtrer par pays, ex: CA, NZ, AU, FR.")
        parser.add_argument("--include-review", action="store_true", help="Inclure les leads à revoir.")
        parser.add_argument("--deactivate-missing", action="store_true", help="Désactiver les anciennes offres issues du scraper absentes du lot.")

    def handle(self, *args, **options):
        limit = max(1, min(int(options["limit"]), 300))
        decisions = ["verified"]
        if options["include_review"]:
            decisions.append("review")

        qs = ScrapedEmployerLead.objects.filter(
            verification_decision__in=decisions,
        ).exclude(
            status="rejected",
        ).order_by("-last_seen_at", "-verification_score", "-confidence_score")

        if options["country"]:
            qs = qs.filter(country=options["country"].strip().upper())

        created = updated = skipped = 0
        published_urls = []

        for lead in qs[:limit]:
            if not is_direct_application_url(lead.job_url):
                skipped += 1
                continue

            host = urlparse(lead.job_url or "").netloc.lower().removeprefix("www.")
            company_name = _usable_company_name(lead.company_name)
            if not company_name:
                for host_hint, label in TRUSTED_BOARD_COMPANY_LABELS.items():
                    if host_hint in host:
                        company_name = label
                        break
            if not company_name:
                skipped += 1
                continue

            risk_level = ""
            try:
                risk_level = lead.scam_assessment.risk_level
            except Exception:
                risk_level = ""
            if risk_level == "high":
                skipped += 1
                continue

            category = _category_for_sector(lead.sector)
            details = (lead.raw_data or {}).get("job_details") or {}
            training_lines = []
            for label, key in [
                ("Type", "training_type"),
                ("Début", "start_date"),
                ("Diplôme demandé", "degree_required"),
                ("Niveau allemand", "language_level"),
            ]:
                value = (details.get(key) or "").strip()
                if value:
                    training_lines.append(f"{label}: {value}")
            description = "\n\n".join(
                part
                for part in [
                    lead.evidence_text.strip(),
                    "\n".join(training_lines),
                    lead.verification_notes.strip(),
                    f"Signal visa/recrutement international: {lead.visa_signal}".strip()
                    if lead.visa_signal
                    else "",
                ]
                if part
            )
            keyword_parts = list(lead.verification_signals or [])
            for key in ["training_type", "start_date", "degree_required", "language_level"]:
                value = (details.get(key) or "").strip()
                if value:
                    keyword_parts.append(value)

            offer, was_created = PublicJobOffer.objects.update_or_create(
                url=lead.job_url,
                defaults={
                    "source": "Agent web Immigration97",
                    "title": lead.title[:220],
                    "company": company_name[:220],
                    "location": lead.location[:220] or COUNTRY_LOCATION_FALLBACKS.get(lead.country, lead.country),
                    "category": category,
                    "skills_keywords": ", ".join(keyword_parts)[:300],
                    "foreign_access_score": int(details.get("foreign_access_score") or lead.confidence_score or 0),
                    "foreign_access_label": (details.get("foreign_access_label") or "À vérifier")[:80],
                    "salary": (details.get("salary") or "")[:180],
                    "province": (details.get("province") or "")[:80],
                    "application_deadline": (details.get("application_deadline") or "")[:80],
                    "vacancies": (details.get("vacancies") or "")[:80],
                    "who_can_apply": details.get("who_can_apply") or "",
                    "description_text": description or lead.title,
                    "is_active": True,
                },
            )
            published_urls.append(offer.url)
            lead.status = "imported"
            lead.save(update_fields=["status", "updated_at"])

            if was_created:
                created += 1
            else:
                updated += 1

        if options["deactivate_missing"] and published_urls:
            PublicJobOffer.objects.filter(source="Agent web Immigration97").exclude(url__in=published_urls).update(is_active=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Publication offres: {created} créées, {updated} mises à jour, {skipped} ignorées."
            )
        )
