from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from django.template.defaultfilters import slugify
from django.utils import timezone

from preparation_tests.models import CourseExercise, CourseLesson, MonthlyTrainingPack, PastExamSubject


SECTION_LABELS = {
    "co": "Compréhension orale",
    "ce": "Compréhension écrite",
    "eo": "Expression orale",
    "ee": "Expression écrite",
}


@dataclass(frozen=True)
class DailySelection:
    language: str
    section: str
    level: str
    lesson: object | None
    exercises: list[object]
    title: str
    empty_reason: str = ""


class DailyContentAgent:
    """Local content agent fed only by existing database lessons/exercises."""

    def __init__(self, today: date | None = None) -> None:
        self.today = today or timezone.localdate()

    def select_french_lesson(self, section: str, level: str = "B1") -> DailySelection:
        lessons = CourseLesson.objects.filter(
            locale="fr",
            section=section,
            level=level,
            is_published=True,
        ).prefetch_related("exercises").order_by("order", "id")
        lesson = self._pick(lessons)
        if not lesson:
            return DailySelection("fr", section, level, None, [], SECTION_LABELS.get(section, section), "Aucune leçon française publiée.")
        exercises = list(lesson.exercises.filter(is_active=True).order_by("order", "id")[:6])
        return DailySelection("fr", section, level, lesson, exercises, lesson.title)

    def select_english_lesson(self, section: str = "", level: str = "") -> DailySelection:
        from EnglishPrepApp.models import EnglishExercise, EnglishLesson, SkillArea

        skill_map = {
            "co": SkillArea.LISTENING,
            "ce": SkillArea.READING,
            "ee": SkillArea.WRITING,
            "eo": SkillArea.SPEAKING,
        }
        qs = EnglishLesson.objects.select_related("test").prefetch_related("exercises").order_by("skill", "order", "id")
        if section:
            qs = qs.filter(skill=skill_map.get(section.lower(), section))
        if level:
            qs = qs.filter(level__iexact=level)
        lesson = self._pick(qs)
        if not lesson:
            return DailySelection("en", section or "all", level or "", None, [], "English daily lesson", "Aucune leçon anglaise disponible.")
        exercises = list(EnglishExercise.objects.filter(lesson=lesson).order_by("order", "id")[:6])
        return DailySelection("en", section or lesson.skill, lesson.level or getattr(lesson.test, "level", ""), lesson, exercises, lesson.title)

    def select_german_lesson(self, section: str = "", level: str = "") -> DailySelection:
        from GermanPrepApp.models import GermanExercise, GermanLesson

        skill_map = {
            "co": "HOREN",
            "ce": "LESEN",
            "ee": "SCHREIBEN",
            "eo": "SPRECHEN",
        }
        qs = GermanLesson.objects.select_related("exam").prefetch_related("exercises").order_by("skill", "order", "id")
        if section:
            qs = qs.filter(skill=skill_map.get(section.lower(), section.upper()))
        if level:
            qs = qs.filter(exam__level=level.upper())
        lesson = self._pick(qs)
        if not lesson:
            return DailySelection("de", section or "all", level or "", None, [], "Deutsch Tageslektion", "Aucune leçon allemande disponible.")
        exercises = list(GermanExercise.objects.filter(lesson=lesson).order_by("id")[:6])
        return DailySelection("de", section or lesson.skill, lesson.exam.level, lesson, exercises, lesson.title)

    def build_french_daily_packs(self, level: str = "B1", sections: Iterable[str] = ("co", "ce", "eo", "ee")) -> list[MonthlyTrainingPack]:
        packs: list[MonthlyTrainingPack] = []
        for order, section in enumerate(sections):
            selection = self.select_french_lesson(section, level=level)
            if not selection.lesson:
                continue
            existing_pack = MonthlyTrainingPack.objects.filter(
                language="fr",
                section=section,
                level=level,
                exam_code="cecr",
                month=self.today,
            ).first()
            slug = existing_pack.slug if existing_pack else self._unique_pack_slug(f"jour-{self.today:%Y%m%d}-{section}-{level}")
            pack, _ = MonthlyTrainingPack.objects.update_or_create(
                language="fr",
                section=section,
                level=level,
                exam_code="cecr",
                month=self.today,
                defaults={
                    "title": f"Leçon du jour {section.upper()} - {selection.lesson.title}",
                    "slug": slug,
                    "subtitle": f"Entraînement quotidien {SECTION_LABELS.get(section, section)}.",
                    "objective": "Réviser une leçon ciblée et faire les exercices associés du jour.",
                    "lesson_html": selection.lesson.content_html,
                    "recurring_theme": selection.lesson.title[:220],
                    "related_lesson": selection.lesson,
                    "is_premium": False,
                    "is_published": True,
                    "order": order,
                },
            )
            if selection.exercises:
                pack.exercises.set(selection.exercises)
            packs.append(pack)
        return packs

    def build_sunday_french_mock_subjects(self, level: str = "B1") -> list[PastExamSubject]:
        if self.today.weekday() != 6:
            return []

        subjects: list[PastExamSubject] = []
        for order, section in enumerate(("co", "ce", "eo", "ee")):
            selection = self.select_french_lesson(section, level=level)
            if not selection.lesson:
                continue
            slug = self._unique_subject_slug(f"examen-blanc-{self.today:%Y%m%d}-{section}-{level}")
            subject, _ = PastExamSubject.objects.update_or_create(
                language="fr",
                exam_code="cecr",
                section=section,
                level=level,
                slug=slug,
                defaults={
                    "title": f"Examen blanc du dimanche {section.upper()} - {level}",
                    "source_label": f"Programme hebdomadaire Immigration97 - {self.today:%d/%m/%Y}",
                    "recurring_theme": selection.lesson.title[:220],
                    "frequency_score": 80,
                    "subject_html": selection.lesson.content_html,
                    "correction_html": "Correction issue des exercices corrigés liés à la leçon.",
                    "related_lesson": selection.lesson,
                    "is_premium": False,
                    "is_published": True,
                    "order": order,
                },
            )
            if selection.exercises:
                subject.exercises.set(selection.exercises)
            subjects.append(subject)
        return subjects

    def _pick(self, queryset):
        count = queryset.count()
        if count == 0:
            return None
        index = self.today.toordinal() % count
        return queryset[index]

    def _unique_pack_slug(self, base: str) -> str:
        return self._unique_slug(base, MonthlyTrainingPack)

    def _unique_subject_slug(self, base: str) -> str:
        return self._unique_slug(base, PastExamSubject)

    def _unique_slug(self, base: str, model) -> str:
        raw = slugify(base)[:42] or "contenu-du-jour"
        candidate = raw
        suffix = 2
        while model.objects.filter(slug=candidate).exists():
            candidate = f"{raw}-{suffix}"
            suffix += 1
        return candidate
