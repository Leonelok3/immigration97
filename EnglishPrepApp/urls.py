from django.urls import path
from . import views

app_name = "englishprep"

urlpatterns = [
    # Dashboard principal anglais
    path("", views.dashboard, name="dashboard"),

    # Liste des tests (deux noms : test_list + exam_list)
    path("tests/", views.test_list, name="test_list"),
    path("examens/", views.test_list, name="exam_list"),

    # Passation d’un test + résultat
    path("test/<int:test_id>/", views.take_test, name="take_test"),
    path("test/<int:test_id>/resultat/", views.test_result, name="test_result"),

    # Historique complet
    path("historique/", views.test_history, name="test_history"),

    # Revoir uniquement les erreurs
    path(
        "test/<int:test_id>/erreurs/",
        views.review_incorrect,
        name="review_incorrect",
    ),

    # Analyse des compétences pour UNE session
    path(
        "session/<int:session_id>/analyse-competences/",
        views.test_skill_analysis,
        name="test_skill_analysis",
    ),

    # Hub IELTS / TOEFL / TOEIC
    path(
        "hub-examens/",
        views.english_exam_hub,
        name="exam_hub",              # nouveau nom "moderne"
    ),
    path(
        "hub-examens/legacy/",
        views.english_exam_hub,
        name="english_exam_hub",      # alias pour les vieux templates
    ),

    # Cours & exercices pour un test
    path(
        "test/<int:test_id>/cours-exercices/",
        views.exam_learning_path,
        name="exam_learning_path",
    ),
    path("lecon-du-jour/", views.english_daily_lesson, name="daily_lesson"),

    # Profil / progression anglais
    path("profil/", views.english_profile, name="profile"),
    path("profil/progression/", views.english_profile, name="profile_progress"),

    # Coach IA (page + API JSON)
    path("coach-ia/", views.ai_coach_page, name="ai_coach"),
    path("coach-ia/api/", views.ai_coach_api, name="ai_coach_api"),

    # EO / EE – soumissions IA
    path("api/submit-eo/", views.english_submit_eo, name="submit_eo"),
    path("api/submit-ee/", views.english_submit_ee, name="submit_ee"),
]
