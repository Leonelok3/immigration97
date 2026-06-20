from django.urls import path
from . import views

app_name = "germanprep"

urlpatterns = [
    path("", views.home, name="home"),
    path("evaluation/", views.placement_test, name="placement_test"),
    path("profil/", views.german_profile, name="profile"),

    # Hub par niveau
    path("niveau/<str:level_code>/", views.level_detail, name="level_detail"),

    # Hub examens allemands
    path("exam-hub/", views.german_exam_hub, name="exam_hub"),

    # Examens / cours / tests
    path("examens/<slug:exam_slug>/", views.exam_detail, name="exam_detail"),
    path(
        "examens/<slug:exam_slug>/lecon/<int:lesson_id>/",
        views.lesson_detail,
        name="lesson_detail",
    ),
    path(
        "examens/<slug:exam_slug>/parcours/",
        views.german_exam_learning_path,
        name="exam_learning_path",
    ),
    path("lecon-du-jour/", views.german_daily_lesson, name="daily_lesson"),
    path("examens/<int:exam_id>/test/", views.take_practice_test, name="take_practice_test"),

    # Résultats & analyse
    path("session/<int:session_id>/resultat/", views.german_test_result, name="test_result"),
    path("session/<int:session_id>/review-incorrect/", views.german_review_incorrect, name="review_incorrect"),
    path("session/<int:session_id>/skills/", views.german_skill_analysis, name="skill_analysis"),

    # Tableau de bord global
    path("progression/", views.progress_dashboard, name="progress_dashboard"),

    # 🔹 COACH IA ALLEMAND
    path("coach/", views.german_ai_coach_page, name="ai_coach"),
    path("coach/api/", views.german_ai_coach_api, name="ai_coach_api"),

    # EO / EE – soumissions IA
    path("api/submit-eo/", views.german_submit_eo, name="submit_eo"),
    path("api/submit-ee/", views.german_submit_ee, name="submit_ee"),

    # ── EXAMENS BLANCS PAR NIVEAU ──
    path("examens-blancs/", views.german_mock_hub, name="mock_hub"),
    path("examens-blancs/<str:level_code>/", views.german_level_mock_exam, name="level_mock_exam"),
]
