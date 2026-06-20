"""
Examens blancs par niveau CECR (A1→C2).

Flow :
    GET  /fr/examen-blanc/           → level_mock_hub   (choisir le niveau)
    GET  /fr/examen-blanc/<level>/   → level_mock_exam  (afficher l'examen)
    POST /fr/examen-blanc/<level>/   → level_mock_exam  (corriger + résultats)

Contenu :
    CO + CE : exercices MCQ auto-corrigés (correct_option)
    EO + EE : sujets affichés en pratique libre (v1 — sans scoring IA)

Aucun nouveau modèle, aucune migration.
"""
from __future__ import annotations

import json
import random

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.timezone import localtime

from .models import CourseLesson, CourseExercise, MockExamResult, UserExerciseProgress
from preparation_tests.services.error_revision import record_detailed_attempt

# Niveaux CECR valides
VALID_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

# Niveau CECR suivant (pour CTA "passer au niveau supérieur")
NEXT_LEVEL = {
    "A1": "A2",
    "A2": "B1",
    "B1": "B2",
    "B2": "C1",
    "C1": "C2",
    "C2": None,
}

# Estimation CECR à partir du score global (CO+CE)
def _estimate_cefr(score: int) -> str:
    if score >= 90:
        return "C1–C2"
    if score >= 75:
        return "B2–C1"
    if score >= 60:
        return "B1–B2"
    if score >= 40:
        return "A2–B1"
    return "A1–A2"


def _option_text(exercise: CourseExercise, option: str) -> str:
    return {
        "A": exercise.option_a,
        "B": exercise.option_b,
        "C": exercise.option_c,
        "D": exercise.option_d,
    }.get((option or "").upper(), "")


def _explanation(exercise: CourseExercise) -> str:
    if exercise.summary:
        return exercise.summary
    correct = (exercise.correct_option or "").upper()
    return (
        f"La bonne réponse est {correct}. {_option_text(exercise, correct)} "
        "car cette option reprend l'information réellement portée par le document. "
        "Pour progresser, repère le mot-clé de la question, retrouve son équivalent "
        "dans le texte ou l'audio, puis élimine les options trop larges ou contradictoires."
    )


def _remember_attempt(user, exercise: CourseExercise, answer: str, is_correct: bool) -> None:
    if not user.is_authenticated:
        return
    prog, _ = UserExerciseProgress.objects.get_or_create(
        user=user,
        exercise=exercise,
        defaults={"lesson": exercise.lesson},
    )
    if prog.lesson_id != exercise.lesson_id:
        prog.lesson = exercise.lesson
    prog.mark_attempt(selected=answer, correct=is_correct)
    prog.save()
    record_detailed_attempt(
        user=user,
        exercise=exercise,
        selected=answer,
        is_correct=is_correct,
        source="level_mock",
        explanation=_explanation(exercise),
    )


def _skill_cards(score_co, co_correct, co_total, score_ce, ce_correct, ce_total) -> list:
    cards = []
    if score_co is not None:
        cards.append({
            "code": "CO",
            "label": "Compréhension orale",
            "pct": score_co,
            "correct": co_correct,
            "total": co_total,
            "cefr": _estimate_cefr(score_co),
        })
    if score_ce is not None:
        cards.append({
            "code": "CE",
            "label": "Compréhension écrite",
            "pct": score_ce,
            "correct": ce_correct,
            "total": ce_total,
            "cefr": _estimate_cefr(score_ce),
        })
    cards.extend([
        {"code": "EO", "label": "Expression orale", "pct": None, "correct": None, "total": None, "cefr": "À évaluer par IA"},
        {"code": "EE", "label": "Expression écrite", "pct": None, "correct": None, "total": None, "cefr": "À évaluer par IA"},
    ])
    return cards


def _get_level_data(level: str) -> dict:
    """
    Sélectionne aléatoirement les leçons et exercices pour un niveau donné.
    Retourne un dict utilisable dans GET et POST.
    """
    def pick_lesson(section):
        lessons = list(
            CourseLesson.objects.filter(
                section=section, level=level, is_published=True
            )
        )
        return random.choice(lessons) if lessons else None

    co_lesson = pick_lesson("co")
    ce_lesson = pick_lesson("ce")

    co_exercises = list(
        CourseExercise.objects.filter(
            lesson=co_lesson, is_active=True
        ).order_by("order")[:5]
    ) if co_lesson else []

    ce_exercises = list(
        CourseExercise.objects.filter(
            lesson=ce_lesson, is_active=True
        ).order_by("order")[:5]
    ) if ce_lesson else []

    # EO : 2 sujets distincts
    eo_qs = list(
        CourseLesson.objects.filter(
            section="eo", level=level, is_published=True
        )
    )
    eo_lessons = random.sample(eo_qs, min(2, len(eo_qs)))

    # EO exercises (1 par leçon — le sujet)
    eo_items = []
    for lesson in eo_lessons:
        ex = lesson.exercises.filter(is_active=True).first()
        if ex:
            eo_items.append({"lesson": lesson, "exercise": ex})

    # EE : 1 sujet
    ee_lesson = pick_lesson("ee")
    ee_exercise = None
    if ee_lesson:
        ee_exercise = ee_lesson.exercises.filter(is_active=True).first()

    return {
        "co_lesson": co_lesson,
        "co_exercises": co_exercises,
        "ce_lesson": ce_lesson,
        "ce_exercises": ce_exercises,
        "eo_items": eo_items,
        "ee_lesson": ee_lesson,
        "ee_exercise": ee_exercise,
    }


# ============================================================
# VUE 1 — HUB : choisir le niveau
# ============================================================
@login_required
def level_mock_hub(request):
    levels_data = []
    for lv in VALID_LEVELS:
        co_count = CourseLesson.objects.filter(section="co", level=lv, is_published=True).count()
        ce_count = CourseLesson.objects.filter(section="ce", level=lv, is_published=True).count()
        eo_count = CourseLesson.objects.filter(section="eo", level=lv, is_published=True).count()
        ee_count = CourseLesson.objects.filter(section="ee", level=lv, is_published=True).count()
        levels_data.append({
            "level": lv,
            "co_count": co_count,
            "ce_count": ce_count,
            "eo_count": eo_count,
            "ee_count": ee_count,
            "has_mcq": co_count > 0 or ce_count > 0,
        })

    return render(request, "preparation_tests/level_mock_hub.html", {
        "levels": levels_data,
    })


# ============================================================
# VUE 2 — EXAMEN : GET affiche le form, POST corrige
# ============================================================
@login_required
def level_mock_exam(request, level: str):
    level = level.upper()
    if level not in VALID_LEVELS:
        raise Http404(f"Niveau invalide : {level}")

    # ── POST : correction ────────────────────────────────────
    if request.method == "POST":
        # Reconstruire les exercices depuis les IDs cachés
        co_ids = request.POST.getlist("co_exercise_ids")
        ce_ids = request.POST.getlist("ce_exercise_ids")

        co_exercises = list(CourseExercise.objects.filter(id__in=co_ids).order_by("order"))
        ce_exercises = list(CourseExercise.objects.filter(id__in=ce_ids).order_by("order"))

        # Correction CO
        co_results = []
        co_correct = 0
        for ex in co_exercises:
            submitted = request.POST.get(f"co_{ex.id}", "")
            is_correct = submitted == ex.correct_option
            if is_correct:
                co_correct += 1
            _remember_attempt(request.user, ex, submitted, is_correct)
            co_results.append({
                "exercise": ex,
                "submitted": submitted,
                "is_correct": is_correct,
                "correct_option": ex.correct_option,
                "correct_text": _option_text(ex, ex.correct_option),
                "answer_text": _option_text(ex, submitted),
                "explanation": _explanation(ex),
            })

        # Correction CE
        ce_results = []
        ce_correct = 0
        for ex in ce_exercises:
            submitted = request.POST.get(f"ce_{ex.id}", "")
            is_correct = submitted == ex.correct_option
            if is_correct:
                ce_correct += 1
            _remember_attempt(request.user, ex, submitted, is_correct)
            ce_results.append({
                "exercise": ex,
                "submitted": submitted,
                "is_correct": is_correct,
                "correct_option": ex.correct_option,
                "correct_text": _option_text(ex, ex.correct_option),
                "answer_text": _option_text(ex, submitted),
                "explanation": _explanation(ex),
            })

        # Scores
        score_co = round(co_correct / len(co_exercises) * 100) if co_exercises else None
        score_ce = round(ce_correct / len(ce_exercises) * 100) if ce_exercises else None

        scored = [s for s in [score_co, score_ce] if s is not None]
        score_global = round(sum(scored) / len(scored)) if scored else None

        cefr_estimate = _estimate_cefr(score_global) if score_global is not None else "—"
        next_level = NEXT_LEVEL.get(level)

        # ── Sauvegarde du résultat ────────────────────────────
        if request.user.is_authenticated:
            MockExamResult.objects.create(
                user=request.user,
                level=level,
                score_co=score_co,
                score_ce=score_ce,
                score_global=score_global,
                co_correct=co_correct,
                co_total=len(co_exercises),
                ce_correct=ce_correct,
                ce_total=len(ce_exercises),
                cefr_estimate=cefr_estimate,
            )

        # EO/EE depuis les IDs cachés
        eo_lesson_ids = request.POST.getlist("eo_lesson_ids")
        eo_exercise_ids = request.POST.getlist("eo_exercise_ids")
        ee_lesson_id = request.POST.get("ee_lesson_id")
        ee_exercise_id = request.POST.get("ee_exercise_id")

        eo_items = []
        for lid, eid in zip(eo_lesson_ids, eo_exercise_ids):
            try:
                lesson = CourseLesson.objects.get(id=lid)
                exercise = CourseExercise.objects.get(id=eid)
                eo_items.append({"lesson": lesson, "exercise": exercise})
            except (CourseLesson.DoesNotExist, CourseExercise.DoesNotExist):
                pass

        ee_lesson = None
        ee_exercise = None
        if ee_lesson_id:
            try:
                ee_lesson = CourseLesson.objects.get(id=ee_lesson_id)
            except CourseLesson.DoesNotExist:
                pass
        if ee_exercise_id:
            try:
                ee_exercise = CourseExercise.objects.get(id=ee_exercise_id)
            except CourseExercise.DoesNotExist:
                pass

        return render(request, "preparation_tests/level_mock_results.html", {
            "level": level,
            "next_level": next_level,
            "co_results": co_results,
            "co_correct": co_correct,
            "co_total": len(co_exercises),
            "score_co": score_co,
            "ce_results": ce_results,
            "ce_correct": ce_correct,
            "ce_total": len(ce_exercises),
            "score_ce": score_ce,
            "score_global": score_global,
            "cefr_estimate": cefr_estimate,
            "skill_cards": _skill_cards(
                score_co, co_correct, len(co_exercises),
                score_ce, ce_correct, len(ce_exercises),
            ),
            "eo_items": eo_items,
            "ee_lesson": ee_lesson,
            "ee_exercise": ee_exercise,
        })

    # ── GET : afficher l'examen ──────────────────────────────
    data = _get_level_data(level)
    return render(request, "preparation_tests/level_mock_exam.html", {
        "level": level,
        **data,
    })


# ============================================================
# VUE 3 — HISTORIQUE + COURBE DE PROGRESSION
# ============================================================
@login_required
def mock_exam_history(request):
    """
    Historique complet des examens blancs de l'utilisateur
    + données Chart.js pour courbe multi-niveaux.
    """
    results = MockExamResult.objects.filter(user=request.user)

    # Données Chart.js — une série par niveau, ordonnée par date
    chart_datasets = {}
    for lv in VALID_LEVELS:
        qs = results.filter(level=lv, score_global__isnull=False).order_by("taken_at")
        if qs.exists():
            chart_datasets[lv] = [
                {
                    "x": localtime(r.taken_at).strftime("%d/%m"),
                    "y": r.score_global,
                }
                for r in qs
            ]

    return render(request, "preparation_tests/mock_exam_history.html", {
        "results": results,
        "chart_datasets_json": json.dumps(chart_datasets),
        "total_count": results.count(),
    })
