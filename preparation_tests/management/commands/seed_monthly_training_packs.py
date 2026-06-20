from datetime import date

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from preparation_tests.models import MonthlyTrainingPack
from preparation_tests.services.monthly_content_ai import generate_exercises_for_source


def _pack_slug(month_date, section, title):
    max_len = MonthlyTrainingPack._meta.get_field("slug").max_length or 50
    base = slugify(f"{month_date:%Y-%m}-{section}-{title}") or f"{month_date:%Y-%m}-{section}"
    return base[:max_len].rstrip("-")


PACKS = {
    "co": {
        "level": "B1",
        "title": "Comprendre une annonce administrative canadienne",
        "subtitle": "Rendez-vous, documents, délais et consignes entendues dans un contexte d'immigration.",
        "objective": "S'entraîner à repérer les informations clés d'une annonce orale: date, lieu, document demandé, conséquence et prochaine étape.",
        "theme": "Démarches administratives, rendez-vous et documents d'immigration",
        "lesson": """
<p>Dans les examens TEF/TCF, les documents oraux administratifs reviennent souvent: message vocal, consigne d'un agent, annonce de service ou conversation courte.</p>
<p>La stratégie consiste à noter les informations concrètes: qui parle, pourquoi, quelle date, quel document, quel délai et quelle action est demandée.</p>
<p>Attention aux distracteurs: une date corrigée, un document mentionné mais non demandé, ou une conséquence formulée indirectement.</p>
""",
    },
    "ce": {
        "level": "B2",
        "title": "Lire un texte sur l'intégration professionnelle des immigrants",
        "subtitle": "Comprendre arguments, données et nuances dans un article de société.",
        "objective": "Travailler les questions fréquentes: idée principale, opinion de l'auteur, cause/conséquence, inférence et vocabulaire en contexte.",
        "theme": "Intégration professionnelle, reconnaissance des diplômes et marché du travail",
        "lesson": """
<p>Les textes sur l'immigration, l'emploi et l'intégration sont très fréquents dans les examens de compréhension écrite.</p>
<p>Pour réussir, distingue les faits, les exemples et l'opinion de l'auteur. Repère les connecteurs: cependant, en revanche, ainsi, faute de, malgré.</p>
<p>Les mauvaises réponses reprennent souvent des mots du texte mais changent la relation logique. Vérifie toujours si l'option respecte la cause, la conséquence et le point de vue.</p>
""",
    },
    "eo": {
        "level": "B2",
        "title": "Présenter et défendre son projet d'installation au Canada",
        "subtitle": "Sujet oral fréquent: motivations, projet professionnel, intégration et arguments.",
        "objective": "Préparer une réponse orale structurée avec introduction, arguments, exemples et conclusion claire.",
        "theme": "Projet d'immigration, intégration et objectifs professionnels",
        "lesson": """
<p>À l'oral, les sujets demandent souvent de présenter un projet, donner son avis ou convaincre un interlocuteur.</p>
<p>Une bonne réponse suit une structure simple: annonce du sujet, deux ou trois arguments, exemples personnels, conclusion.</p>
<p>Utilise des connecteurs utiles: d'abord, ensuite, en plus, cependant, c'est pourquoi, pour conclure.</p>
""",
    },
    "ee": {
        "level": "B2",
        "title": "Rédiger une lettre formelle de demande d'information",
        "subtitle": "Sujet écrit fréquent: demander des renseignements, expliquer une situation et formuler une demande polie.",
        "objective": "Maîtriser la structure d'une lettre/courriel formel avec objet, contexte, demande, justification et formule de politesse.",
        "theme": "Lettre formelle, demande d'information et démarches administratives",
        "lesson": """
<p>Les lettres formelles reviennent souvent dans les épreuves écrites: demande d'information, réclamation, inscription, annulation ou explication d'une situation.</p>
<p>Respecte une structure claire: formule d'appel, contexte, demande précise, détails utiles, remerciement et formule de politesse.</p>
<p>Évite les phrases trop familières. Privilégie: Je souhaiterais, Pourriez-vous, Je vous serais reconnaissant de, Dans l'attente de votre réponse.</p>
""",
    },
}


class Command(BaseCommand):
    help = "Crée les packs mensuels CO/CE/EO/EE du mois courant et génère leurs exercices."

    def add_arguments(self, parser):
        parser.add_argument("--month", help="Mois au format YYYY-MM-01. Défaut: mois courant.")
        parser.add_argument("--no-ai", action="store_true", help="Utilise le générateur fallback sans appel IA.")
        parser.add_argument("--force", action="store_true", help="Ajoute des exercices même si le pack en a déjà.")
        parser.add_argument("--replace", action="store_true", help="Supprime les exercices existants du pack avant de régénérer.")

    def handle(self, *args, **options):
        if options.get("month"):
            year, month, day = [int(x) for x in options["month"].split("-")]
            month_date = date(year, month, day)
        else:
            today = date.today()
            month_date = today.replace(day=1)

        total = 0
        for section, data in PACKS.items():
            slug = _pack_slug(month_date, section, data["title"])
            pack, created = MonthlyTrainingPack.objects.update_or_create(
                slug=slug,
                defaults={
                    "language": "fr",
                    "section": section,
                    "level": data["level"],
                    "exam_code": "cecr",
                    "month": month_date,
                    "title": data["title"],
                    "subtitle": data["subtitle"],
                    "objective": data["objective"],
                    "recurring_theme": data["theme"],
                    "lesson_html": data["lesson"],
                    "is_premium": False,
                    "is_published": True,
                    "order": ["co", "ce", "eo", "ee"].index(section),
                },
            )
            if pack.exercises.exists() and not options["force"] and not options["replace"]:
                self.stdout.write(self.style.WARNING(f"{section.upper()} déjà alimenté: {pack.title}"))
                continue

            result = generate_exercises_for_source(
                pack,
                count=6,
                use_ai=not options["no_ai"],
                replace=options["replace"],
            )
            total += result["created"]
            action = "créé" if created else "mis à jour"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{section.upper()} {action}: {pack.title} · {result['created']} exercice(s) · {result['generated_by']}"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Total exercices générés: {total}"))
