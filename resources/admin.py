from django.contrib import admin
from django.utils.html import format_html
from .models import Resource, ResourcePurchase


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "destination", "resource_type",
        "price_display", "access_type", "downloads",
        "is_active", "is_featured", "order",
    )
    list_filter   = ("category", "destination", "resource_type", "is_active", "is_premium", "is_free", "is_featured")
    search_fields = ("title", "description", "slug")
    list_editable = ("is_active", "is_featured", "order")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order", "-created_at")
    readonly_fields = ("downloads", "created_at", "slug_preview")

    fieldsets = (
        ("Informations principales", {
            "fields": ("title", "slug", "slug_preview", "description", "long_description",
                       "what_inside", "category", "destination", "resource_type")
        }),
        ("Médias", {
            "fields": ("cover_image", "preview_url"),
        }),
        ("Fichier", {
            "fields": ("file", "file_size"),
        }),
        ("Prix & Accès", {
            "fields": ("is_free", "price_xaf", "price_eur", "is_premium"),
            "description": (
                "is_free = téléchargement libre | "
                "price_xaf > 0 = vente à l'unité via WhatsApp | "
                "is_premium = inclus dans l'abonnement"
            ),
        }),
        ("Publication", {
            "fields": ("is_active", "is_featured", "order", "downloads", "created_at"),
        }),
    )

    def price_display(self, obj):
        if obj.is_free:
            return format_html('<span style="color:#16a34a;font-weight:700;">GRATUIT</span>')
        if obj.price_xaf:
            eur = f" / {obj.price_eur} €" if obj.price_eur else ""
            price_xaf = f"{obj.price_xaf:,}"
            return format_html(
                '<span style="color:#D4A843;font-weight:700;">{} XAF{}</span>',
                price_xaf, eur,
            )
        return format_html('<span style="color:#6366f1;font-weight:600;">Premium</span>')
    price_display.short_description = "Prix"

    def access_type(self, obj):
        badges = []
        if obj.is_free:
            badges.append('<span style="background:#dcfce7;color:#15803d;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;">LIBRE</span>')
        if obj.is_premium:
            badges.append('<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;">ABONNEMENT</span>')
        if obj.is_paid():
            badges.append('<span style="background:#ede9fe;color:#5b21b6;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;">VENTE</span>')
        return format_html(" ".join(badges)) if badges else format_html('<span style="color:#94a3b8;">—</span>')
    access_type.short_description = "Accès"

    def slug_preview(self, obj):
        if obj.pk:
            return format_html(
                '<a href="/ressources/{}/" target="_blank" style="color:#3b82f6;">/ressources/{}/</a>',
                obj.pk, obj.pk,
            )
        return "—"
    slug_preview.short_description = "URL publique"


@admin.register(ResourcePurchase)
class ResourcePurchaseAdmin(admin.ModelAdmin):
    list_display  = ("user", "resource", "amount_paid_xaf", "payment_method", "purchased_at", "is_active")
    list_filter   = ("is_active", "payment_method", "purchased_at")
    search_fields = ("user__email", "user__username", "resource__title", "payment_ref")
    list_editable = ("is_active",)
    ordering      = ("-purchased_at",)
    readonly_fields = ("purchased_at",)

    fieldsets = (
        ("Achat", {
            "fields": ("user", "resource", "amount_paid_xaf", "payment_method", "payment_ref"),
        }),
        ("Statut", {
            "fields": ("is_active", "notes", "purchased_at"),
        }),
    )

    actions = ["activate_purchases", "deactivate_purchases"]

    def activate_purchases(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} achat(s) activé(s).")
    activate_purchases.short_description = "Activer les achats sélectionnés"

    def deactivate_purchases(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} achat(s) désactivé(s).")
    deactivate_purchases.short_description = "Désactiver les achats sélectionnés"
