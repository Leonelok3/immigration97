from django.urls import include, path

urlpatterns = [
    path("esignature/", include(("esignature.urls", "esignature"), namespace="esignature")),
]
