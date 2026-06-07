from django.urls import path

from . import views

app_name = "outreach"

urlpatterns = [
    path("opportunites-verifiees/", views.verified_opportunities, name="verified_opportunities"),
    path("business/opportunites-verifiees/", views.verified_opportunities, name="business_verified_opportunities"),
    path("eligibilite-emploi-visa/", views.job_visa_eligibility_start, name="job_visa_eligibility"),
    path("eligibilite-emploi-visa/<int:pk>/", views.job_visa_eligibility_result, name="job_visa_eligibility_result"),
]
