from django.urls import path
from . import views

app_name = "visaetude"

urlpatterns = [
    path("", views.home, name="home"),
    path("profil/", views.profile, name="profile"),
    path("student-profile/", views.student_profile, name="student_profile"),  # ✅ ajouté
    path("pays/", views.countries_list, name="countries_list"),
    path("bourses/", views.scholarship_offers, name="scholarship_offers"),
    path("pays/<str:country>/", views.country_detail, name="country_detail"),
    path("parcours/", views.roadmap, name="roadmap"),
    path("checklist/", views.checklist, name="checklist"),
    path("coach/", views.coach_ai, name="coach_ai"),
    path("coach-api/", views.coach_ai_api, name="coach_ai_api"),
    path("resource/<int:resource_id>/", views.resource_view, name="resource_view"),
]
