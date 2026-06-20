from __future__ import annotations

import re
from datetime import timedelta

from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from preparation_tests.models import CourseExercise, DetailedError


GRAMMAR_HINTS = (
    "accord", "conjug", "temps", "mode", "subjonctif", "conditionnel",
    "pronom", "préposition", "preposition", "article", "genre", "nombre",
    "grammaire", "syntaxe", "participe",
)
LEXICAL_HINTS = (
    "vocab", "lexique", "synonyme", "antonyme", "mot", "expression",
    "registre", "sens", "nuance", "terme",
)
STRATEGY_HINTS = (
    "sauf", "except", "principal", "implicite", "déduire", "deduire",
    "intention", "ton", "objectif", "piège", "piege",
)


def classify_error(exercise: CourseExercise) -> str:
    lesson = exercise.lesson
    text = " ".join([
        lesson.title or "",
        lesson.content_html or "",
        exercise.title or "",
        exercise.instruction or "",
        exercise.question_text or "",
        exercise.summary or "",
    ]).lower()

    def has_any(words):
        return any(w in text for w in words)

    if lesson.section == "eo":
        return "speaking"
    if lesson.section == "ee":
        return "writing"
    if lesson.section == "co":
        if has_any(GRAMMAR_HINTS):
            return "grammar"
        if has_any(LEXICAL_HINTS):
            return "lexical"
        return "listening"
    if has_any(GRAMMAR_HINTS):
        return "grammar"
    if has_any(LEXICAL_HINTS):
        return "lexical"
    if has_any(STRATEGY_HINTS):
        return "strategy"
    return "comprehension"


def option_text(exercise: CourseExercise, option: str) -> str:
    return {
        "A": exercise.option_a,
        "B": exercise.option_b,
        "C": exercise.option_c,
        "D": exercise.option_d,
    }.get((option or "").upper(), "")


def fallback_explanation(exercise: CourseExercise) -> str:
    if exercise.summary:
        return exercise.summary
    correct = (exercise.correct_option or "").upper()
    correct_text = option_text(exercise, correct)
    return (
        f"La bonne réponse est {correct}. {correct_text} "
        "Reprends le document avec la question en tête, repère l'information exacte, "
        "puis élimine les options qui ajoutent une idée absente ou contraire."
    )


def record_detailed_attempt(
    *,
    user,
    exercise: CourseExercise,
    selected: str,
    is_correct: bool,
    source: str = "lesson",
    explanation: str = "",
    category: str = "",
) -> DetailedError | None:
    if not user or not user.is_authenticated:
        return None

    selected = (selected or "").upper()
    correct = (exercise.correct_option or "").upper()
    now = timezone.now()

    existing = DetailedError.objects.filter(user=user, exercise=exercise).first()

    if is_correct:
        if existing:
            apply_review_result(existing, success=True, reviewed_at=now)
        return existing

    err, created = DetailedError.objects.get_or_create(
        user=user,
        exercise=exercise,
        defaults={
            "lesson": exercise.lesson,
            "category": category or classify_error(exercise),
            "source": source,
            "selected_answer": selected,
            "correct_answer": correct,
            "explanation": explanation or fallback_explanation(exercise),
            "occurrences": 1,
            "status": "active",
            "ease_factor": 2.3,
            "interval_days": 1,
            "repetitions": 0,
            "lapses": 1,
            "last_reviewed_at": now,
            "next_review_at": now + timedelta(days=1),
        },
    )

    if not created:
        err.lesson = exercise.lesson
        err.category = category or err.category or classify_error(exercise)
        err.source = source or err.source
        err.selected_answer = selected
        err.correct_answer = correct
        err.explanation = explanation or err.explanation or fallback_explanation(exercise)
        err.occurrences = (err.occurrences or 0) + 1
        err.status = "active"
        err.repetitions = 0
        err.lapses = (err.lapses or 0) + 1
        err.ease_factor = max(1.3, (err.ease_factor or 2.5) - 0.2)
        err.interval_days = 1
        err.last_reviewed_at = now
        err.next_review_at = now + timedelta(days=1)
        err.save()

    return err


def apply_review_result(error: DetailedError, *, success: bool, reviewed_at=None) -> DetailedError:
    now = reviewed_at or timezone.now()
    error.last_reviewed_at = now

    if success:
        reps = (error.repetitions or 0) + 1
        ease = min(3.0, (error.ease_factor or 2.5) + 0.08)
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 3
        else:
            interval = max(4, round((error.interval_days or 1) * ease))

        error.repetitions = reps
        error.ease_factor = ease
        error.interval_days = interval
        error.next_review_at = now + timedelta(days=interval)
        if reps >= 3:
            error.status = "resolved"
    else:
        error.status = "active"
        error.repetitions = 0
        error.lapses = (error.lapses or 0) + 1
        error.ease_factor = max(1.3, (error.ease_factor or 2.5) - 0.2)
        error.interval_days = 1
        error.next_review_at = now + timedelta(days=1)

    error.save()
    return error


def due_errors(user, limit: int = 30):
    now = timezone.now()
    return (
        DetailedError.objects.filter(user=user, status="active")
        .select_related("exercise", "lesson")
        .annotate(
            due_rank=Case(
                When(next_review_at__lte=now, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("due_rank", "next_review_at", "-occurrences", "-lapses")[:limit]
    )


def error_stats(user) -> dict:
    errors = DetailedError.objects.filter(user=user, status="active")
    by_category = {}
    for code, label in DetailedError.CATEGORY_CHOICES:
        count = errors.filter(category=code).count()
        if count:
            by_category[code] = {"label": label, "count": count}

    due_count = errors.filter(next_review_at__lte=timezone.now()).count()
    return {
        "active": errors.count(),
        "due": due_count,
        "by_category": by_category,
    }


def normalize_text_for_category(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
