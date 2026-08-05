from django.urls import path
from django.http import HttpResponse

app_name = "edu_platform"

urlpatterns = [
    path("", lambda request: HttpResponse("Edu Platform placeholder"), name="index"),
]
