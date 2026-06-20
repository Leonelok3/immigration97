"""
python manage.py find_recruiters --sector agriculture --country CA --count 30

Utilise GPT pour générer une liste de contacts recruteurs fictifs/réalistes
à partir d'un secteur et d'un pays. Les résultats sont insérés en base
(RecruiterContact) avec source="ai_search".

Pour de vraies données : remplacer generate_with_ai() par un scraper web.
"""
import json
import logging
import time

from django.core.management.base import BaseCommand, CommandError
from services.ai_service import AIService, AIServiceError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es un expert en ressources humaines et en recrutement international.
Tu connais les entreprises qui recrutent des travailleurs africains qualifiés.

Quand on te demande une liste de recruteurs, tu dois retourner UNIQUEMENT un JSON valide
(pas de markdown, pas d'explication), tableau d'objets avec ces champs :
- company_name (string, nom réel ou plausible)
- contact_name (string, peut être vide)
- job_title (string, ex: "DRH", "Responsable RH", "Directeur du personnel")
- email (string, email professionnel réaliste du domaine de l'entreprise)
- phone (string, format international, peut être vide)
- website (string, URL plausible, peut être vide)
- city (string)
- notes (string, courte description de l'activité de l'entreprise)

Génère des contacts réalistes et diversifiés. Les emails doivent correspondre au domaine
de l'entreprise (ex: rh@nomEntreprise.ca)."""

USER_PROMPT_TEMPLATE = """Génère {count} contacts de recruteurs dans le secteur "{sector_label}"
au {country_label} qui pourraient être intéressés à recruter des candidats africains qualifiés.

Retourne uniquement le JSON tableau, sans markdown ni commentaire."""


SECTOR_LABELS = {
    "agriculture": "Agriculture / Agroalimentaire",
    "construction": "Construction / BTP",
    "tech": "Technologie / IT",
    "sante": "Santé / Médical",
    "logistique": "Transport / Logistique",
    "hotellerie": "Hôtellerie / Restauration",
    "education": "Éducation / Formation",
    "finance": "Finance / Comptabilité",
    "industrie": "Industrie / Manufacture",
    "commerce": "Commerce / Vente",
    "services": "Services aux entreprises",
}

COUNTRY_LABELS = {
    "CA": "Canada", "FR": "France", "DE": "Allemagne", "BE": "Belgique",
    "CH": "Suisse", "AU": "Australie", "GB": "Royaume-Uni", "US": "États-Unis",
    "MA": "Maroc", "SN": "Sénégal", "CI": "Côte d'Ivoire",
}


class Command(BaseCommand):
    help = "Génère des contacts recruteurs via l'IA GPT et les insère en base."

    def add_arguments(self, parser):
        parser.add_argument("--sector", required=True, help="Code secteur ex: agriculture")
        parser.add_argument("--country", required=True, help="Code pays ex: CA")
        parser.add_argument("--count", type=int, default=20, help="Nombre de contacts à générer (max 50)")
        parser.add_argument("--dry-run", action="store_true", help="Afficher sans insérer en base")
        parser.add_argument("--model", default="gpt-4.1-mini", help="Modèle OpenAI à utiliser")

    def handle(self, *args, **options):
        sector = options["sector"].lower().strip()
        country = options["country"].upper().strip()
        count = min(options["count"], 50)
        dry_run = options["dry_run"]
        model = options["model"]

        sector_label = SECTOR_LABELS.get(sector, sector)
        country_label = COUNTRY_LABELS.get(country, country)

        self.stdout.write(f"🔍 Recherche de {count} recruteurs — {sector_label} / {country_label}")
        self.stdout.write(f"   Modèle : {model} | Dry-run : {dry_run}")

        contacts = self._generate_with_ai(sector_label, country_label, count, model)

        if not contacts:
            raise CommandError("Aucun contact généré. Vérifiez votre clé OpenAI (OPENAI_API_KEY).")

        self.stdout.write(f"✅ {len(contacts)} contact(s) générés.")

        if dry_run:
            self.stdout.write("\n--- DRY RUN (rien n'est inséré) ---")
            for i, c in enumerate(contacts, 1):
                self.stdout.write(
                    f"{i}. {c.get('company_name')} — {c.get('email')} — {c.get('city')}"
                )
            return

        created = updated = skipped = 0
        from outreach.models import RecruiterContact

        for c in contacts:
            email = (c.get("email") or "").strip().lower()
            company = (c.get("company_name") or "").strip()
            if not email or "@" not in email or not company:
                skipped += 1
                continue

            defaults = {
                "company_name": company,
                "contact_name": (c.get("contact_name") or "").strip(),
                "job_title": (c.get("job_title") or "").strip(),
                "phone": (c.get("phone") or "").strip(),
                "website": (c.get("website") or "").strip(),
                "city": (c.get("city") or "").strip(),
                "notes": (c.get("notes") or "").strip(),
                "sector": sector,
                "country": country,
                "source": "ai_search",
            }

            try:
                _, was_created = RecruiterContact.objects.update_or_create(
                    email=email, defaults=defaults
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                self.stderr.write(f"  ⚠️ Erreur ({email}): {e}")
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Import terminé — {created} créés, {updated} mis à jour, {skipped} ignorés."
            )
        )

    def _generate_with_ai(self, sector_label, country_label, count, model) -> list:
        user_msg = USER_PROMPT_TEMPLATE.format(
            count=count, sector_label=sector_label, country_label=country_label
        )

        for attempt in range(1, 4):
            try:
                self.stdout.write(f"  Tentative {attempt}/3 …")
                raw = AIService().chat_text(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=user_msg,
                    task_type="analyse",
                )

                # Nettoyer le markdown si présent
                if raw.startswith("```"):
                    raw = raw.split("```")[1]
                    if raw.startswith("json"):
                        raw = raw[4:]

                data = json.loads(raw)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "contacts" in data:
                    return data["contacts"]
                self.stderr.write(f"  Format inattendu : {type(data)}")
                return []

            except json.JSONDecodeError as e:
                self.stderr.write(f"  JSON parse error (tentative {attempt}): {e}")
                if attempt < 3:
                    time.sleep(2)
            except AIServiceError as e:
                self.stderr.write(f"  AIService error: {e}")
                return []
            except Exception as e:
                self.stderr.write(f"  API error (tentative {attempt}): {e}")
                if attempt < 3:
                    time.sleep(3)

        return []
