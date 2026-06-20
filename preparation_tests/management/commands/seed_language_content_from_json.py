import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from EnglishPrepApp.models import EnglishQuestion, EnglishTest
from GermanPrepApp.models import GermanExam, GermanExercise, GermanLesson
from italian_courses.models import Choice, CourseCategory, Lesson, Question, Quiz
from italian_courses.sanitizer import sanitize_html
from preparation_tests.models import CourseExercise, CourseLesson


BASE_DIR = Path("data/lessons_json")
LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}


GERMAN_EXAM_LABELS = {
    "GOETHE": "Goethe-Zertifikat",
    "TELC": "telc Deutsch",
    "TESTDAF": "TestDaF",
    "DSH": "DSH",
    "GENERAL": "Général / Visa",
    "INTEGRATION": "Test d'intégration",
}


def _cut(value, limit: int) -> str:
    return str(value or "")[:limit]


class Command(BaseCommand):
    help = "Importe les contenus langue depuis data/lessons_json vers les apps existantes."

    def add_arguments(self, parser):
        parser.add_argument("--dir", default=str(BASE_DIR), help="Dossier contenant les JSON.")
        parser.add_argument("--language", choices=["all", "en", "de", "it", "fr"], default="all")
        parser.add_argument("--clear", action="store_true", help="Supprime les contenus importés avant import.")

    @transaction.atomic
    def handle(self, *args, **options):
        root = Path(options["dir"])
        if not root.exists():
            raise CommandError(f"Dossier introuvable: {root}")

        language = options["language"]
        if options["clear"]:
            self._clear(language)

        totals = {"en": 0, "de": 0, "it": 0, "fr": 0}

        if language in {"all", "en"}:
            for path in sorted(root.glob("en_*.json")):
                totals["en"] += self._import_english(path)

        if language in {"all", "de"}:
            for path in sorted(root.glob("de_*.json")):
                totals["de"] += self._import_german(path)

        if language in {"all", "it"}:
            for path in sorted(root.glob("it_*.json")):
                totals["it"] += self._import_italian(path)

        if language in {"all", "fr"}:
            for path in sorted(list(root.glob("ce_*.json")) + list(root.glob("ee_*.json")) + list(root.glob("eo_*.json"))):
                totals["fr"] += self._import_french(path)

        self.stdout.write(self.style.SUCCESS(f"Import terminé: {totals}"))

    def _read(self, path: Path):
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _clear(self, language: str):
        if language in {"all", "en"}:
            EnglishTest.objects.all().delete()
        if language in {"all", "de"}:
            GermanExam.objects.all().delete()
        if language in {"all", "it"}:
            CourseCategory.objects.all().delete()
        if language in {"all", "fr"}:
            CourseLesson.objects.filter(locale="fr").delete()
        self.stdout.write(self.style.WARNING(f"Contenus supprimés pour: {language}"))

    def _import_english(self, path: Path) -> int:
        data = self._read(path)
        created = 0
        for item in data.get("tests", []):
            level = (item.get("level") or "").upper()
            if level not in LEVELS:
                continue
            exam_type = (item.get("exam_type") or "GENERAL").upper()
            name = (item.get("name") or f"English {level}").strip()
            test, _ = EnglishTest.objects.update_or_create(
                name=name[:255],
                defaults={
                    "description": item.get("description", ""),
                    "exam_type": exam_type if exam_type in {"GENERAL", "IELTS", "TOEFL", "TOEIC"} else "GENERAL",
                    "level": level,
                    "duration_minutes": int(item.get("duration_minutes") or 20),
                    "is_active": bool(item.get("is_active", True)),
                },
            )
            test.questions.all().delete()
            for q in item.get("questions", []):
                correct = (q.get("correct_option") or "A").upper()
                if correct not in {"A", "B", "C", "D"}:
                    correct = "A"
                EnglishQuestion.objects.create(
                    test=test,
                    skill=(q.get("skill") or "USE_OF_ENGLISH").upper(),
                    question_text=q.get("question_text") or q.get("prompt") or "",
                    option_a=_cut(q.get("option_a"), 255),
                    option_b=_cut(q.get("option_b"), 255),
                    option_c=_cut(q.get("option_c"), 255),
                    option_d=_cut(q.get("option_d"), 255),
                    correct_option=correct,
                    explanation=q.get("explanation") or q.get("summary") or "",
                    audio_url=_cut(q.get("audio_url"), 200),
                )
            created += 1
        self.stdout.write(f"EN {path.name}: {created} test(s)")
        return created

    def _get_german_exam(self, level: str, exam_type: str) -> GermanExam:
        exam_type = exam_type if exam_type in GERMAN_EXAM_LABELS else "GOETHE"
        label = GERMAN_EXAM_LABELS[exam_type]
        exam, _ = GermanExam.objects.get_or_create(
            slug=slugify(f"{exam_type}-{level}"),
            defaults={
                "title": f"{label} {level}",
                "short_description": f"Préparation {label} niveau {level}.",
                "description": f"Cours, exercices et vocabulaire pour {label} {level}.",
                "exam_type": exam_type,
                "level": level,
                "is_active": True,
            },
        )
        return exam

    def _import_german(self, path: Path) -> int:
        data = self._read(path)
        if not isinstance(data, list):
            return 0
        created = 0
        for idx, item in enumerate(data, start=1):
            level = (item.get("level") or "").upper()
            if level not in LEVELS:
                continue
            exam = self._get_german_exam(level, (item.get("exam_type") or "GOETHE").upper())
            title = item.get("title") or f"Leçon {idx}"
            lesson, _ = GermanLesson.objects.update_or_create(
                exam=exam,
                title=title[:255],
                defaults={
                    "skill": (item.get("skill") or "GRAMMATIK").upper(),
                    "order": GermanLesson.objects.filter(exam=exam).count() + 1,
                    "intro": item.get("intro", "")[:500],
                    "content": item.get("content", ""),
                },
            )
            lesson.exercises.all().delete()
            for ex in item.get("exercises", []):
                correct = (ex.get("correct_option") or "A").upper()
                GermanExercise.objects.create(
                    lesson=lesson,
                    question_text=ex.get("question_text") or "",
                    option_a=_cut(ex.get("option_a"), 255),
                    option_b=_cut(ex.get("option_b"), 255),
                    option_c=_cut(ex.get("option_c"), 255),
                    option_d=_cut(ex.get("option_d"), 255),
                    correct_option=correct if correct in {"A", "B", "C", "D"} else "A",
                    explanation=ex.get("explanation") or "",
                )
            created += 1
        self.stdout.write(f"DE {path.name}: {created} leçon(s)")
        return created

    def _import_italian(self, path: Path) -> int:
        data = self._read(path)
        cat_map = {}
        for cat in data.get("categories", []):
            category, _ = CourseCategory.objects.update_or_create(
                slug=cat["slug"],
                defaults={"name": cat.get("name", cat["slug"]), "is_active": True},
            )
            cat_map[category.slug] = category

        count = 0
        for item in data.get("lessons", []):
            category = cat_map.get(item.get("category_slug"))
            if not category:
                continue
            lesson, _ = Lesson.objects.update_or_create(
                category=category,
                slug=item.get("slug") or slugify(item.get("title", "")),
                defaults={
                    "title": item.get("title", "Leçon")[:200],
                    "content_html": sanitize_html(item.get("content_html", "")),
                    "transcript": item.get("excerpt", ""),
                    "is_published": bool(item.get("is_published", True)),
                    "order": int(item.get("order_index", item.get("order", 1)) or 1),
                    "estimated_minutes": int(item.get("estimated_minutes", 10) or 10),
                },
            )
            quiz_data = item.get("quiz") or {}
            if quiz_data:
                quiz, _ = Quiz.objects.update_or_create(
                    lesson=lesson,
                    defaults={"title": quiz_data.get("title", "Quiz"), "is_active": bool(quiz_data.get("is_active", True))},
                )
                quiz.questions.all().delete()
                for q_index, q in enumerate(quiz_data.get("questions", []), start=1):
                    question = Question.objects.create(
                        quiz=quiz,
                        prompt=q.get("prompt", ""),
                        explanation=q.get("explanation", ""),
                        order=int(q.get("order_index", q_index) or q_index),
                    )
                    for c_index, choice in enumerate(q.get("choices", []), start=1):
                        Choice.objects.create(
                            question=question,
                            text=choice.get("text", ""),
                            is_correct=bool(choice.get("is_correct", False)),
                            order=c_index,
                        )
            count += 1
        self.stdout.write(f"IT {path.name}: {count} leçon(s)")
        return count

    def _import_french(self, path: Path) -> int:
        data = self._read(path)
        if isinstance(data, list):
            skill = path.name[:2].lower()
            parts = path.stem.split("_")
            level = next((p.upper() for p in parts if p.upper() in LEVELS), "A1")
            lessons = data
        else:
            skill = (data.get("skill") or path.name[:2]).lower()
            level = (data.get("level") or "A1").upper()
            lessons = data.get("lessons", [])
        count = 0
        for index, item in enumerate(lessons, start=1):
            title = item.get("title") or item.get("topic") or f"{skill.upper()} {level} - Leçon {index}"
            content = item.get("reading_text") or ""
            if skill == "ee":
                content = (
                    f"<p><strong>Consigne:</strong> {item.get('instructions', '')}</p>"
                    f"<p><strong>Minimum:</strong> {item.get('min_words', '')} mots</p>"
                    f"<pre>{item.get('sample_answer', '')}</pre>"
                )
            elif skill == "eo":
                points = "".join(f"<li>{p}</li>" for p in item.get("expected_points", []))
                content = f"<p>{item.get('instructions', '')}</p><ul>{points}</ul>"
            lesson, _ = CourseLesson.objects.update_or_create(
                slug=slugify(f"fr-{skill}-{level}-{path.stem}-{index}")[:50],
                defaults={
                    "section": skill if skill in {"ce", "co", "ee", "eo"} else "ce",
                    "level": level,
                    "title": title[:255],
                    "locale": "fr",
                    "content_html": content,
                    "order": index,
                    "is_published": True,
                },
            )
            lesson.exercises.all().delete()
            for q_index, q in enumerate(item.get("questions", []), start=1):
                correct = (q.get("correct_option") or "A").upper()
                CourseExercise.objects.create(
                    lesson=lesson,
                    title=f"Question {q_index}",
                    instruction=item.get("reading_text") or item.get("instructions", ""),
                    question_text=q.get("question_text") or q.get("question") or "",
                    option_a=_cut(q.get("option_a"), 255),
                    option_b=_cut(q.get("option_b"), 255),
                    option_c=_cut(q.get("option_c"), 255),
                    option_d=_cut(q.get("option_d"), 255),
                    correct_option=correct if correct in {"A", "B", "C", "D"} else "A",
                    summary=q.get("summary") or q.get("explanation") or "",
                    order=q_index,
                    is_active=True,
                )
            count += 1
        self.stdout.write(f"FR {path.name}: {count} leçon(s)")
        return count
