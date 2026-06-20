from django.urls import path
from . import views, views_level_mock, views_mock_exam_format

app_name = "preparation_tests"

urlpatterns = [
    # =====================================================
    # 🏠 ACCUEIL GÉNÉRAL
    # =====================================================
    path("", views.home, name="home"),

    # =====================================================
    # 📚 LISTE DES EXAMENS
    # =====================================================
    path("exams/", views.exam_list, name="exam_list"),
    path("exam/<str:exam_code>/", views.exam_detail, name="exam_detail"),

    # =====================================================
    # 🇫🇷 HUBS EXAMENS FRANÇAIS
    # =====================================================
    path("fr/", views.french_exams, name="french_exams"),
    path("fr/tef/", views.tef_hub, name="tef_hub"),
    path("fr/tcf/", views.tcf_hub, name="tcf_hub"),
    path("fr/delf/", views.delf_hub, name="delf_hub"),
    path("fr/dalf/", views.dalf_hub, name="dalf_hub"),

    # =====================================================
    # 🎧 HUB CO (Compréhension Orale) - CECR
    # =====================================================
    path("fr/co/", views.co_hub, name="co_hub"),
    path("fr/co/<str:level>/", views.co_by_level, name="co_by_level"),

    # =====================================================
    # 📖 HUB CE (Compréhension Écrite) - CECR
    # =====================================================
    path("fr/ce/", views.ce_hub, name="ce_hub"),
    path("fr/ce/<str:level>/", views.ce_by_level, name="ce_by_level"),

    # =====================================================
    # 🎤 HUB EO (Expression Orale) - CECR
    # =====================================================
    path("fr/eo/", views.eo_hub, name="eo_hub"),
    path("fr/eo/<str:level>/", views.eo_by_level, name="eo_by_level"),

    # =====================================================
    # ✍️ HUB EE (Expression Écrite) - CECR
    # =====================================================
    path("fr/ee/", views.ee_hub, name="ee_hub"),
    path("fr/ee/<str:level>/", views.ee_by_level, name="ee_by_level"),

    # =====================================================
    # 🔄 API SOUMISSIONS EO / EE
    # =====================================================
    path("api/submit-eo/", views.submit_eo, name="submit_eo"),
    path("api/submit-ee/", views.submit_ee, name="submit_ee"),

    # =====================================================
    # 📝 EXAMEN BLANC (MOCK)
    # =====================================================
    path(
        "mock/<str:exam_code>/<str:section_code>/start/",
        views.start_mock_exam,
        name="start_mock_exam",
    ),
    path(
        "mock/<int:session_id>/",
        views.mock_exam_session,
        name="mock_exam_session",
    ),
    path(
        "mock/<int:session_id>/results/",
        views.mock_exam_results,
        name="mock_exam_results",
    ),

    # =====================================================
    # 🕒 SESSIONS (ANCIEN MOTEUR)
    # =====================================================
    path(
        "start/<str:exam_code>/",
        views.start_session,
        name="start_session",
    ),
    path(
        "start/<str:exam_code>/<str:section>/",
        views.start_session_with_section,
        name="start_session_with_section",
    ),
    path(
        "section/<int:attempt_id>/",
        views.take_section,
        name="take_section",
    ),
    path(
        "section/<int:attempt_id>/submit/<int:question_id>/",
        views.submit_answer,
        name="submit_answer",
    ),

    # =====================================================
    # 📊 RÉSULTATS & CORRECTIONS
    # =====================================================
    path(
        "result/<int:session_id>/",
        views.session_result,
        name="session_result",
    ),
    path(
        "correction/<int:session_id>/",
        views.session_correction,
        name="session_correction",
    ),
    path(
        "retry/<int:session_id>/",
        views.retry_session_errors,
        name="retry_session_errors",
    ),

    # =====================================================
    # 📜 CERTIFICATS
    # =====================================================
    path(
        "certificate/<str:exam_code>/<str:level>/download/",
        views.download_certificate,
        name="download_certificate",
    ),
    path(
        "certificate/verify/<str:public_id>/",
        views.verify_certificate,
        name="verify_certificate",
    ),

    # =====================================================
    # 📊 DASHBOARD & COACH IA
    # =====================================================
    path("dashboard/", views.dashboard_global, name="dashboard_global"),
    path("coach/history/", views.coach_ai_history, name="coach_ai_history"),
    path("coach/pdf/<int:report_id>/", views.coach_ai_pdf, name="coach_ai_pdf"),
    path("review/", views.session_review, name="session_review"),
    path("fr/lecons-du-jour/", views.monthly_packs_index, name="daily_packs_index"),
    path("fr/lecons-du-jour/<slug:slug>/", views.monthly_pack_detail, name="daily_pack_detail"),
    path("fr/sujets-du-mois/", views.monthly_packs_index, name="monthly_packs_index"),
    path("fr/sujets-du-mois/<slug:slug>/", views.monthly_pack_detail, name="monthly_pack_detail"),
    path("fr/anciens-sujets/", views.past_exam_subjects_index, name="past_exam_subjects_index"),
    path("fr/anciens-sujets/<slug:slug>/", views.past_exam_subject_detail, name="past_exam_subject_detail"),

    # =====================================================
    # 📅 PLAN D'ÉTUDE
    # =====================================================
    path(
        "study-plan/<str:exam_code>/",
        views.study_plan_view,
        name="study_plan",
    ),
    path(
        "study-plan/<str:exam_code>/complete/",
        views.complete_study_day,
        name="complete_study_day",
    ),

    # =====================================================
    # 🔄 API PROGRESSION EXERCICES
    # =====================================================
    path(
        "api/exercise-progress/",
        views.exercise_progress,
        name="exercise_progress",
    ),
    # Alias sans préfixe api/ pour compatibilité JS (fetch /prep/exercise-progress/)
    path(
        "exercise-progress/",
        views.exercise_progress,
    ),

    # =====================================================
    # 🏆 EXAMENS BLANCS FORMAT OFFICIEL (TEF/TCF/DELF/DALF)
    # =====================================================
    path(
        "fr/examen-officiel/historique/",
        views_mock_exam_format.exam_format_history,
        name="exam_format_history",
    ),
    path(
        "fr/revision-intelligente/",
        views_mock_exam_format.smart_revision,
        name="smart_revision",
    ),
    path(
        "fr/<str:exam_code>/examen/",
        views_mock_exam_format.exam_format_hub,
        name="exam_format_hub",
    ),
    path(
        "fr/<str:exam_code>/examen/<str:level>/",
        views_mock_exam_format.exam_format_exam,
        name="exam_format_exam",
    ),

    # =====================================================
    # 🧪 EXAMENS BLANCS PAR NIVEAU CECR
    # =====================================================
    path(
        "fr/examen-blanc/",
        views_level_mock.level_mock_hub,
        name="level_mock_hub",
    ),
    path(
        "fr/examen-blanc/historique/",
        views_level_mock.mock_exam_history,
        name="mock_exam_history",
    ),
    path(
        "fr/examen-blanc/<str:level>/",
        views_level_mock.level_mock_exam,
        name="level_mock_exam",
    ),

    # =====================================================
    # 📘 SECTIONS DE COURS PAR EXAMEN — ROUTES GÉNÉRIQUES
    # ⚠️ OBLIGATOIREMENT EN DERNIER : <str:...> capture tout.
    # Toute route fixe placée après serait inaccessible.
    # =====================================================
    path(
        "<str:exam_code>/<str:section>/lesson/<int:lesson_id>/",
        views.lesson_session,
        name="lesson_session",
    ),
    path(
        "<str:exam_code>/<str:section>/",
        views.course_section,
        name="course_section",
    ),
]
