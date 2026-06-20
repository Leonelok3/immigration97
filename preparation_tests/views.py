from __future__ import annotations

# =========================================================
# 📦 IMPORTS STANDARD
# =========================================================
import json
from pathlib import Path

# =========================================================
# 📦 IMPORTS DJANGO
# =========================================================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    FileResponse,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.views.decorators.http import require_POST

# =========================================================
# 📦 MODELS
# =========================================================
from .models import (
    CEFRCertificate,
    CoachIAReport,
    Exam,
    ExamSection,
    Question,
    Choice,
    Session,
    Attempt,
    Answer,
    CourseLesson,
    CourseExercise,
    UserSkillResult,
    UserSkillProgress,
    UserLessonProgress,
    UserExerciseProgress,
    EOSubmission,
    EESubmission,
    MonthlyTrainingPack,
    PastExamSubject,
    FeaturedContent,
)
from billing.services import has_active_access

# =========================================================
# 🧠 SERVICES MÉTIER
# =========================================================
from preparation_tests.services.feedback import build_smart_feedback
from preparation_tests.services.recommendations import recommend_lessons
from preparation_tests.services.level_engine import get_cefr_progress
from preparation_tests.services.study_plan import (
    build_study_plan,
    adapt_study_plan,
    advance_study_day,
)
from preparation_tests.services.error_revision import record_detailed_attempt

# =========================================================
# 🤖 IA
# =========================================================
from preparation_tests.services.ai_coach import get_ai_coach
from preparation_tests.services.ai_coach.coach_global import AICoachGlobal

# =========================================================
# 🔧 CORE
# =========================================================
from core.constants import LEVEL_ORDER


# =========================================================
# 🔧 OUTILS INTERNES
# =========================================================
def _ulp_count(user, **filters) -> int:
    """Compte les UserLessonProgress en ignorant les erreurs DB (ex: migration manquante)."""
    try:
        return UserLessonProgress.objects.filter(user=user, **filters).count()
    except Exception:
        return 0


def _ulp_first(user, lesson):
    """Retourne le UserLessonProgress ou None, sans planter si la table est absente."""
    try:
        return UserLessonProgress.objects.filter(user=user, lesson=lesson).first()
    except Exception:
        return None


def _next_unanswered_question(attempt: Attempt):
    answered = set(attempt.answers.values_list("question_id", flat=True))
    return (
        attempt.section.questions
        .exclude(id__in=answered)
        .order_by("id")
        .first()
    )


def _audio_url_from_question(q: Question):
    """
    Retourne l'URL audio si présente
    """
    try:
        if q.asset and q.asset.kind == "audio" and q.asset.file:
            return q.asset.file.url
    except Exception:
        pass
    return None


def _ensure_expression_exercise(lesson):
    if lesson.section not in {"eo", "ee"}:
        return
    if lesson.exercises.filter(is_active=True).exists():
        return

    instruction = (
        "Réponds au sujet en respectant le niveau demandé. "
        "Structure ta réponse et donne des exemples précis."
    )
    if lesson.section == "ee":
        instruction = (
            "Rédige une réponse complète et structurée. "
            "Relis ton texte avant de demander la correction IA."
        )

    CourseExercise.objects.create(
        lesson=lesson,
        title=lesson.title,
        instruction=instruction,
        question_text=lesson.title,
        option_a="Réponse libre",
        option_b="Réponse libre",
        option_c="",
        option_d="",
        correct_option="A",
        summary=lesson.content_html or "",
        order=1,
        is_active=True,
    )


def _course_option_text(exercise, option):
    return {
        "A": exercise.option_a,
        "B": exercise.option_b,
        "C": exercise.option_c,
        "D": exercise.option_d,
    }.get((option or "").upper(), "")


def _course_explanation(exercise):
    if exercise.summary:
        return exercise.summary
    correct = (exercise.correct_option or "").upper()
    return (
        f"La bonne réponse est {correct}. {_course_option_text(exercise, correct)} "
        "car cette option correspond à l'information attendue dans la leçon. "
        "Relis la consigne, repère le mot-clé, puis compare chaque option avec le document."
    )


# =========================================================
# 🏠 ACCUEIL & HUBS
# =========================================================
@login_required
def home(request):
    return render(request, "preparation_tests/home.html")


@login_required
def french_exams(request):
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    section_labels = {
        "ce": "Compréhension écrite",
        "ee": "Expression écrite",
        "eo": "Expression orale",
        "co": "Compréhension orale",
    }
    section_routes = {
        "ce": "preparation_tests:ce_by_level",
        "ee": "preparation_tests:ee_by_level",
        "eo": "preparation_tests:eo_by_level",
        "co": "preparation_tests:co_by_level",
    }

    level_cards = []
    for level in levels:
        lesson_total = CourseLesson.objects.filter(
            level=level,
            is_published=True,
        ).count()
        exercise_total = CourseExercise.objects.filter(
            lesson__level=level,
            lesson__is_published=True,
            is_active=True,
        ).count()
        completed = _ulp_count(request.user, lesson__level=level, is_completed=True)

        skills = []
        for code, label in section_labels.items():
            count = CourseLesson.objects.filter(
                section=code,
                level=level,
                is_published=True,
            ).count()
            if count:
                skills.append({
                    "code": code,
                    "label": label,
                    "count": count,
                    "url": reverse(section_routes[code], args=[level]),
                })

        first_skill = skills[0] if skills else None
        level_cards.append({
            "level": level,
            "lessons": lesson_total,
            "exercises": exercise_total,
            "completed": completed,
            "progress_pct": int((completed / lesson_total) * 100) if lesson_total else 0,
            "skills": skills,
            "start_url": first_skill["url"] if first_skill else reverse("preparation_tests:french_exams"),
        })

    section_cards = []
    for code, label in section_labels.items():
        total = CourseLesson.objects.filter(section=code, is_published=True).count()
        exercises = CourseExercise.objects.filter(
            lesson__section=code,
            lesson__is_published=True,
            is_active=True,
        ).count()
        section_cards.append({
            "code": code,
            "label": label,
            "lessons": total,
            "exercises": exercises,
            "url": reverse(f"preparation_tests:{code}_hub"),
        })

    return render(
        request,
        "preparation_tests/french_exams.html",
        {
            "level_cards": level_cards,
            "section_cards": section_cards,
            "total_lessons": CourseLesson.objects.filter(is_published=True).count(),
            "total_exercises": CourseExercise.objects.filter(
                lesson__is_published=True,
                is_active=True,
            ).count(),
        },
    )


@login_required
def tef_hub(request):
    sections = [
        {"code": "co", "title": "Compréhension orale"},
        {"code": "ce", "title": "Compréhension écrite"},
        {"code": "ee", "title": "Expression écrite"},
        {"code": "eo", "title": "Expression orale"},
    ]

    for s in sections:
        s["url"] = reverse(
            "preparation_tests:course_section",
            args=["tef", s["code"]],
        )

    return render(
        request,
        "preparation_tests/fr_tef_hub.html",
        {"sections": sections},
    )


@login_required
def tcf_hub(request):
    sections = [
        {"code": "co", "title": "Compréhension orale"},
        {"code": "ce", "title": "Compréhension écrite"},
        {"code": "ee", "title": "Expression écrite"},
        {"code": "eo", "title": "Expression orale"},
    ]

    for s in sections:
        s["url"] = reverse(
            "preparation_tests:course_section",
            args=["tcf", s["code"]],
        )

    return render(
        request,
        "preparation_tests/fr_tcf_hub.html",
        {"sections": sections},
    )


@login_required
def delf_hub(request):
    return render(request, "preparation_tests/fr_delf_hub.html")


@login_required
def dalf_hub(request):
    return render(request, "preparation_tests/fr_dalf_hub.html")


# =========================================================
# 📚 EXAMENS
# =========================================================
@login_required
def exam_list(request):
    exams = Exam.objects.all().order_by("language", "name")
    return render(request, "preparation_tests/exam_list.html", {"exams": exams})


@login_required
def exam_detail(request, exam_code):
    code = exam_code.lower()
    if code == "tef":
        return redirect("preparation_tests:tef_hub")
    if code == "tcf":
        return redirect("preparation_tests:tcf_hub")
    exam = get_object_or_404(Exam, code__iexact=exam_code)
    sections = exam.sections.all()
    return render(
        request,
        "preparation_tests/exam_detail.html",
        {"exam": exam, "sections": sections},
    )


# =========================================================
# 📖 COURS PAR SECTION
# =========================================================
@login_required
def course_section(request, exam_code, section):
    exam_code = exam_code.upper()
    exam = get_object_or_404(Exam, code__iexact=exam_code)

    lessons = CourseLesson.objects.filter(
        exams=exam,
        section=section,
        is_published=True
    ).order_by("level", "order")

    cefr = get_cefr_progress(
        user=request.user,
        exam_code=exam.code,
        skill=section,
    )

    return render(
        request,
        "preparation_tests/course_section.html",
        {
            "exam": exam,
            "exam_code": exam.code,
            "section": section,
            "lessons": lessons,
            "cefr": cefr,
        }
    )


# =========================================================
# 📘 LEÇON + EXERCICES
# =========================================================
@login_required
def lesson_session(request, exam_code, section, lesson_id):
    """
    Affiche une leçon avec ses exercices.
    """
    lesson = get_object_or_404(CourseLesson, id=lesson_id)
    user = request.user
    _ensure_expression_exercise(lesson)

    raw_exercises = CourseExercise.objects.filter(
        lesson=lesson,
        is_active=True,
    ).order_by("order")

    # Progression utilisateur sur cette leçon
    ulp = _ulp_first(user, lesson)
    progress_completed = ulp.completed_exercises if ulp else 0
    progress_total = raw_exercises.count()
    progress_percent = ulp.percent if ulp else 0

    # Premium : tous les utilisateurs connectés ont accès audio (à ajuster avec billing)
    is_premium = True

    # Structure attendue par le template : row.obj + row.can_audio
    exercises = [
        {"obj": ex, "can_audio": is_premium}
        for ex in raw_exercises
    ]

    context = {
        "lesson": lesson,
        "exercises": exercises,
        "exam_code": exam_code,
        "display_exam_code": exam_code.upper(),
        "section": section,
        "progress_completed": progress_completed,
        "progress_total": progress_total,
        "progress_percent": progress_percent,
        "is_premium": is_premium,
    }

    return render(request, "preparation_tests/lesson_session.html", context)


# =========================================================
# 🕒 SESSIONS
# =========================================================
@login_required
def start_session_generic(request, exam_code):
    exam = Exam.objects.filter(code__iexact=exam_code).first()
    if not exam:
        code = (exam_code or "").lower()
        if code in {"tef", "tcf", "delf", "dalf"}:
            return redirect("preparation_tests:exam_format_hub", exam_code=code)
        raise Http404()

    section = exam.sections.order_by("order").first()

    if not section:
        messages.error(request, "Aucune section disponible.")
        return redirect("preparation_tests:exam_detail", exam_code=exam.code)

    session = Session.objects.create(
        user=request.user,
        exam=exam,
        mode="practice",
    )

    attempt = Attempt.objects.create(
        session=session,
        section=section,
    )

    return redirect("preparation_tests:take_section", attempt_id=attempt.id)


@login_required
def start_session(request, exam_code):
    return start_session_generic(request, exam_code=exam_code)


@login_required
def start_session_with_section(request, exam_code, section):
    return start_session_generic(request, exam_code=exam_code)


# =========================================================
# ❓ QUESTIONS
# =========================================================
@login_required
def take_section(request, attempt_id):
    attempt = get_object_or_404(
        Attempt,
        id=attempt_id,
        session__user=request.user,
    )

    question = _next_unanswered_question(attempt)

    if not question:
        attempt.total_items = attempt.section.questions.count()
        attempt.raw_score = attempt.answers.filter(is_correct=True).count()

        if hasattr(attempt, "ended_at"):
            attempt.ended_at = timezone.now()

        attempt.save()

        attempt.session.completed_at = timezone.now()
        attempt.session.save()

        return redirect("preparation_tests:session_result", session_id=attempt.session.id)

    return render(
        request,
        "preparation_tests/question.html",
        {
            "attempt": attempt,
            "question": question,
            "choices": question.choices.all(),
            "audio_url": _audio_url_from_question(question),
            "current_index": attempt.answers.count() + 1,
            "total_questions": attempt.section.questions.count(),
        },
    )


@login_required
def submit_answer(request, attempt_id, question_id):
    if request.method != "POST":
        raise Http404()

    attempt = get_object_or_404(Attempt, id=attempt_id, session__user=request.user)
    question = get_object_or_404(Question, id=question_id)

    choice_id = request.POST.get("choice")
    is_correct = False

    if choice_id:
        choice = get_object_or_404(Choice, id=choice_id, question=question)
        is_correct = choice.is_correct

    Answer.objects.create(
        attempt=attempt,
        question=question,
        payload={"choice_id": choice_id},
        is_correct=is_correct,
    )

    return redirect("preparation_tests:take_section", attempt_id=attempt.id)


# =========================================================
# 📊 RÉSULTATS
# =========================================================
@login_required
def session_result(request, session_id):
    session = get_object_or_404(Session, id=session_id, user=request.user)
    attempts = session.attempts.all()

    total_items = sum(a.total_items or 0 for a in attempts)
    total_correct = sum(a.raw_score or 0 for a in attempts)
    global_pct = int(round(100 * total_correct / total_items)) if total_items else 0

    per_section = {}
    for a in attempts:
        per_section[a.section.code.upper()] = {
            "pct": int(round(100 * a.raw_score / a.total_items)) if a.total_items else 0,
            "correct": a.raw_score,
            "total": a.total_items,
        }

    feedback = build_smart_feedback(
        exam_code=session.exam.code,
        global_pct=global_pct,
        per_section=per_section,
        unlocked_info=None,
    )

    recommended_lessons = recommend_lessons(
        user=request.user,
        exam_code=session.exam.code,
        per_section=per_section,
    )

    analysis = None
    global_analysis = None
    cefr = None

    if attempts.exists():
        global_analysis = AICoachGlobal.analyze_session(attempts)

        first_attempt = attempts.first()
        coach = get_ai_coach(first_attempt.section.code)
        if coach:
            analysis = coach.analyze_attempt(first_attempt)

        cefr = get_cefr_progress(
            user=request.user,
            exam_code=session.exam.code,
            skill=first_attempt.section.code,
        )

    return render(
        request,
        "preparation_tests/result.html",
        {
            "session": session,
            "attempts": attempts,
            "global_pct": global_pct,
            "analysis": analysis,
            "global_analysis": global_analysis,
            "feedback": feedback,
            "recommended_lessons": recommended_lessons,
            "cefr": cefr,
        },
    )


@login_required
def session_correction(request, session_id):
    return redirect("preparation_tests:session_result", session_id=session_id)


@login_required
def session_skill_analysis(request, session_id):
    return redirect("preparation_tests:session_result", session_id=session_id)


@login_required
def session_review(request):
    return render(request, "preparation_tests/session_review.html", {"sessions": []})


@login_required
def retry_wrong_questions(request, session_id):
    return redirect("preparation_tests:session_result", session_id=session_id)


@login_required
def run_retry_session(request, session_id):
    return redirect("preparation_tests:session_result", session_id=session_id)


@login_required
def retry_session_errors(request, session_id):
    session = get_object_or_404(Session, id=session_id, user=request.user)
    return redirect("preparation_tests:session_result", session_id=session.id)


@login_required
def save_lesson_progress(request):
    return JsonResponse({"status": "ok"})


# =========================================================
# 📜 CERTIFICATS
# =========================================================
@login_required
def download_certificate(request, exam_code, level):
    cert_dir = Path(settings.MEDIA_ROOT) / "certificates"
    for file in cert_dir.glob(f"{exam_code}_{level}_*.pdf"):
        return FileResponse(open(file, "rb"), as_attachment=True, filename=file.name)
    raise Http404("Certificat introuvable")


@login_required
def verify_certificate(request, public_id):
    certificate = get_object_or_404(CEFRCertificate, public_id=public_id)
    return render(
        request,
        "preparation_tests/certificate_verify.html",
        {"certificate": certificate},
    )


# =========================================================
# 🎓 EXAMEN BLANC (MOCK EXAM)
# =========================================================
@login_required
def start_mock_exam(request, exam_code, section_code):
    exam = get_object_or_404(Exam, code=exam_code)
    section = get_object_or_404(ExamSection, exam=exam, code=section_code)

    session = Session.objects.create(
        user=request.user,
        exam=exam,
        section=section,
        mode="mock",
    )

    Attempt.objects.create(
        session=session,
        section=section,
    )

    return redirect("preparation_tests:mock_exam_session", session_id=session.id)


@login_required
def mock_exam_session(request, session_id):
    session = get_object_or_404(
        Session,
        id=session_id,
        user=request.user,
        mode="mock",
    )

    exam = session.exam
    section = session.section

    questions = Question.objects.filter(section=section).order_by("?")[:25]

    attempt, _ = Attempt.objects.get_or_create(
        session=session,
        section=section,
        defaults={
            "total_items": questions.count(),
            "raw_score": 0,
            "score_percent": 0,
        },
    )

    cefr = get_cefr_progress(
        user=request.user,
        exam_code=exam.code,
        skill=section.code,
    )

    context = {
        "session": session,
        "exam": exam,
        "exam_code": exam.code,
        "section": section.code,
        "questions": questions,
        "attempt": attempt,
        "cefr": cefr,
    }

    return render(request, "preparation_tests/mock_exam_session.html", context)


@login_required
def mock_exam_results(request, session_id):
    session = get_object_or_404(Session, id=session_id, user=request.user)
    attempt = session.attempts.first()

    correct = attempt.answers.filter(is_correct=True).count()
    total = attempt.total_items
    score = round((correct / total) * 100, 2) if total else 0

    attempt.raw_score = correct
    attempt.score_percent = score
    attempt.save()

    session.total_score = score
    session.completed_at = timezone.now()
    session.save()

    return render(
        request,
        "preparation_tests/mock_exam_results.html",
        {
            "session": session,
            "score": score,
            "correct": correct,
            "total": total,
        },
    )


# =========================================================
# 📊 TABLEAU DE BORD GLOBAL
# =========================================================
@login_required
def dashboard_global(request):
    user = request.user

    progresses = UserSkillProgress.objects.filter(user=user)

    exams = {}
    for p in progresses:
        exams.setdefault(p.exam_code, []).append(p)

    exam_stats = []
    for exam_code, items in exams.items():
        avg_score = round(
            sum(i.score_percent for i in items) / len(items)
        ) if items else 0

        max_level = max(
            items,
            key=lambda x: list(LEVEL_ORDER.keys()).index(x.current_level)
        ).current_level

        exam_stats.append({
            "exam": exam_code.upper(),
            "avg_score": avg_score,
            "level": max_level,
        })

    if progresses.exists():
        global_index = max(
            list(LEVEL_ORDER.keys()).index(p.current_level)
            for p in progresses
        )
    else:
        global_index = 0

    global_level = list(LEVEL_ORDER.keys())[global_index]
    global_progress = round(global_index / (len(LEVEL_ORDER) - 1) * 100)

    skills = {"co": 0, "ce": 0, "ee": 0, "eo": 0}
    counts = {"co": 0, "ce": 0, "ee": 0, "eo": 0}

    for p in progresses:
        if p.skill in skills:
            skills[p.skill] += p.score_percent
            counts[p.skill] += 1

    for k in skills:
        skills[k] = round(skills[k] / counts[k]) if counts[k] else 0

    certificates = CEFRCertificate.objects.filter(user=user)

    latest_sessions = (
        Session.objects
        .filter(user=user, completed_at__isnull=False)
        .prefetch_related("attempts", "attempts__section")
        .order_by("-completed_at")[:3]
    )

    global_ai_analysis = None

    if latest_sessions.exists():
        all_attempts = []
        for session in latest_sessions:
            all_attempts.extend(list(session.attempts.all()))

        if all_attempts:
            global_ai_analysis = AICoachGlobal.analyze_session(all_attempts)

            CoachIAReport.objects.create(
                user=user,
                exam_code=latest_sessions.first().exam.code.upper(),
                scope="global",
                data=global_ai_analysis,
                score_snapshot=skills,
            )

    context = {
        "global_level": global_level,
        "global_progress": global_progress,
        "exam_stats": exam_stats,
        "skills": skills,
        "certificates": certificates,
        "context_global_ai": global_ai_analysis,
    }

    return render(request, "preparation_tests/dashboard_global.html", context)


# =========================================================
# 📅 PLAN D'ÉTUDE PERSONNALISÉ
# =========================================================
@login_required
def study_plan_view(request, exam_code):
    """
    Affiche le plan d'étude personnalisé de l'utilisateur
    """
    plan = build_study_plan(user=request.user, exam_code=exam_code)

    if not plan:
        messages.error(request, "Impossible de charger ton plan d'étude.")
        return redirect("preparation_tests:exam_detail", exam_code=exam_code)

    try:
        last_results = UserSkillResult.objects.filter(
            user=request.user,
            exam__code__iexact=exam_code,
        )

        per_section = {}
        for r in last_results:
            if r.section:
                per_section[r.section.code.upper()] = {"pct": r.score_percent}

        if per_section:
            plan = adapt_study_plan(plan_data=plan, per_section=per_section)

    except Exception:
        pass

    return render(
        request,
        "preparation_tests/study_plan.html",
        {"exam_code": exam_code, "plan": plan},
    )


@login_required
def complete_study_day(request, exam_code):
    """
    Valider la journée d'étude en cours
    """
    advance_study_day(user=request.user, exam_code=exam_code)
    messages.success(request, "Journée validée. Continue comme ca !")
    return redirect("preparation_tests:study_plan", exam_code=exam_code)


# =========================================================
# 🤖 HISTORIQUE COACH IA
# =========================================================
@login_required
def coach_ai_history(request):
    reports = request.user.coach_reports.all()
    return render(
        request,
        "preparation_tests/coach_ai_history.html",
        {"reports": reports},
    )


@login_required
def coach_ai_pdf(request, report_id):
    from preparation_tests.services.coach_ai_pdf import generate_coach_ai_pdf

    report = get_object_or_404(CoachIAReport, id=report_id, user=request.user)
    pdf_path = generate_coach_ai_pdf(report)

    return FileResponse(open(pdf_path, "rb"), as_attachment=True, filename=pdf_path.name)


# =========================================================
# 🛠 HELPER — contexte commun des hubs de compétence
# =========================================================
def _build_skill_hub_context(user, section: str) -> dict:
    from django.utils import timezone as tz
    today = tz.now().date()

    # Niveaux + progression
    level_keys = (
        CourseLesson.objects.filter(section=section, is_published=True)
        .values_list("level", flat=True)
        .distinct()
        .order_by("level")
    )
    levels_data = []
    for lv in level_keys:
        total = CourseLesson.objects.filter(section=section, level=lv, is_published=True).count()
        done = _ulp_count(user, lesson__section=section, lesson__level=lv, is_completed=True)
        levels_data.append({
            "level": lv,
            "completed": done,
            "total": total,
            "progress_pct": int((done / total) * 100) if total else 0,
        })

    # Contenu mis en avant
    base_qs = FeaturedContent.objects.filter(
        language="fr", section=section, is_published=True
    )
    monthly_topic = base_qs.filter(content_type="monthly").first()
    official_subjects = base_qs.filter(content_type__in=["subject", "correction"]).order_by("order", "-created_at")
    tips = base_qs.filter(content_type="tip").order_by("order")
    monthly_packs = MonthlyTrainingPack.objects.filter(
        language="fr",
        section=section,
        is_published=True,
    ).order_by("-month", "order")[:4]
    if not monthly_topic and monthly_packs:
        monthly_topic = monthly_packs[0]
    past_exam_subjects = PastExamSubject.objects.filter(
        language="fr",
        section=section,
        is_published=True,
    ).order_by("-frequency_score", "order", "-created_at")[:6]

    has_access = has_active_access(user)

    return {
        "levels": levels_data,
        "monthly_topic": monthly_topic,
        "official_subjects": official_subjects,
        "monthly_packs": monthly_packs,
        "past_exam_subjects": past_exam_subjects,
        "tips": tips,
        "has_access": has_access,
        "section_code": section,
    }


@login_required
def monthly_packs_index(request):
    from django.utils import timezone as tz

    today = tz.localdate()
    packs = MonthlyTrainingPack.objects.filter(language="fr", is_published=True).order_by("-month", "section", "level")
    today_packs = packs.filter(month=today)
    return render(
        request,
        "preparation_tests/monthly_packs_index.html",
        {"packs": packs, "today_packs": today_packs, "today": today},
    )


@login_required
def monthly_pack_detail(request, slug):
    pack = get_object_or_404(MonthlyTrainingPack, slug=slug, is_published=True)
    if pack.is_premium and not has_active_access(request.user):
        messages.info(request, "Cette leçon du jour est réservée aux membres Premium.")
        return redirect("billing:pricing")
    return render(request, "preparation_tests/monthly_pack_detail.html", {"pack": pack})


@login_required
def past_exam_subjects_index(request):
    subjects = PastExamSubject.objects.filter(language="fr", is_published=True).order_by("-frequency_score", "section", "level")
    return render(request, "preparation_tests/past_exam_subjects_index.html", {"subjects": subjects})


@login_required
def past_exam_subject_detail(request, slug):
    subject = get_object_or_404(PastExamSubject, slug=slug, is_published=True)
    if subject.is_premium and not has_active_access(request.user):
        messages.info(request, "Cet ancien sujet corrigé est réservé aux membres Premium.")
        return redirect("billing:pricing")
    return render(request, "preparation_tests/past_exam_subject_detail.html", {"subject": subject})


# =========================================================
# ✅ HUB CO / CE PAR NIVEAU
# =========================================================
@login_required
def co_hub(request):
    ctx = _build_skill_hub_context(request.user, "co")
    return render(request, "preparation_tests/co_hub.html", ctx)


@login_required
def co_by_level(request, level):
    level = level.upper()
    user = request.user

    lessons = CourseLesson.objects.filter(
        section="co", level=level, is_published=True
    ).order_by("order")

    try:
        cefr = get_cefr_progress(user=user, exam_code="CECR", skill="co")
    except Exception:
        cefr = None

    return render(
        request,
        "preparation_tests/co_by_level.html",
        {
            "section": "co",
            "level": level,
            "lessons": lessons,
            "cefr": cefr,
        },
    )


@login_required
def ce_hub(request):
    ctx = _build_skill_hub_context(request.user, "ce")
    return render(request, "preparation_tests/ce_hub.html", ctx)


@login_required
def ce_by_level(request, level):
    level = level.upper()
    user = request.user

    lessons = CourseLesson.objects.filter(
        section="ce", level=level, is_published=True
    ).order_by("order")

    try:
        cefr = get_cefr_progress(user=user, exam_code="CECR", skill="ce")
    except Exception:
        cefr = None

    return render(
        request,
        "preparation_tests/ce_by_level.html",
        {
            "section": "ce",
            "level": level,
            "lessons": lessons,
            "cefr": cefr,
        },
    )


# =========================================================
# 📈 PROGRESSION EXERCICES (API)
# =========================================================
@login_required
@require_POST
def exercise_progress(request):
    """
    Reçoit: {exercise_id: int, selected: "A", correct: true/false}
    Met à jour UserExerciseProgress + UserLessonProgress.
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    exercise_id = payload.get("exercise_id")
    selected = (payload.get("selected") or "").upper()
    client_correct = bool(payload.get("correct"))

    if not exercise_id:
        return JsonResponse({"ok": False, "error": "missing_exercise_id"}, status=400)

    exercise = CourseExercise.objects.select_related("lesson").filter(id=exercise_id).first()
    if not exercise:
        return JsonResponse({"ok": False, "error": "exercise_not_found"}, status=404)

    lesson = exercise.lesson
    user = request.user
    correct_option = (exercise.correct_option or "").upper()
    correct = bool(selected and selected == correct_option)

    prog, _ = UserExerciseProgress.objects.get_or_create(
        user=user,
        exercise=exercise,
        defaults={"lesson": lesson},
    )

    if prog.lesson_id != lesson.id:
        prog.lesson = lesson

    prog.mark_attempt(selected=selected, correct=correct)
    prog.save()
    record_detailed_attempt(
        user=user,
        exercise=exercise,
        selected=selected,
        is_correct=correct,
        source="lesson",
        explanation=_course_explanation(exercise),
    )

    total = lesson.exercises.filter(is_active=True).count()
    completed = UserExerciseProgress.objects.filter(
        user=user,
        lesson=lesson,
        is_completed=True
    ).count()

    percent = int(round((completed / total) * 100)) if total else 0
    is_completed = (total > 0 and completed >= total)

    ulp, _ = UserLessonProgress.objects.get_or_create(
        user=user,
        lesson=lesson,
        defaults={
            "percent": 0,
            "is_completed": False,
            "completed_exercises": 0,
            "total_exercises": total,
        }
    )

    ulp.total_exercises = total
    ulp.completed_exercises = completed
    ulp.percent = percent
    ulp.is_completed = is_completed
    ulp.save()

    return JsonResponse({
        "ok": True,
        "lesson_id": lesson.id,
        "selected": selected,
        "correct": correct,
        "client_correct": client_correct,
        "correct_option": correct_option,
        "correct_text": _course_option_text(exercise, correct_option),
        "selected_text": _course_option_text(exercise, selected),
        "explanation": _course_explanation(exercise),
        "total_exercises": total,
        "completed_exercises": completed,
        "percent": percent,
        "is_completed": is_completed,
        "exercise_completed": prog.is_completed,
        "attempts": prog.attempts,
    })


# =========================================================
# 🎤 HUB EO / EE PAR NIVEAU
# =========================================================
@login_required
def eo_hub(request):
    ctx = _build_skill_hub_context(request.user, "eo")
    return render(request, "preparation_tests/eo_hub.html", ctx)


@login_required
def eo_by_level(request, level):
    level = level.upper()
    user = request.user

    lessons = CourseLesson.objects.filter(
        section="eo", level=level, is_published=True
    ).order_by("order")

    try:
        cefr = get_cefr_progress(user=user, exam_code="CECR", skill="eo")
    except Exception:
        cefr = None

    return render(
        request,
        "preparation_tests/eo_by_level.html",
        {
            "section": "eo",
            "level": level,
            "lessons": lessons,
            "cefr": cefr,
        },
    )


@login_required
def ee_hub(request):
    ctx = _build_skill_hub_context(request.user, "ee")
    return render(request, "preparation_tests/ee_hub.html", ctx)


@login_required
def ee_by_level(request, level):
    level = level.upper()
    user = request.user

    lessons = CourseLesson.objects.filter(
        section="ee", level=level, is_published=True
    ).order_by("order")

    try:
        cefr = get_cefr_progress(user=user, exam_code="CECR", skill="ee")
    except Exception:
        cefr = None

    return render(
        request,
        "preparation_tests/ee_by_level.html",
        {
            "section": "ee",
            "level": level,
            "lessons": lessons,
            "cefr": cefr,
        },
    )


# =========================================================
# 🎤 API SOUMISSION EO
# =========================================================
@login_required
@require_POST
def submit_eo(request):
    """
    Reçoit: multipart/form-data avec exercise_id + audio (Blob)
    Transcrit (Whisper) → évalue (GPT) → sauvegarde EOSubmission → met à jour progression.
    """
    from ai_engine.services.eval_service import transcribe_audio, evaluate_eo
    import tempfile, os

    exercise_id = request.POST.get("exercise_id")
    audio_file = request.FILES.get("audio")

    if not exercise_id:
        return JsonResponse({"ok": False, "error": "missing_exercise_id"}, status=400)

    exercise = CourseExercise.objects.select_related("lesson").filter(id=exercise_id).first()
    if not exercise:
        return JsonResponse({"ok": False, "error": "exercise_not_found"}, status=404)

    lesson = exercise.lesson
    user = request.user

    # Sauvegarder le fichier audio temporairement pour Whisper
    transcript = ""
    if audio_file:
        suffix = ".webm"
        if audio_file.content_type and "ogg" in audio_file.content_type:
            suffix = ".ogg"
        elif audio_file.content_type and "mp4" in audio_file.content_type:
            suffix = ".mp4"

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            transcript = transcribe_audio(tmp_path)
        except Exception as _transcribe_err:
            import logging as _log
            _log.getLogger(__name__).error("submit_eo transcription error: %s", _transcribe_err)
            transcript = ""
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not transcript:
        return JsonResponse({"ok": False, "error": "transcription_failed"}, status=422)

    # Évaluation IA
    import json as _json
    expected_points = []
    if exercise.summary:
        try:
            pts = _json.loads(exercise.summary)
            if isinstance(pts, list):
                expected_points = pts
        except (ValueError, TypeError):
            expected_points = [exercise.summary]

    result = evaluate_eo(
        transcript=transcript,
        topic=exercise.question_text,
        instructions=exercise.instruction,
        level=lesson.level,
        expected_points=expected_points,
    )

    score = float(result.get("score", 0))

    # Sauvegarder soumission (sans garder le fichier audio en DB pour économiser l'espace)
    EOSubmission.objects.create(
        user=user,
        exercise=exercise,
        transcript=transcript,
        score=score,
        feedback_json=result,
    )

    # Mettre à jour la progression (score >= 60 = exercice réussi)
    is_correct = score >= 60
    prog, _ = UserExerciseProgress.objects.get_or_create(
        user=user,
        exercise=exercise,
        defaults={"lesson": lesson},
    )
    if prog.lesson_id != lesson.id:
        prog.lesson = lesson
    prog.mark_attempt(selected="EO", correct=is_correct)
    prog.save()
    record_detailed_attempt(
        user=user,
        exercise=exercise,
        selected="EO",
        is_correct=is_correct,
        source="expression_orale",
        explanation=result.get("feedback", "") or _course_explanation(exercise),
        category="speaking",
    )

    total = lesson.exercises.filter(is_active=True).count()
    completed = UserExerciseProgress.objects.filter(
        user=user, lesson=lesson, is_completed=True
    ).count()
    percent = int(round((completed / total) * 100)) if total else 0
    lesson_done = total > 0 and completed >= total

    ulp, _ = UserLessonProgress.objects.get_or_create(
        user=user, lesson=lesson,
        defaults={"percent": 0, "is_completed": False, "completed_exercises": 0, "total_exercises": total},
    )
    ulp.total_exercises = total
    ulp.completed_exercises = completed
    ulp.percent = percent
    ulp.is_completed = lesson_done
    ulp.save()

    return JsonResponse({
        "ok": True,
        "score": score,
        "transcript": transcript,
        "feedback": result.get("feedback", ""),
        "points_covered": result.get("points_covered", []),
        "suggestions": result.get("suggestions", []),
        "criteria": result.get("criteria", {}),
        "is_correct": is_correct,
        "completed_exercises": completed,
        "total_exercises": total,
        "percent": percent,
        "is_completed": lesson_done,
    })


# =========================================================
# ✍️ API SOUMISSION EE
# =========================================================
@login_required
@require_POST
def submit_ee(request):
    """
    Reçoit: JSON avec exercise_id + text
    Évalue (GPT) → sauvegarde EESubmission → met à jour progression.
    """
    from ai_engine.services.eval_service import evaluate_ee

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    exercise_id = payload.get("exercise_id")
    text = (payload.get("text") or "").strip()

    if not exercise_id:
        return JsonResponse({"ok": False, "error": "missing_exercise_id"}, status=400)
    if not text:
        return JsonResponse({"ok": False, "error": "empty_text"}, status=400)

    exercise = CourseExercise.objects.select_related("lesson").filter(id=exercise_id).first()
    if not exercise:
        return JsonResponse({"ok": False, "error": "exercise_not_found"}, status=404)

    lesson = exercise.lesson
    user = request.user

    word_count = len(text.split())

    result = evaluate_ee(
        text=text,
        topic=exercise.question_text,
        instructions=exercise.instruction,
        level=lesson.level,
    )

    score = float(result.get("score", 0))

    EESubmission.objects.create(
        user=user,
        exercise=exercise,
        text=text,
        word_count=word_count,
        score=score,
        feedback_json=result,
    )

    is_correct = score >= 60
    prog, _ = UserExerciseProgress.objects.get_or_create(
        user=user,
        exercise=exercise,
        defaults={"lesson": lesson},
    )
    if prog.lesson_id != lesson.id:
        prog.lesson = lesson
    prog.mark_attempt(selected="EE", correct=is_correct)
    prog.save()
    record_detailed_attempt(
        user=user,
        exercise=exercise,
        selected="EE",
        is_correct=is_correct,
        source="expression_ecrite",
        explanation=result.get("feedback", "") or _course_explanation(exercise),
        category="writing",
    )

    total = lesson.exercises.filter(is_active=True).count()
    completed = UserExerciseProgress.objects.filter(
        user=user, lesson=lesson, is_completed=True
    ).count()
    percent = int(round((completed / total) * 100)) if total else 0
    lesson_done = total > 0 and completed >= total

    ulp, _ = UserLessonProgress.objects.get_or_create(
        user=user, lesson=lesson,
        defaults={"percent": 0, "is_completed": False, "completed_exercises": 0, "total_exercises": total},
    )
    ulp.total_exercises = total
    ulp.completed_exercises = completed
    ulp.percent = percent
    ulp.is_completed = lesson_done
    ulp.save()

    return JsonResponse({
        "ok": True,
        "score": score,
        "feedback": result.get("feedback", ""),
        "errors": result.get("errors", []),
        "corrected_version": result.get("corrected_version", ""),
        "criteria": result.get("criteria", {}),
        "word_count": word_count,
        "is_correct": is_correct,
        "completed_exercises": completed,
        "total_exercises": total,
        "percent": percent,
        "is_completed": lesson_done,
    })
