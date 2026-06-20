from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    CandidateProfile,
    CandidateDocuments,
    JobSearch,
    JobLead,
    ApplicationPack,
    PublicJobOffer,
    AnswerTemplate,
    LetterTemplate,
    FollowUpTemplate,
)


# =========================================================
# Candidate Profile
# =========================================================
@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "full_name",
        "preferred_location",
        "preferred_remote",
        "language",
        "updated_at",
    )
    search_fields = ("user__username", "full_name", "preferred_location")
    list_filter = ("language", "preferred_remote")
    readonly_fields = ("created_at", "updated_at")


# =========================================================
# Candidate Documents
# =========================================================
@admin.register(CandidateDocuments)
class CandidateDocumentsAdmin(admin.ModelAdmin):
    list_display = ("user", "has_cv_text", "updated_at")
    readonly_fields = ("updated_at",)

    def has_cv_text(self, obj):
        return bool(obj.cv_text.strip())
    has_cv_text.boolean = True
    has_cv_text.short_description = "CV Texte"


# =========================================================
# Job Search
# =========================================================
@admin.register(JobSearch)
class JobSearchAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "title",
        "location",
        "remote_ok",
        "contract_type",
        "language",
        "created_at",
    )
    search_fields = ("title", "keywords", "location", "user__username")
    list_filter = ("language", "remote_ok", "contract_type")
    readonly_fields = ("created_at",)


# =========================================================
# Job Lead (CORE ADMIN)
# =========================================================
@admin.register(JobLead)
class JobLeadAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "title",
        "company",
        "score_colored",
        "status",
        "has_pack",
        "contact_email",
        "applied_at",
        "followup_sent_at",
        "created_at",
    )

    search_fields = (
        "title",
        "company",
        "location",
        "url",
        "contact_email",
        "user__username",
    )

    list_filter = (
        "status",
        "source",
        "created_at",
        "applied_at",
    )

    readonly_fields = ("created_at", "updated_at")

    ordering = ("-created_at",)
    actions = ("publish_selected_to_public",)

    # ---------- Custom Columns ----------

    def score_colored(self, obj):
        if obj.match_score >= 75:
            color = "green"
        elif obj.match_score >= 50:
            color = "orange"
        else:
            color = "red"

        return format_html(
            "<strong style='color:{};'>{}/100</strong>",
            color,
            obj.match_score,
        )

    score_colored.short_description = "Score"

    def has_pack(self, obj):
        return hasattr(obj, "pack")

    has_pack.boolean = True
    has_pack.short_description = "Pack"

    @admin.action(description="Publier les offres sélectionnées en offres publiques")
    def publish_selected_to_public(self, request, queryset):
        created = 0
        updated = 0
        skipped = 0

        for lead in queryset.exclude(url=""):
            if not (lead.title or "").strip():
                skipped += 1
                continue

            _offer, was_created = PublicJobOffer.objects.update_or_create(
                url=lead.url,
                defaults={
                    "source": lead.source or "Job Agent",
                    "title": (lead.title or "Offre")[:220],
                    "company": (lead.company or "Entreprise")[:220],
                    "location": (lead.location or "International")[:220],
                    "description_text": lead.description_text or lead.title or "Offre",
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.message_user(
            request,
            f"Publication terminée: {created} créées, {updated} mises à jour, {skipped} ignorées.",
        )


# =========================================================
# Application Pack
# =========================================================
@admin.register(ApplicationPack)
class ApplicationPackAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "lead",
        "ats_score",
        "ai_status",
        "has_email",
        "has_letter",
        "updated_at",
    )

    readonly_fields = ("created_at", "updated_at")

    def has_email(self, obj):
        return bool(obj.generated_email.strip())

    has_email.boolean = True
    has_email.short_description = "Email"

    def has_letter(self, obj):
        return bool(obj.generated_letter.strip())

    has_letter.boolean = True
    has_letter.short_description = "Lettre"


# =========================================================
# Public Job Offer
# =========================================================
@admin.register(PublicJobOffer)
class PublicJobOfferAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "location",
        "category",
        "source",
        "is_active",
        "created_at",
    )
    search_fields = ("title", "company", "location", "source", "url", "skills_keywords")
    list_filter = ("is_active", "source", "category")
    readonly_fields = ("created_at", "updated_at")


# =========================================================
# Answer Templates
# =========================================================
@admin.register(AnswerTemplate)
class AnswerTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "language", "key", "is_active")
    list_filter = ("language", "is_active")
    search_fields = ("title", "key", "content")


# =========================================================
# Letter Templates
# =========================================================
@admin.register(LetterTemplate)
class LetterTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "language", "is_active")
    list_filter = ("language", "is_active")
    search_fields = ("title", "content")


# =========================================================
# FollowUp Templates
# =========================================================
@admin.register(FollowUpTemplate)
class FollowUpTemplateAdmin(admin.ModelAdmin):
    list_display = ("title", "language", "is_active")
    list_filter = ("language", "is_active")
    search_fields = ("title", "subject", "content")
