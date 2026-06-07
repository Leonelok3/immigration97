import csv
from django.contrib import admin, messages
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils import timezone
from django.shortcuts import render, get_object_or_404
from django import forms

from .models import (
    JobVisaEligibilityAssessment,
    RecruiterContact,
    OutreachTemplate,
    OutreachCampaign,
    OutreachLog,
    ScrapedEmployerLead,
    ScamAssessment,
)
from .opportunity_verifier import verify_employer_lead
from .scam_guard import assess_scam_risk
from .services import (
    import_contacts_from_csv, import_contacts_from_excel,
    export_contacts_to_csv, send_campaign, send_single_email,
)


class ImportContactsForm(forms.Form):
    file = forms.FileField(
        label="Fichier CSV ou Excel (.csv / .xlsx)",
        help_text=(
            "Colonnes reconnues automatiquement : Entreprise, Email/Portail RH, Secteur, "
            "Région/Ville, Site Web, Téléphone, Notes… "
            "Les titres et sous-titres en haut du fichier sont ignorés automatiquement."
        ),
    )
    default_country = forms.ChoiceField(
        label="Pays par défaut (si pas de colonne Pays dans le fichier)",
        choices=[
            ("BE", "🇧🇪 Belgique"), ("CA", "🇨🇦 Canada"), ("FR", "🇫🇷 France"),
            ("DE", "🇩🇪 Allemagne"), ("CH", "🇨🇭 Suisse"), ("AU", "🇦🇺 Australie"),
            ("GB", "🇬🇧 Royaume-Uni"), ("US", "🇺🇸 États-Unis"),
        ],
        initial="BE",
    )
    encoding = forms.ChoiceField(
        label="Encodage (CSV seulement)",
        choices=[("utf-8-sig", "UTF-8 BOM (Excel FR)"), ("utf-8", "UTF-8"), ("latin-1", "Latin-1")],
        initial="utf-8-sig",
        required=False,
    )


@admin.register(RecruiterContact)
class RecruiterContactAdmin(admin.ModelAdmin):
    list_display = [
        "company_name", "contact_name", "email", "phone",
        "sector_badge", "country", "city", "status_badge",
        "source", "last_contacted_at", "created_at",
    ]
    list_filter = ["sector", "country", "status", "source", "created_at"]
    search_fields = ["company_name", "contact_name", "email", "city", "tags"]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]
    list_per_page = 50

    fieldsets = (
        ("Identité", {
            "fields": (("company_name", "contact_name"), ("job_title", "phone"), ("email", "website")),
        }),
        ("Catégorie", {
            "fields": (("sector", "country", "city"), "tags"),
        }),
        ("Workflow", {
            "fields": (("status", "source"), "notes"),
        }),
        ("Historique", {
            "fields": (("last_contacted_at", "last_replied_at"),),
            "classes": ("collapse",),
        }),
    )

    actions = [
        "action_export_csv",
        "action_mark_contacted",
        "action_mark_not_interested",
        "action_send_campaign_to_selected",
    ]

    @admin.display(description="Secteur")
    def sector_badge(self, obj):
        colors = {
            "agriculture": "#16a34a", "construction": "#ca8a04",
            "tech": "#2563eb", "sante": "#dc2626",
            "logistique": "#7c3aed", "hotellerie": "#db2777",
            "education": "#0891b2", "finance": "#059669",
        }
        color = colors.get(obj.sector, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_sector_display(),
        )

    @admin.display(description="Statut")
    def status_badge(self, obj):
        colors = {
            "new": "#6b7280", "contacted": "#2563eb", "opened": "#7c3aed",
            "replied": "#16a34a", "registered": "#059669",
            "not_interested": "#dc2626", "bounce": "#991b1b",
        }
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display(),
        )

    @admin.action(description="⬇️ Exporter la sélection en CSV")
    def action_export_csv(self, request, queryset):
        csv_data = export_contacts_to_csv(queryset)
        response = HttpResponse(csv_data, content_type="text/csv; charset=utf-8-sig")
        ts = timezone.now().strftime("%Y%m%d_%H%M")
        response["Content-Disposition"] = f'attachment; filename="recruteurs_{ts}.csv"'
        return response

    @admin.action(description="✅ Marquer comme : Contacté")
    def action_mark_contacted(self, request, queryset):
        count = queryset.update(status="contacted", last_contacted_at=timezone.now())
        self.message_user(request, f"{count} contact(s) marqué(s) comme contacté(s).")

    @admin.action(description="🚫 Marquer comme : Pas intéressé")
    def action_mark_not_interested(self, request, queryset):
        count = queryset.update(status="not_interested")
        self.message_user(request, f"{count} contact(s) marqué(s) non intéressé(s).")

    @admin.action(description="📧 Envoyer un email à la sélection")
    def action_send_campaign_to_selected(self, request, queryset):
        ids = ",".join(str(r.id) for r in queryset)
        return HttpResponseRedirect(
            reverse("admin:outreach_send_to_selected") + f"?ids={ids}"
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("import-csv/", self.admin_site.admin_view(self.import_csv_view), name="outreach_import_csv"),
            path("send-to-selected/", self.admin_site.admin_view(self.send_to_selected_view), name="outreach_send_to_selected"),
            path("template-preview/<int:template_id>/", self.admin_site.admin_view(self.template_preview_view), name="outreach_template_preview"),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["import_csv_url"] = reverse("admin:outreach_import_csv")
        return super().changelist_view(request, extra_context=extra_context)

    def import_csv_view(self, request):
        opts = self.model._meta
        if request.method == "POST":
            form = ImportContactsForm(request.POST, request.FILES)
            if form.is_valid():
                file_obj = form.cleaned_data["file"]
                encoding = form.cleaned_data.get("encoding") or "utf-8-sig"
                default_country = form.cleaned_data.get("default_country") or "BE"
                name = file_obj.name.lower()
                if name.endswith(".xlsx") or name.endswith(".xls"):
                    result = import_contacts_from_excel(file_obj, default_country=default_country)
                else:
                    result = import_contacts_from_csv(file_obj, encoding=encoding)
                level = messages.SUCCESS if not result["errors"] else messages.WARNING
                self.message_user(
                    request,
                    f"✅ Import terminé — {result['created']} créés, {result['updated']} mis à jour, "
                    f"{result['skipped']} ignorés."
                    + (f" ⚠️ {len(result['errors'])} erreur(s) : {'; '.join(result['errors'][:3])}" if result["errors"] else ""),
                    level,
                )
                return HttpResponseRedirect(reverse("admin:outreach_recruitercontact_changelist"))
        else:
            form = ImportContactsForm()

        context = {
            **self.admin_site.each_context(request),
            "title": "Importer des contacts recruteurs (CSV / Excel)",
            "form": form, "opts": opts, "media": self.media,
        }
        return render(request, "admin/outreach/import_contacts.html", context)

    def send_to_selected_view(self, request):
        opts = self.model._meta
        ids_str = request.GET.get("ids", "") or request.POST.get("ids", "")
        try:
            ids = [int(i) for i in ids_str.split(",") if i.strip()]
        except ValueError:
            ids = []
        recruiters = RecruiterContact.objects.filter(id__in=ids)
        templates = OutreachTemplate.objects.filter(is_active=True)

        if request.method == "POST":
            template_id = request.POST.get("template_id")
            create_campaign = request.POST.get("create_campaign") == "1"
            campaign_name = request.POST.get("campaign_name", "").strip()
            if not template_id:
                self.message_user(request, "Sélectionnez un template.", messages.ERROR)
            else:
                tmpl = get_object_or_404(OutreachTemplate, pk=template_id)
                campaign = None
                if create_campaign and campaign_name:
                    campaign = OutreachCampaign.objects.create(
                        name=campaign_name, template=tmpl,
                        created_by=request.user, status="sending",
                    )
                sent = failed = 0
                for r in recruiters:
                    ok = send_single_email(r, tmpl, campaign=campaign)
                    if ok:
                        sent += 1
                    else:
                        failed += 1
                if campaign:
                    campaign.sent_count = sent
                    campaign.total_recipients = recruiters.count()
                    campaign.status = "sent"
                    campaign.sent_at = timezone.now()
                    campaign.save()
                self.message_user(
                    request,
                    f"📧 Envoi terminé — {sent} envoyé(s), {failed} échoué(s).",
                    messages.SUCCESS if failed == 0 else messages.WARNING,
                )
                return HttpResponseRedirect(reverse("admin:outreach_recruitercontact_changelist"))

        context = {
            **self.admin_site.each_context(request),
            "title": f"Envoyer un email à {recruiters.count()} contact(s)",
            "recruiters": recruiters, "templates": templates, "ids": ids_str, "opts": opts,
        }
        return render(request, "admin/outreach/send_to_selected.html", context)

    def template_preview_view(self, request, template_id):
        tmpl = get_object_or_404(OutreachTemplate, pk=template_id)

        class FakeRecruiter:
            company_name = "Ferme ABC Canada"
            contact_name = "Jean Tremblay"
            job_title = "Directeur RH"
            email = "rh@ferme-abc.ca"
            phone = "+1 514 000 0000"
            website = "https://ferme-abc.ca"
            sector = "agriculture"
            country = "CA"
            city = "Montréal"
            SECTOR_CHOICES = RecruiterContact.SECTOR_CHOICES
            COUNTRY_CHOICES = RecruiterContact.COUNTRY_CHOICES

        from .services import render_template
        try:
            html = render_template(tmpl.body_html, FakeRecruiter())
        except Exception as e:
            html = f"<p style='color:red'>Erreur de rendu : {e}</p><pre>{tmpl.body_html}</pre>"
        return HttpResponse(html)


@admin.register(OutreachTemplate)
class OutreachTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "language", "subject", "is_active", "preview_link", "updated_at"]
    list_editable = ["is_active"]
    list_filter = ["language", "is_active"]
    search_fields = ["name", "subject"]

    @admin.display(description="Aperçu")
    def preview_link(self, obj):
        url = reverse("admin:outreach_template_preview", args=[obj.pk])
        return format_html('<a href="{}" target="_blank">👁 Voir le rendu</a>', url)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["body_html"].widget.attrs["rows"] = 25
        form.base_fields["body_text"].widget.attrs["rows"] = 12
        return form


@admin.register(OutreachCampaign)
class OutreachCampaignAdmin(admin.ModelAdmin):
    list_display = [
        "name", "template", "status_badge", "total_recipients",
        "sent_count", "opened_count", "replied_count", "sent_at", "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["total_recipients", "sent_count", "opened_count", "replied_count", "status", "sent_at"]

    fieldsets = (
        ("Campagne", {"fields": ("name", "template", "created_by")}),
        ("Filtres destinataires", {
            "fields": ("filter_sectors", "filter_countries", "filter_status"),
            "description": "Laissez vide pour tous. Valeurs séparées par des virgules.",
        }),
        ("Statistiques", {
            "fields": ("status", ("total_recipients", "sent_count"), ("opened_count", "replied_count"), "sent_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["action_launch", "action_dry_run"]

    @admin.display(description="Statut")
    def status_badge(self, obj):
        colors = {"draft": "#6b7280", "sending": "#2563eb", "sent": "#16a34a", "paused": "#ca8a04"}
        color = colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:11px">{}</span>',
            color, obj.get_status_display(),
        )

    @admin.action(description="🚀 Lancer l'envoi")
    def action_launch(self, request, queryset):
        for c in queryset:
            if c.status == "sent":
                self.message_user(request, f"'{c.name}' déjà envoyée.", messages.WARNING)
                continue
            result = send_campaign(c)
            self.message_user(
                request,
                f"📧 '{c.name}' — {result['sent']} envoyé(s), {result['failed']} échoué(s) / {result['total']}.",
                messages.SUCCESS if result["failed"] == 0 else messages.WARNING,
            )

    @admin.action(description="🔍 Simulation (compter sans envoyer)")
    def action_dry_run(self, request, queryset):
        for c in queryset:
            result = send_campaign(c, dry_run=True)
            self.message_user(request, f"[DRY-RUN] '{c.name}' → {result['total']} contact(s) ciblé(s).", messages.INFO)


@admin.register(OutreachLog)
class OutreachLogAdmin(admin.ModelAdmin):
    list_display = ["campaign", "recruiter", "sent_at", "opened", "clicked", "bounced", "error"]
    list_filter = ["campaign", "opened", "bounced", "sent_at"]
    search_fields = ["recruiter__email", "recruiter__company_name", "campaign__name"]
    readonly_fields = ["tracking_id", "sent_at", "opened_at"]
    date_hierarchy = "sent_at"


@admin.register(ScrapedEmployerLead)
class ScrapedEmployerLeadAdmin(admin.ModelAdmin):
    list_display = [
        "company_name",
        "title",
        "country",
        "sector",
        "confidence_score",
        "verification_score",
        "verification_decision",
        "scam_risk_badge",
        "status",
        "last_seen_at",
    ]
    list_filter = ["country", "sector", "status", "verification_decision", "confidence_score"]
    search_fields = ["company_name", "title", "job_url", "evidence_text", "visa_signal"]
    readonly_fields = [
        "first_seen_at",
        "last_seen_at",
        "created_at",
        "updated_at",
        "raw_data",
        "verification_score",
        "verification_decision",
        "verification_notes",
        "verification_signals",
    ]
    ordering = ["-last_seen_at", "-confidence_score"]
    actions = ["run_verification", "run_scam_assessment", "mark_reviewed", "mark_rejected"]

    @admin.display(description="Risque arnaque")
    def scam_risk_badge(self, obj):
        assessment = getattr(obj, "scam_assessment", None)
        if not assessment:
            return "—"
        colors = {"low": "#16a34a", "medium": "#d97706", "high": "#dc2626"}
        return format_html(
            '<strong style="color:{}">{} ({})</strong>',
            colors.get(assessment.risk_level, "#6b7280"),
            assessment.get_risk_level_display(),
            assessment.risk_score,
        )

    @admin.action(description="Qualifier avec Agent Opportunités Vérifiées")
    def run_verification(self, request, queryset):
        updated = 0
        for lead in queryset:
            result = verify_employer_lead(lead)
            lead.verification_score = result.score
            lead.verification_decision = result.decision
            lead.verification_notes = result.notes
            lead.verification_signals = result.signals
            if result.decision == "verified":
                lead.status = "reviewed"
            elif result.decision == "weak":
                lead.status = "rejected"
            lead.save(
                update_fields=[
                    "verification_score",
                    "verification_decision",
                    "verification_notes",
                    "verification_signals",
                    "status",
                    "updated_at",
                ]
            )
            updated += 1
        messages.success(request, f"{updated} lead(s) qualifié(s).")

    @admin.action(description="Analyser avec Agent Anti-Arnaque")
    def run_scam_assessment(self, request, queryset):
        updated = 0
        for lead in queryset:
            result = assess_scam_risk(lead)
            ScamAssessment.objects.update_or_create(
                lead=lead,
                defaults={
                    "risk_score": result.risk_score,
                    "risk_level": result.risk_level,
                    "flags": result.flags,
                    "recommendation": result.recommendation,
                },
            )
            updated += 1
        messages.success(request, f"{updated} lead(s) analysé(s) anti-arnaque.")

    @admin.action(description="Marquer comme vérifié")
    def mark_reviewed(self, request, queryset):
        updated = queryset.update(status="reviewed")
        messages.success(request, f"{updated} lead(s) marqué(s) comme vérifié(s).")

    @admin.action(description="Rejeter")
    def mark_rejected(self, request, queryset):
        updated = queryset.update(status="rejected")
        messages.warning(request, f"{updated} lead(s) rejeté(s).")


@admin.register(ScamAssessment)
class ScamAssessmentAdmin(admin.ModelAdmin):
    list_display = ["lead", "risk_level", "risk_score", "assessed_at"]
    list_filter = ["risk_level", "risk_score", "assessed_at"]
    search_fields = ["lead__company_name", "lead__title", "lead__job_url", "recommendation"]
    readonly_fields = ["lead", "risk_score", "risk_level", "flags", "recommendation", "assessed_at", "created_at"]
    ordering = ["-assessed_at", "-risk_score"]


@admin.register(JobVisaEligibilityAssessment)
class JobVisaEligibilityAssessmentAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "profession",
        "sector",
        "country",
        "readiness_score",
        "has_passport",
        "has_cv",
        "created_at",
    ]
    list_filter = [
        "sector",
        "country",
        "education_level",
        "french_level",
        "english_level",
        "has_passport",
        "has_cv",
        "budget",
        "readiness_score",
        "created_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "profession",
        "country",
        "city",
        "preferred_countries",
    ]
    readonly_fields = [
        "readiness_score",
        "recommended_countries",
        "accessible_jobs",
        "missing_documents",
        "action_plan",
        "result_summary",
        "raw_result",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"
    ordering = ["-created_at", "-readiness_score"]
