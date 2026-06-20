"""
python manage.py generate_employer_targets
python manage.py generate_employer_targets --dry-run
python manage.py generate_employer_targets --min-candidates 3 --employers-per-group 20
python manage.py generate_employer_targets --sector agriculture --country CA

Ce script lit la base de candidats (profiles.Profile + job_agent.CandidateProfile
+ job_agent.JobSearch) pour construire une matrice "secteur × pays cible",
puis génère pour chaque groupe des contacts employeurs ciblés via GPT.

Résultat : outreach.RecruiterContact enrichis avec context=données candidats réels.
"""
import json
import logging
import re
import time
from collections import defaultdict

from django.core.management.base import BaseCommand
from services.ai_service import AIService, AIServiceError

logger = logging.getLogger(__name__)

# ─── Mapping Category.name (libre) → outreach sector code ──────────────────
# Le script tente d'abord une correspondance exacte, sinon sous-chaîne.
CATEGORY_TO_SECTOR = {
    # Agriculture
    "agriculture": "agriculture", "agricole": "agriculture", "agriculteur": "agriculture",
    "agro": "agriculture", "agroalimentaire": "agriculture", "maraîch": "agriculture",
    "élevage": "agriculture", "ferme": "agriculture", "jardin": "agriculture",
    # Construction
    "construction": "construction", "btp": "construction", "bâtiment": "construction",
    "menuisier": "construction", "menuiserie": "construction", "plombier": "construction",
    "électricien": "construction", "maçon": "construction", "charpentier": "construction",
    "soudeur": "construction", "carreleur": "construction", "peintre": "construction",
    # Tech
    "informatique": "tech", "développeur": "tech", "tech": "tech", "web": "tech",
    "logiciel": "tech", "it": "tech", "data": "tech", "réseau": "tech",
    "système": "tech", "digital": "tech", "numérique": "tech",
    # Santé
    "santé": "sante", "infirmier": "sante", "médecin": "sante", "médical": "sante",
    "aide-soignant": "sante", "pharmacie": "sante", "kinésithér": "sante",
    # Logistique
    "logistique": "logistique", "transport": "logistique", "chauffeur": "logistique",
    "livreur": "logistique", "magasinier": "logistique", "entrepôt": "logistique",
    # Hôtellerie
    "hôtel": "hotellerie", "restaurant": "hotellerie", "cuisinier": "hotellerie",
    "serveur": "hotellerie", "tourisme": "hotellerie", "cuisine": "hotellerie",
    # Éducation
    "éducation": "education", "enseignant": "education", "professeur": "education",
    "formation": "education", "école": "education",
    # Finance
    "comptable": "finance", "finance": "finance", "audit": "finance",
    "banque": "finance", "trésor": "finance",
    # Industrie
    "industrie": "industrie", "manufacture": "industrie", "opérateur": "industrie",
    "usine": "industrie", "production": "industrie",
    # Commerce
    "commercial": "commerce", "vente": "commerce", "commerce": "commerce",
    "marketing": "commerce", "achat": "commerce",
}

# ─── Mapping texte libre localisation → code pays outreach ─────────────────
LOCATION_TO_COUNTRY = {
    "canada": "CA", "canadien": "CA", "québec": "CA", "ontario": "CA",
    "montréal": "CA", "toronto": "CA", "vancouver": "CA", "calgary": "CA",
    "france": "FR", "français": "FR", "paris": "FR", "lyon": "FR",
    "marseille": "FR", "bordeaux": "FR", "toulouse": "FR",
    "allemagne": "DE", "german": "DE", "berlin": "DE", "munich": "DE",
    "belgique": "BE", "bruxelles": "BE", "belgisch": "BE",
    "suisse": "CH", "genève": "CH", "zurich": "CH",
    "australie": "AU", "sydney": "AU", "melbourne": "AU",
    "royaume-uni": "GB", "uk": "GB", "london": "GB", "england": "GB",
    "états-unis": "US", "usa": "US", "new york": "US",
    "maroc": "MA", "casablanca": "MA", "rabat": "MA",
}

# ─── Labels lisibles pour les prompts GPT ──────────────────────────────────
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
    "autre": "Divers",
}
COUNTRY_LABELS = {
    "CA": "Canada", "FR": "France", "DE": "Allemagne", "BE": "Belgique",
    "CH": "Suisse", "AU": "Australie", "GB": "Royaume-Uni", "US": "États-Unis",
    "MA": "Maroc", "SN": "Sénégal", "CI": "Côte d'Ivoire",
}


# ═══════════════════════════════════════════════════════════════════════════
# ANALYSE DE LA BASE CANDIDATS
# ═══════════════════════════════════════════════════════════════════════════

def _normalize_sector(text: str) -> str:
    """Convertit un nom de catégorie libre en code secteur outreach."""
    text_lower = text.lower().strip()
    if text_lower in CATEGORY_TO_SECTOR:
        return CATEGORY_TO_SECTOR[text_lower]
    for key, code in CATEGORY_TO_SECTOR.items():
        if key in text_lower or text_lower in key:
            return code
    return "autre"


def _normalize_country(text: str) -> str | None:
    """Extrait un code pays depuis un texte libre."""
    if not text:
        return None
    text_lower = text.lower().strip()
    for key, code in LOCATION_TO_COUNTRY.items():
        if key in text_lower:
            return code
    # Codes ISO directs (CA, FR, DE…)
    iso = text.strip().upper()[:2]
    if iso in COUNTRY_LABELS:
        return iso
    return None


def analyze_candidates(only_sector=None, only_country=None) -> dict:
    """
    Lit la base Django et retourne :
    {
      (sector_code, country_code): {
        "count": int,
        "skills": [str, ...],        # compétences les plus fréquentes
        "job_titles": [str, ...],     # titres de poste recherchés
        "keywords": [str, ...],       # mots-clés de recherche
        "headlines": [str, ...],      # titres de profil candidats
        "contracts": [str, ...],      # types de contrat souhaités
      }
    }
    """
    from profiles.models import Profile, ProfileSkill
    from job_agent.models import CandidateProfile, JobSearch

    groups = defaultdict(lambda: {
        "count": 0, "skills": defaultdict(int),
        "job_titles": [], "keywords": [], "headlines": [], "contracts": []
    })

    # ── 1. Profils publiés + catégorie + compétences ────────────────────────
    profiles_qs = Profile.objects.filter(is_public=True).select_related(
        "category", "user"
    ).prefetch_related("profileskill_set__skill")

    for p in profiles_qs:
        sector = _normalize_sector(p.category.name) if p.category else "autre"
        if only_sector and sector != only_sector:
            continue

        # Essayer de trouver le pays cible depuis CandidateProfile
        try:
            cp = p.user.candidate_profile
            country = _normalize_country(cp.preferred_location) or _normalize_country(cp.country)
        except Exception:
            cp = None
            country = None

        if not country:
            country = "CA"  # défaut Canada si non renseigné

        if only_country and country != only_country:
            continue

        key = (sector, country)
        groups[key]["count"] += 1

        if p.headline:
            groups[key]["headlines"].append(p.headline)

        if cp:
            if cp.preferred_contract:
                groups[key]["contracts"].append(cp.preferred_contract)

        for ps in p.profileskill_set.all():
            groups[key]["skills"][ps.skill.name] += 1

    # ── 2. JobSearch (titres + keywords + localisations) ───────────────────
    for js in JobSearch.objects.all().select_related("user"):
        country = _normalize_country(js.location)
        if not country:
            continue

        sector = "autre"
        # Essayer de déduire le secteur depuis le titre de recherche
        combined = f"{js.title} {js.keywords}".lower()
        for key_word, code in CATEGORY_TO_SECTOR.items():
            if key_word in combined:
                sector = code
                break

        if only_sector and sector != only_sector:
            continue
        if only_country and country != only_country:
            continue

        key = (sector, country)
        if js.title:
            groups[key]["job_titles"].append(js.title)
        if js.keywords:
            for kw in js.keywords.split(","):
                kw = kw.strip()
                if kw:
                    groups[key]["keywords"].append(kw)

    # Trier les compétences par fréquence
    result = {}
    for key, data in groups.items():
        result[key] = {
            "count": data["count"],
            "skills": [k for k, _ in sorted(data["skills"].items(), key=lambda x: -x[1])[:10]],
            "job_titles": list(dict.fromkeys(data["job_titles"]))[:8],
            "keywords": list(dict.fromkeys(data["keywords"]))[:12],
            "headlines": list(dict.fromkeys(data["headlines"]))[:6],
            "contracts": list(dict.fromkeys(data["contracts"]))[:4],
        }

    return result


# ═══════════════════════════════════════════════════════════════════════════
# GÉNÉRATION GPT
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Tu es un expert en recrutement international et en ressources humaines.
Tu connais les entreprises qui recrutent des travailleurs africains qualifiés dans différents pays.

Quand on te fournit un profil de candidats (secteur, compétences, titres de poste),
tu génères une liste d'entreprises employeurs qui correspondent EXACTEMENT à ce profil.

Retourne UNIQUEMENT un JSON valide (tableau), sans markdown, sans explication.
Chaque objet a ces champs :
- company_name : nom d'entreprise réaliste (peut être fictif mais plausible)
- contact_name : nom du responsable RH (peut être vide)
- job_title : poste du contact (ex: DRH, Responsable RH, Directeur du personnel)
- email : email professionnel réaliste du domaine de l'entreprise
- phone : numéro international (peut être vide)
- website : URL plausible (peut être vide)
- city : ville dans le pays cible
- notes : 1 phrase sur l'activité de l'entreprise et pourquoi elle recrute des profils africains"""


def build_gpt_prompt(sector: str, country: str, group_data: dict, count: int) -> str:
    sector_label = SECTOR_LABELS.get(sector, sector)
    country_label = COUNTRY_LABELS.get(country, country)

    lines = [
        f"Génère {count} contacts d'employeurs dans le secteur « {sector_label} » au {country_label}.",
        "",
        f"Contexte réel : nous avons {group_data['count']} candidat(s) africain(s) qualifié(s)",
        f"dans ce secteur qui cherchent du travail au {country_label}.",
        "",
    ]

    if group_data["skills"]:
        lines.append(f"Compétences clés de nos candidats : {', '.join(group_data['skills'])}")

    if group_data["job_titles"]:
        lines.append(f"Postes recherchés : {', '.join(group_data['job_titles'])}")

    if group_data["headlines"]:
        lines.append(f"Exemples de profils : {', '.join(group_data['headlines'][:3])}")

    if group_data["contracts"]:
        lines.append(f"Types de contrat souhaités : {', '.join(group_data['contracts'])}")

    lines += [
        "",
        f"Génère {count} employeurs qui auraient besoin de ces profils.",
        "Retourne uniquement le JSON tableau, sans markdown.",
    ]

    return "\n".join(lines)


def call_gpt(prompt: str, model: str) -> list:
    for attempt in range(1, 4):
        try:
            raw = AIService().chat_text(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=prompt,
                task_type="analyse",
            )
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for key in ("contacts", "results", "data", "employers"):
                    if key in data and isinstance(data[key], list):
                        return data[key]
        except json.JSONDecodeError as e:
            logger.warning("JSON parse error attempt %d: %s", attempt, e)
            if attempt < 3:
                time.sleep(2)
        except AIServiceError as e:
            logger.warning("AIService error: %s", e)
            return []
        except Exception as e:
            logger.warning("GPT error attempt %d: %s", attempt, e)
            if attempt < 3:
                time.sleep(3)
    return []


# ═══════════════════════════════════════════════════════════════════════════
# COMMANDE DJANGO
# ═══════════════════════════════════════════════════════════════════════════

class Command(BaseCommand):
    help = (
        "Analyse la base de candidats et génère des contacts employeurs ciblés via GPT. "
        "Résultat sauvegardé dans outreach.RecruiterContact."
    )

    def add_arguments(self, parser):
        parser.add_argument("--min-candidates", type=int, default=1,
                            help="Nombre minimum de candidats pour traiter un groupe (défaut: 1)")
        parser.add_argument("--employers-per-group", type=int, default=15,
                            help="Nombre d'employeurs à générer par groupe (défaut: 15)")
        parser.add_argument("--sector", help="Forcer un secteur spécifique (ex: agriculture)")
        parser.add_argument("--country", help="Forcer un pays spécifique (ex: CA)")
        parser.add_argument("--model", default="gpt-4.1-mini", help="Modèle OpenAI")
        parser.add_argument("--dry-run", action="store_true",
                            help="Afficher l'analyse sans appeler GPT ni insérer en base")

    def handle(self, *args, **options):
        min_cand = options["min_candidates"]
        per_group = options["employers_per_group"]
        only_sector = options.get("sector")
        only_country = options.get("country")
        model = options["model"]
        dry_run = options["dry_run"]

        self.stdout.write("🔍 Analyse de la base candidats…")
        groups = analyze_candidates(only_sector=only_sector, only_country=only_country)

        if not groups:
            self.stdout.write(self.style.WARNING(
                "⚠️  Aucun candidat trouvé. Vérifiez que des profils sont publiés (is_public=True) "
                "et que des CandidateProfile existent avec preferred_location renseigné."
            ))
            return

        # Filtrer par seuil minimum
        eligible = {k: v for k, v in groups.items() if v["count"] >= min_cand}

        self.stdout.write(f"\n📊 Matrice candidats → employeurs cibles :")
        self.stdout.write(f"{'Secteur':<25} {'Pays':<8} {'Candidats':>10} {'Compétences (top 3)'}")
        self.stdout.write("─" * 75)
        for (sector, country), data in sorted(eligible.items(), key=lambda x: -x[1]["count"]):
            top_skills = ", ".join(data["skills"][:3]) or "—"
            self.stdout.write(
                f"{SECTOR_LABELS.get(sector, sector):<25} {country:<8} "
                f"{data['count']:>10}   {top_skills}"
            )

        self.stdout.write(f"\n{'─'*75}")
        self.stdout.write(f"Total : {len(eligible)} groupe(s) — "
                          f"~{len(eligible) * per_group} employeurs à générer")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n[DRY-RUN] Analyse terminée. Aucun appel GPT effectué."))
            self._show_sample_prompt(eligible, per_group)
            return

        from outreach.models import RecruiterContact

        total_created = total_updated = total_skipped = 0

        for i, ((sector, country), data) in enumerate(
            sorted(eligible.items(), key=lambda x: -x[1]["count"]), 1
        ):
            sector_label = SECTOR_LABELS.get(sector, sector)
            country_label = COUNTRY_LABELS.get(country, country)
            self.stdout.write(
                f"\n[{i}/{len(eligible)}] 🎯 {sector_label} / {country_label} "
                f"({data['count']} candidat(s)) — génération de {per_group} employeurs…"
            )

            prompt = build_gpt_prompt(sector, country, data, per_group)
            contacts = call_gpt(prompt, model)

            if not contacts:
                self.stderr.write(f"  ⚠️  Aucun contact généré pour ce groupe.")
                continue

            self.stdout.write(f"  ✅ {len(contacts)} contact(s) reçus de GPT.")

            created = updated = skipped = 0
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
                    "tags": f"auto-généré,{sector},{country}",
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
                    self.stderr.write(f"    ⚠️  Erreur ({email}): {e}")
                    skipped += 1

            total_created += created
            total_updated += updated
            total_skipped += skipped
            self.stdout.write(
                f"  💾 Sauvegardés : {created} créés, {updated} mis à jour, {skipped} ignorés."
            )

            # Pause entre les groupes pour respecter les rate limits OpenAI
            if i < len(eligible):
                time.sleep(1.5)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Terminé — {total_created} créés, {total_updated} mis à jour, "
            f"{total_skipped} ignorés sur {len(eligible)} groupe(s) traité(s)."
        ))

    def _show_sample_prompt(self, eligible: dict, per_group: int):
        """Affiche un exemple de prompt qui serait envoyé à GPT."""
        if not eligible:
            return
        (sector, country), data = next(iter(
            sorted(eligible.items(), key=lambda x: -x[1]["count"])
        ))
        self.stdout.write("\n─── Exemple de prompt GPT (premier groupe) ───")
        self.stdout.write(build_gpt_prompt(sector, country, data, per_group))
        self.stdout.write("─" * 60)
