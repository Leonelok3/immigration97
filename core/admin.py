from django.contrib import admin
from .models import ConsultationRequest, HomeSlide, ImmigrationAlertSubscriber


@admin.register(HomeSlide)
class HomeSlideAdmin(admin.ModelAdmin):
    list_display = [
        "order", "kicker", "title_before", "primary_label", "theme", "is_active", "updated_at",
    ]
    list_display_links = ["kicker"]
    list_editable = ["order", "theme", "is_active"]
    list_filter = ["is_active", "theme", "updated_at"]
    search_fields = ["kicker", "title_before", "title_accent", "subtitle", "primary_label"]
    readonly_fields = ["created_at", "updated_at", "image_recommendation"]
    fieldsets = (
        ("Contenu du slide", {
            "fields": ("kicker", "title_before", "title_accent", "subtitle")
        }),
        ("Appels à l'action", {
            "fields": ("primary_label", "primary_url", "secondary_label", "secondary_url")
        }),
        ("Visuel et affichage", {
            "fields": ("image_recommendation", "background_image", "theme", "order", "is_active")
        }),
        ("Dates", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Dimensions recommandées")
    def image_recommendation(self, obj):
        return "1920 x 900 px, WebP ou JPG, moins de 350 Ko. Garder le centre sombre pour le texte."


@admin.register(ConsultationRequest)
class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = [
        "full_name", "email", "phone", "consultation_type",
        "destination_country", "budget", "status", "created_at",
    ]
    list_filter = ["status", "consultation_type", "budget", "created_at"]
    search_fields = ["full_name", "email", "phone", "message", "destination_country"]
    readonly_fields = ["created_at", "updated_at", "user"]
    list_editable = ["status"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]

    fieldsets = (
        ("Informations du candidat", {
            "fields": ("user", "full_name", "email", "phone", "country")
        }),
        ("Demande", {
            "fields": ("consultation_type", "destination_country", "message", "budget", "preferred_date")
        }),
        ("Suivi interne", {
            "fields": ("status", "admin_notes", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")


@admin.register(ImmigrationAlertSubscriber)
class ImmigrationAlertSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "whatsapp", "country", "project_type", "channel", "is_active", "created_at"]
    list_filter = ["project_type", "channel", "is_active", "country", "created_at"]
    search_fields = ["email", "whatsapp", "country"]
    list_editable = ["is_active"]
    readonly_fields = ["created_at"]
    ordering = ["-created_at"]
