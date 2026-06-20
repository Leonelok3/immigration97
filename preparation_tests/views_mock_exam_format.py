"""
Examens blancs format officiel : TEF Canada, TCF Canada, DELF (A1-B2), DALF (C1-C2).

Expert config basée sur les formats réels :
  - TEF Canada  : 60 CO (40 min) + 50 CE (60 min) → score 0-450/section → CECR
  - TCF Canada  : 29 CO (25 min) + 29 CE (45 min) → score 0-699/section → CECR
  - DELF A1-B2  : CO+CE variables → score /25 par épreuve (seuil 50/100 + 5/25)
  - DALF C1-C2  : CO+CE 20q chacun → score /25 par épreuve

Format entraînement (CO réduit pour ne pas dépasser les exercices disponibles,
timing respecté pour simuler les conditions réelles).

URLs :
    GET /prep/fr/tef/examen/          → exam_format_hub("tef")
    GET /prep/fr/tef/examen/<level>/  → exam_format_exam("tef", level)
    POST                               → correction
    (même pattern : tcf, delf, dalf)
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from billing.decorators import subscription_required

from .models import CourseLesson, CourseExercise, ExamFormatResult, UserExerciseProgress
from preparation_tests.services.error_revision import (
    due_errors,
    error_stats,
    record_detailed_attempt,
)

# ─── CONFIGURATION OFFICIELLE PAR EXAMEN ──────────────────────────────────────

EXAM_CONFIGS: dict = {
    "tef": {
        "name": "TEF Canada",
        "full_name": "Test d'Évaluation de Français — Canada",
        "badge": "⏱ TEF Canada",
        "levels": ["A1", "A2", "B1", "B2", "C1", "C2"],
        # Entraînement: 20 CO + 15 CE (réel: 60 CO + 50 CE)
        "co_count": 20, "ce_count": 15,
        "co_min": 20, "ce_min": 20,
        "eo_count": 1, "ee_count": 1,
        "eo_min": 15, "ee_min": 60,
        "score_type": "tef",
        "note": "Format entraînement (TEF réel : 60 CO / 50 CE). Score 0–450 par section.",
        "timer_sec_co": 40,   # secondes simulées par question CO
        "timer_sec_ce": 90,   # secondes simulées par question CE
    },
    "tcf": {
        "name": "TCF Canada",
        "full_name": "Test de Connaissance du Français — Canada",
        "badge": "⏱ TCF Canada",
        "levels": ["A1", "A2", "B1", "B2", "C1", "C2"],
        # Format réel : 29 CO + 29 CE (adaptatif simulé)
        "co_count": 29, "ce_count": 29,
        "co_min": 25, "ce_min": 45,
        "eo_count": 1, "ee_count": 2,
        "eo_min": 12, "ee_min": 60,
        "score_type": "tcf",
        "note": "Format réel TCF Canada (29 CO + 29 CE, adaptatif simulé). Score 0–699 par section.",
        "timer_sec_co": 52,   # 25 min / 29 questions
        "timer_sec_ce": 93,   # 45 min / 29 questions
    },
    "delf": {
        "name": "DELF",
        "full_name": "Diplôme d'Études en Langue Française",
        "badge": "🎓 DELF",
        "levels": ["A1", "A2", "B1", "B2"],
        "level_config": {
            "A1": {"co_count": 10, "ce_count": 10, "co_min": 20, "ce_min": 35},
            "A2": {"co_count": 10, "ce_count": 15, "co_min": 25, "ce_min": 45},
            "B1": {"co_count": 15, "ce_count": 20, "co_min": 25, "ce_min": 45},
            "B2": {"co_count": 20, "ce_count": 25, "co_min": 30, "ce_min": 60},
        },
        "eo_count": 1, "ee_count": 1,
        "eo_min": 10, "ee_min": 45,
        "score_type": "delf",
        "note": "Score /25 par épreuve (100 total). Seuil : 50/100 + min 5/25 par épreuve.",
        "timer_sec_co": 120,
        "timer_sec_ce": 180,
    },
    "dalf": {
        "name": "DALF",
        "full_name": "Diplôme Approfondi de Langue Française",
        "badge": "🎓 DALF",
        "levels": ["C1", "C2"],
        "level_config": {
            "C1": {"co_count": 20, "ce_count": 20, "co_min": 40, "ce_min": 60},
            "C2": {"co_count": 20, "ce_count": 20, "co_min": 40, "ce_min": 60},
        },
        "eo_count": 1, "ee_count": 1,
        "eo_min": 30, "ee_min": 150,
        "score_type": "dalf",
        "note": "Score /25 par épreuve (100 total). Seuil : 50/100 + min 5/25 par épreuve.",
        "timer_sec_co": 120,
        "timer_sec_ce": 180,
    },
}

# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _cfg_for_level(exam_code: str, level: str) -> dict:
    """Merge exam config + level-specific overrides."""
    cfg = dict(EXAM_CONFIGS[exam_code])
    if "level_config" in cfg and level in cfg["level_config"]:
        cfg.update(cfg["level_config"][level])
    return cfg


def _pick_exercises(section: str, level: str, count: int) -> list:
    """Pick `count` random active exercises from all lessons of this section/level."""
    all_exs = list(
        CourseExercise.objects.filter(
            lesson__section=section,
            lesson__level=level,
            lesson__is_published=True,
            is_active=True,
        ).select_related("lesson")
    )
    random.shuffle(all_exs)
    return all_exs[:count]


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
    correct_text = _option_text(exercise, correct)
    lesson_title = exercise.lesson.title if exercise.lesson_id else "la leçon"
    return (
        f"La bonne réponse est {correct}. {correct_text} "
        f"car c'est l'option qui correspond le mieux à l'objectif de {lesson_title}. "
        "Relis la phrase clé du texte ou de l'audio, puis élimine les réponses qui ajoutent "
        "une idée absente, trop générale ou contraire au document."
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
        source="official_mock",
        explanation=_explanation(exercise),
    )


def _skill_cards(co_correct: int, co_total: int, ce_correct: int, ce_total: int, scores: dict) -> list:
    cards = []
    if co_total:
        cards.append({
            "code": "CO",
            "label": "Compréhension orale",
            "pct": scores["co_pct"],
            "correct": co_correct,
            "total": co_total,
            "cefr": scores["cefr_co"],
        })
    if ce_total:
        cards.append({
            "code": "CE",
            "label": "Compréhension écrite",
            "pct": scores["ce_pct"],
            "correct": ce_correct,
            "total": ce_total,
            "cefr": scores["cefr_ce"],
        })
    cards.extend([
        {
            "code": "EO",
            "label": "Expression orale",
            "pct": None,
            "correct": None,
            "total": None,
            "cefr": "À évaluer par IA",
        },
        {
            "code": "EE",
            "label": "Expression écrite",
            "pct": None,
            "correct": None,
            "total": None,
            "cefr": "À évaluer par IA",
        },
    ])
    return cards


_LEVEL_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _pick_tcf_exercises(section: str, level: str, count: int) -> list:
    """TCF adaptatif simulé : mix 30% niveau-1 + 40% niveau-cible + 30% niveau+1.

    Simule la progression adaptative du TCF réel (questions s'ajustent selon le niveau).
    Fallback sur le niveau courant si les niveaux adjacents n'ont pas assez d'exercices.
    """
    try:
        idx = _LEVEL_ORDER.index(level)
    except ValueError:
        idx = 2  # défaut B1

    lower_lv = _LEVEL_ORDER[idx - 1] if idx > 0 else level
    upper_lv = _LEVEL_ORDER[idx + 1] if idx < len(_LEVEL_ORDER) - 1 else level

    n_lower = round(count * 0.30)
    n_upper = round(count * 0.30)
    n_current = count - n_lower - n_upper

    def _fetch(lv: str, n: int) -> list:
        exs = list(
            CourseExercise.objects.filter(
                lesson__section=section,
                lesson__level=lv,
                lesson__is_published=True,
                is_active=True,
            ).select_related("lesson")
        )
        random.shuffle(exs)
        return exs[:n]

    lower_exs = _fetch(lower_lv, n_lower) if lower_lv != level else []
    upper_exs = _fetch(upper_lv, n_upper) if upper_lv != level else []

    # Overpick au niveau courant pour combler les manques
    current_exs = _fetch(level, count)
    picked_ids = {ex.id for ex in lower_exs + upper_exs}
    current_fill = [ex for ex in current_exs if ex.id not in picked_ids]

    result = lower_exs + upper_exs + current_fill[:n_current + (n_lower - len(lower_exs)) + (n_upper - len(upper_exs))]
    random.shuffle(result)
    return result[:count]


def _group_by_lesson(exercises: list) -> list:
    """Return [(lesson, [exercises...]), ...] ordered by lesson."""
    groups: dict = defaultdict(list)
    for ex in exercises:
        groups[ex.lesson].append(ex)
    return list(groups.items())


def _pick_eo_items(level: str, count: int) -> list:
    lessons = list(CourseLesson.objects.filter(section="eo", level=level, is_published=True))
    random.shuffle(lessons)
    items = []
    for lesson in lessons[:count]:
        ex = lesson.exercises.filter(is_active=True).first()
        if ex:
            items.append({"lesson": lesson, "exercise": ex})
    return items


def _pick_ee_items(level: str, count: int) -> list:
    lessons = list(CourseLesson.objects.filter(section="ee", level=level, is_published=True))
    random.shuffle(lessons)
    items = []
    for lesson in lessons[:count]:
        ex = lesson.exercises.filter(is_active=True).first()
        if ex:
            items.append({"lesson": lesson, "exercise": ex})
    return items


def _calc_score(score_type: str, co_correct: int, co_total: int,
                ce_correct: int, ce_total: int) -> dict:
    """Compute exam-specific scores + CECR estimate."""
    co_pct = co_correct / max(co_total, 1) * 100
    ce_pct = ce_correct / max(ce_total, 1) * 100
    g_pct = (co_correct + ce_correct) / max(co_total + ce_total, 1) * 100

    if score_type == "tef":
        # TEF Canada : 0–450 per section
        # Official CEFR bands (approximate from IRB guidelines)
        co_s = round(co_pct / 100 * 450)
        ce_s = round(ce_pct / 100 * 450)
        g_s = round(g_pct / 100 * 450)

        def _cefr(s):
            if s >= 417: return "C2"
            if s >= 366: return "C1"
            if s >= 304: return "B2"
            if s >= 242: return "B1"
            if s >= 181: return "A2"
            return "A1"

        return {
            "co_score": co_s, "co_max": 450,
            "ce_score": ce_s, "ce_max": 450,
            "global": g_s, "global_max": 450,
            "cefr_co": _cefr(co_s), "cefr_ce": _cefr(ce_s), "cefr_global": _cefr(g_s),
            "passed": None, "unit": "pts",
            "co_pct": round(co_pct), "ce_pct": round(ce_pct), "global_pct": round(g_pct),
        }

    elif score_type == "tcf":
        # TCF Canada : 0–699 per section
        # Official CEFR thresholds from France Education International
        co_s = round(co_pct / 100 * 699)
        ce_s = round(ce_pct / 100 * 699)
        g_s = round(g_pct / 100 * 699)

        def _cefr(s):
            if s >= 589: return "C2"
            if s >= 500: return "C1"
            if s >= 400: return "B2"
            if s >= 300: return "B1"
            if s >= 226: return "A2"
            return "A1"

        return {
            "co_score": co_s, "co_max": 699,
            "ce_score": ce_s, "ce_max": 699,
            "global": g_s, "global_max": 699,
            "cefr_co": _cefr(co_s), "cefr_ce": _cefr(ce_s), "cefr_global": _cefr(g_s),
            "passed": None, "unit": "pts",
            "co_pct": round(co_pct), "ce_pct": round(ce_pct), "global_pct": round(g_pct),
        }

    else:
        # DELF / DALF : /25 par section — CO+CE auto-scorés
        co_s = round(co_pct / 100 * 25)
        ce_s = round(ce_pct / 100 * 25)
        g_s = co_s + ce_s  # out of 50 (CO+CE only; PE+PO need AI/human)
        passed_co_ce = co_s >= 5 and ce_s >= 5 and g_s >= 25

        def _cefr(pct):
            if pct >= 90: return "C1–C2"
            if pct >= 75: return "B2–C1"
            if pct >= 60: return "B1–B2"
            if pct >= 40: return "A2–B1"
            return "A1–A2"

        return {
            "co_score": co_s, "co_max": 25,
            "ce_score": ce_s, "ce_max": 25,
            "global": g_s, "global_max": 50,
            "cefr_co": _cefr(co_pct), "cefr_ce": _cefr(ce_pct), "cefr_global": _cefr(g_pct),
            "passed": passed_co_ce, "unit": "/25",
            "co_pct": round(co_pct), "ce_pct": round(ce_pct), "global_pct": round(g_pct),
        }


# ─── VUES ─────────────────────────────────────────────────────────────────────

@login_required
def exam_format_hub(request, exam_code: str):
    """Hub de sélection du niveau (TEF / TCF)."""
    if exam_code not in EXAM_CONFIGS:
        raise Http404

    cfg = EXAM_CONFIGS[exam_code]
    levels_data = []
    for lv in cfg["levels"]:
        co_cnt = CourseExercise.objects.filter(
            lesson__section="co", lesson__level=lv,
            lesson__is_published=True, is_active=True,
        ).count()
        ce_cnt = CourseExercise.objects.filter(
            lesson__section="ce", lesson__level=lv,
            lesson__is_published=True, is_active=True,
        ).count()
        levels_data.append({
            "level": lv,
            "co_exercises": co_cnt,
            "ce_exercises": ce_cnt,
            "can_start": co_cnt >= 5 or ce_cnt >= 5,
        })

    return render(request, "preparation_tests/exam_format_hub.html", {
        "exam_code": exam_code,
        "cfg": cfg,
        "levels_data": levels_data,
    })


@subscription_required
def exam_format_exam(request, exam_code: str, level: str):
    """Examen blanc format officiel : GET → formulaire, POST → résultats."""
    if exam_code not in EXAM_CONFIGS:
        raise Http404

    level = level.upper()
    cfg = _cfg_for_level(exam_code, level)

    if level not in EXAM_CONFIGS[exam_code]["levels"]:
        raise Http404

    # ── POST : correction ────────────────────────────────────────────────────
    if request.method == "POST":
        co_ids = request.POST.getlist("co_exercise_ids")
        ce_ids = request.POST.getlist("ce_exercise_ids")

        co_exercises = list(
            CourseExercise.objects.filter(id__in=co_ids).select_related("lesson")
        )
        ce_exercises = list(
            CourseExercise.objects.filter(id__in=ce_ids).select_related("lesson")
        )
        # Preserve original order from hidden inputs
        co_map = {str(ex.id): ex for ex in co_exercises}
        ce_map = {str(ex.id): ex for ex in ce_exercises}
        co_exercises = [co_map[i] for i in co_ids if i in co_map]
        ce_exercises = [ce_map[i] for i in ce_ids if i in ce_map]

        co_correct = 0
        co_results = []
        for ex in co_exercises:
            answer = request.POST.get(f"co_{ex.id}", "").upper()
            correct = ex.correct_option.upper()
            is_ok = answer == correct
            if is_ok:
                co_correct += 1
            _remember_attempt(request.user, ex, answer, is_ok)
            co_results.append({
                "exercise": ex,
                "answer": answer,
                "is_correct": is_ok,
                "correct_option": correct,
                "correct_text": _option_text(ex, correct),
                "answer_text": _option_text(ex, answer),
                "explanation": _explanation(ex),
            })

        ce_correct = 0
        ce_results = []
        for ex in ce_exercises:
            answer = request.POST.get(f"ce_{ex.id}", "").upper()
            correct = ex.correct_option.upper()
            is_ok = answer == correct
            if is_ok:
                ce_correct += 1
            _remember_attempt(request.user, ex, answer, is_ok)
            ce_results.append({
                "exercise": ex,
                "answer": answer,
                "is_correct": is_ok,
                "correct_option": correct,
                "correct_text": _option_text(ex, correct),
                "answer_text": _option_text(ex, answer),
                "explanation": _explanation(ex),
            })

        scores = _calc_score(
            cfg["score_type"],
            co_correct, len(co_exercises),
            ce_correct, len(ce_exercises),
        )

        # ── Sauvegarder le résultat en base ──────────────────────
        saved_result = ExamFormatResult.objects.create(
            user=request.user,
            exam_code=exam_code,
            level=level,
            co_correct=co_correct,
            co_total=len(co_exercises),
            ce_correct=ce_correct,
            ce_total=len(ce_exercises),
            co_pct=scores["co_pct"],
            ce_pct=scores["ce_pct"],
            global_pct=scores["global_pct"],
            co_score=scores["co_score"],
            ce_score=scores["ce_score"],
            global_score=scores["global"],
            score_max=scores["global_max"],
            cefr_co=scores["cefr_co"],
            cefr_ce=scores["cefr_ce"],
            cefr_global=scores["cefr_global"],
            passed=scores["passed"],
        )

        # EO / EE (pour affichage résultats + correction IA)
        eo_ids = request.POST.getlist("eo_exercise_ids")
        ee_ids = request.POST.getlist("ee_exercise_ids")
        eo_items = []
        for eid in eo_ids:
            try:
                ex = CourseExercise.objects.select_related("lesson").get(id=eid)
                eo_items.append({"exercise": ex, "lesson": ex.lesson})
            except CourseExercise.DoesNotExist:
                pass
        ee_items = []
        for eid in ee_ids:
            try:
                ex = CourseExercise.objects.select_related("lesson").get(id=eid)
                ee_items.append({"exercise": ex, "lesson": ex.lesson})
            except CourseExercise.DoesNotExist:
                pass

        return render(request, "preparation_tests/exam_format_results.html", {
            "exam_code": exam_code,
            "level": level,
            "cfg": cfg,
            "co_results": co_results,
            "ce_results": ce_results,
            "co_correct": co_correct,
            "co_total": len(co_exercises),
            "ce_correct": ce_correct,
            "ce_total": len(ce_exercises),
            "scores": scores,
            "skill_cards": _skill_cards(
                co_correct, len(co_exercises), ce_correct, len(ce_exercises), scores
            ),
            "eo_items": eo_items,
            "ee_items": ee_items,
            "result_id": saved_result.id,
        })

    # ── GET : préparer l'examen ───────────────────────────────────────────────
    if exam_code == "tcf":
        co_exercises = _pick_tcf_exercises("co", level, cfg["co_count"])
        ce_exercises = _pick_tcf_exercises("ce", level, cfg["ce_count"])
    else:
        co_exercises = _pick_exercises("co", level, cfg["co_count"])
        ce_exercises = _pick_exercises("ce", level, cfg["ce_count"])
    co_groups = _group_by_lesson(co_exercises)
    ce_groups = _group_by_lesson(ce_exercises)
    eo_items = _pick_eo_items(level, cfg.get("eo_count", 1))
    ee_items = _pick_ee_items(level, cfg.get("ee_count", 1))

    total_min = cfg["co_min"] + cfg["ce_min"]
    timer_sec = (len(co_exercises) * cfg.get("timer_sec_co", 40)
                 + len(ce_exercises) * cfg.get("timer_sec_ce", 90))

    return render(request, "preparation_tests/exam_format_exam.html", {
        "exam_code": exam_code,
        "level": level,
        "cfg": cfg,
        "co_exercises": co_exercises,
        "co_groups": co_groups,
        "ce_exercises": ce_exercises,
        "ce_groups": ce_groups,
        "eo_items": eo_items,
        "ee_items": ee_items,
        "total_min": total_min,
        "timer_sec": timer_sec,
        "is_tcf_adaptive": exam_code == "tcf",
    })


# ─── HISTORIQUE ───────────────────────────────────────────────────────────────

@login_required
def exam_format_history(request):
    """Historique de tous les examens blancs format officiel de l'utilisateur."""
    results = ExamFormatResult.objects.filter(user=request.user)

    # Construction des datasets Chart.js — 1 série par exam_code
    _COLORS = {
        "tef":  "#3b82f6",
        "tcf":  "#22c55e",
        "delf": "#f59e0b",
        "dalf": "#a855f7",
    }
    chart_datasets: dict = {}
    for r in results:
        label = r.get_exam_code_display()
        if label not in chart_datasets:
            chart_datasets[label] = {
                "color": _COLORS.get(r.exam_code, "#888"),
                "data": [],
            }
        chart_datasets[label]["data"].append({
            "x": r.taken_at.strftime("%d/%m"),
            "y": r.global_pct,
        })

    return render(request, "preparation_tests/exam_format_history.html", {
        "results": results,
        "chart_datasets_json": json.dumps(chart_datasets),
        "total_count": results.count(),
    })


# ─── PACK RÉVISION INTELLIGENT ────────────────────────────────────────────────

@login_required
def smart_revision(request):
    """Analyse les examens + erreurs de leçons → génère un pack ciblé/adaptatif."""
    from collections import defaultdict

    last_results = list(
        ExamFormatResult.objects.filter(user=request.user).order_by("-taken_at")[:20]
    )
    scheduled_errors = list(due_errors(request.user, limit=30))
    revision_stats = error_stats(request.user)

    if not last_results and not scheduled_errors:
        return render(request, "preparation_tests/smart_revision.html", {"no_data": True})

    # ── Calcul des moyennes CO + CE par (exam_code, level) ──
    smap: dict = defaultdict(lambda: {"co": [], "ce": []})
    for r in last_results:
        smap[(r.exam_code, r.level)]["co"].append(r.co_pct)
        smap[(r.exam_code, r.level)]["ce"].append(r.ce_pct)

    for err in scheduled_errors:
        if err.lesson.section in {"co", "ce"}:
            smap[("cecr", err.lesson.level)][err.lesson.section].append(0)

    weakest_key = None
    weakest_score = 101.0
    weakest_section = "co"
    for key, vals in smap.items():
        avg_co = sum(vals["co"]) / len(vals["co"]) if vals["co"] else None
        avg_ce = sum(vals["ce"]) / len(vals["ce"]) if vals["ce"] else None
        if avg_co is not None and avg_co < weakest_score:
            weakest_score, weakest_key, weakest_section = avg_co, key, "co"
        if avg_ce is not None and avg_ce < weakest_score:
            weakest_score, weakest_key, weakest_section = avg_ce, key, "ce"

    if weakest_key is None:
        return render(request, "preparation_tests/smart_revision.html", {"no_data": True})

    weak_exam_code, weak_level = weakest_key
    weak_exam_name = EXAM_CONFIGS.get(weak_exam_code, {}).get("name", "CECR")

    error_exercises = [
        err.exercise for err in scheduled_errors
        if err.lesson.section == weakest_section and err.lesson.level == weak_level
    ]
    seen_ids = {ex.id for ex in error_exercises}
    fill = [ex for ex in _pick_exercises(weakest_section, weak_level, 15) if ex.id not in seen_ids]
    exercises = (error_exercises + fill)[:15]
    adaptive_note = (
        "Pack prioritaire basé sur tes erreurs dues en révision espacée."
        if error_exercises else
        "Pack basé sur la compétence la plus faible dans tes examens blancs."
    )

    # ── POST : correction du pack soumis ──
    if request.method == "POST":
        ids = request.POST.getlist("exercise_ids")
        ex_objs = {
            str(e.id): e
            for e in CourseExercise.objects.filter(id__in=ids).select_related("lesson")
        }
        exs_ordered = [ex_objs[i] for i in ids if i in ex_objs]
        correct = 0
        rev = []
        for ex in exs_ordered:
            ans = request.POST.get(f"q_{ex.id}", "").upper()
            is_ok = ans == ex.correct_option.upper()
            if is_ok:
                correct += 1
            _remember_attempt(request.user, ex, ans, is_ok)
            rev.append({
                "exercise": ex,
                "answer": ans,
                "is_correct": is_ok,
                "correct_option": ex.correct_option.upper(),
                "correct_text": _option_text(ex, ex.correct_option),
                "answer_text": _option_text(ex, ans),
                "explanation": _explanation(ex),
            })

        return render(request, "preparation_tests/smart_revision.html", {
            "submitted": True,
            "results_list": rev,
            "correct": correct,
            "total": len(rev),
            "pct": round(correct / max(len(rev), 1) * 100),
            "weak_exam": weak_exam_name,
            "weak_level": weak_level,
            "weak_section": weakest_section.upper(),
            "avg_score": round(weakest_score),
            "adaptive_note": adaptive_note,
            "revision_stats": revision_stats,
        })

    # ── GET : afficher le pack ──
    return render(request, "preparation_tests/smart_revision.html", {
        "exercises": exercises,
        "weak_exam": weak_exam_name,
        "weak_level": weak_level,
        "weak_section": weakest_section.upper(),
        "avg_score": round(weakest_score),
        "total_analyzed": len(last_results),
        "error_count": revision_stats["active"],
        "due_count": revision_stats["due"],
        "revision_stats": revision_stats,
        "adaptive_note": adaptive_note,
    })
