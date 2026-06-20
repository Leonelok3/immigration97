from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from preparation_tests.services.daily_content_agent import DailyContentAgent


class Command(BaseCommand):
    help = "Publie les leçons/exercices du jour et prépare les examens blancs du dimanche sans appel OpenAI."

    def add_arguments(self, parser):
        parser.add_argument("--date", default="", help="Date YYYY-MM-DD. Défaut: aujourd'hui.")
        parser.add_argument("--level", default="B1", help="Niveau CECR pour les contenus français du jour.")
        parser.add_argument("--no-weekly-mock", action="store_true", help="Ne crée pas les examens blancs du dimanche.")

    def handle(self, *args, **options):
        if options["date"]:
            today = datetime.strptime(options["date"], "%Y-%m-%d").date()
        else:
            today = timezone.localdate()

        agent = DailyContentAgent(today=today)
        level = options["level"].strip().upper()

        packs = agent.build_french_daily_packs(level=level)
        self.stdout.write(self.style.SUCCESS(f"Leçons du jour FR: {len(packs)} pack(s) publié(s)."))
        for pack in packs:
            self.stdout.write(f"  - {pack.section.upper()} {pack.level}: {pack.title} ({pack.exercises.count()} exercice(s))")

        if options["no_weekly_mock"]:
            return

        subjects = agent.build_sunday_french_mock_subjects(level=level)
        if today.weekday() == 6:
            self.stdout.write(self.style.SUCCESS(f"Examens blancs du dimanche: {len(subjects)} sujet(s) publié(s)."))
            for subject in subjects:
                self.stdout.write(f"  - {subject.section.upper()} {subject.level}: {subject.title}")
        else:
            self.stdout.write("Pas dimanche: aucun examen blanc hebdomadaire créé.")
