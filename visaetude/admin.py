from django.contrib import admin
from .models import PublicScholarshipOffer, VisaCountry, VisaResource


@admin.register(VisaCountry)
class VisaCountryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(VisaResource)
class VisaResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "country", "category", "resource_type", "order")
    list_filter = ("country", "category", "resource_type")
    search_fields = ("title", "step_label", "url")
    ordering = ("country", "order")


@admin.register(PublicScholarshipOffer)
class PublicScholarshipOfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "organization",
        "country",
        "study_level",
        "funding_type",
        "confidence_score",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "country", "study_level", "funding_type", "verification_label")
    search_fields = ("title", "organization", "country", "url", "description_text", "requirements")
    readonly_fields = ("first_seen_at", "last_seen_at", "created_at", "updated_at")
    ordering = ("-confidence_score", "-created_at")
