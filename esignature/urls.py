from django.urls import path

from . import views

app_name = "esignature"

urlpatterns = [
    path("upload/", views.upload_contract, name="upload_contract"),
    path("sign/<str:token>/", views.sign_contract, name="sign_contract"),
    path("sign/<str:token>/pdf/", views.preview_contract, name="preview_contract"),
    path("sign/<str:token>/submit/", views.submit_signature, name="submit_signature"),
]
