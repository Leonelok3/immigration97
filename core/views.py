from datetime import timedelta
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from xhtml2pdf import pisa

from actualite.models import NewsItem
from eligibility.models import Session as EligSession
from billing.services import has_active_access

from .models import ConsultationRequest
from .forms import ConsultationForm


def user_is_subscriber(user):
    return has_active_access(user)


@login_required
def wizard_page(request):
    if not user_is_subscriber(request.user):
        return redirect("/billing/subscribe/")
    return render(request, "wizard/index.html")


@login_required
def wizard_steps_page(request):
    if not user_is_subscriber(request.user):
        return redirect("/billing/subscribe/")
    return render(request, "wizard/steps.html")


@login_required
def wizard_result_page(request, session_id: int):
    if not user_is_subscriber(request.user):
        return redirect("/billing/subscribe/")

    try:
        sess = EligSession.objects.get(id=session_id, user=request.user)
    except EligSession.DoesNotExist:
        return redirect("/wizard/")

    return render(
        request,
        "wizard/result.html",
        {
            "session_id": session_id,
            "result": sess.result_json or {},
        },
    )


@login_required
def wizard_pdf(request):
    if not user_is_subscriber(request.user):
        return redirect("/billing/subscribe/")

    session_id = request.GET.get("session_id")
    if not session_id:
        return HttpResponseBadRequest("session_id manquant")

    try:
        sess = EligSession.objects.get(id=int(session_id), user=request.user)
    except EligSession.DoesNotExist:
        return HttpResponseBadRequest("session introuvable")

    data = sess.result_json or {}
    if not data or not data.get("results"):
        data = {"results": []}

    html = render(request, "wizard/pdf.html", {"data": data}).content.decode("utf-8")
    pdf_io = BytesIO()
    pisa.CreatePDF(html, dest=pdf_io)

    response = HttpResponse(pdf_io.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="plan_immigration_session_{session_id}.pdf"'
    return response


@login_required
def dashboard_page(request):
    return render(request, "dashboard/index.html")


def _safe_reverse(name: str, fallback: str = "#") -> str:
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback


@staff_member_required
def arsenal_ia_page(request):
    stats = {
        "scraped_leads": 0,
        "verified_opportunities": 0,
        "scam_assessments": 0,
        "high_risk_scams": 0,
        "job_visa_assessments": 0,
        "recruiter_contacts": 0,
        "job_leads": 0,
        "public_offers": 0,
    }
    try:
        from outreach.models import JobVisaEligibilityAssessment, RecruiterContact, ScrapedEmployerLead, ScamAssessment
        from job_agent.models import JobLead, PublicJobOffer

        stats["scraped_leads"] = ScrapedEmployerLead.objects.count()
        stats["verified_opportunities"] = ScrapedEmployerLead.objects.filter(verification_decision="verified").count()
        stats["scam_assessments"] = ScamAssessment.objects.count()
        stats["high_risk_scams"] = ScamAssessment.objects.filter(risk_level="high").count()
        stats["job_visa_assessments"] = JobVisaEligibilityAssessment.objects.count()
        stats["recruiter_contacts"] = RecruiterContact.objects.count()
        stats["job_leads"] = JobLead.objects.count()
        stats["public_offers"] = PublicJobOffer.objects.filter(is_active=True).count()
    except Exception:
        pass

    agents = [
        {
            "group": "Prospection internationale",
            "name": "Agent web employeurs",
            "status": "Nouveau",
            "description": "Scrape les sources web pour trouver les employeurs avec signaux visa, LMIA, sponsoring ou recrutement international.",
            "links": [
                {"label": "Opportunités vérifiées", "url": _safe_reverse("outreach:verified_opportunities", "/opportunites-verifiees/")},
                {"label": "Leads scrapés", "url": _safe_reverse("admin:outreach_scrapedemployerlead_changelist")},
                {"label": "Commande", "url": "#daily-command"},
            ],
            "metric": stats["scraped_leads"],
            "metric_label": "leads web",
        },
        {
            "group": "Prospection internationale",
            "name": "Agent Opportunités Vérifiées",
            "status": "Actif",
            "description": "Qualifie chaque opportunité avec score, signaux pays/visa/secteur et décision: vérifiée, à revoir ou faible.",
            "links": [
                {"label": "Page opportunités", "url": _safe_reverse("outreach:verified_opportunities", "/opportunites-verifiees/")},
                {"label": "Leads vérifiés", "url": _safe_reverse("admin:outreach_scrapedemployerlead_changelist") + "?verification_decision__exact=verified"},
                {"label": "Commande", "url": "#verified-command"},
            ],
            "metric": stats["verified_opportunities"],
            "metric_label": "vérifiées",
        },
        {
            "group": "Protection candidats",
            "name": "Agent Anti-Arnaque",
            "status": "Actif",
            "description": "Détecte frais suspects, promesses de visa garanti, emails gratuits, faux recruteurs et demandes de paiement risquées.",
            "links": [
                {"label": "Analyses anti-arnaque", "url": _safe_reverse("admin:outreach_scamassessment_changelist")},
                {"label": "Commande", "url": "#scam-command"},
            ],
            "metric": stats["scam_assessments"],
            "metric_label": "analyses",
        },
        {
            "group": "Profil candidat",
            "name": "Agent Éligibilité Emploi + Visa",
            "status": "Actif",
            "description": "Analyse âge, métier, expérience, langues, documents, budget et pays cibles pour recommander pays, métiers, documents et plan d'action.",
            "links": [
                {"label": "Lancer agent", "url": _safe_reverse("outreach:job_visa_eligibility", "/eligibilite-emploi-visa/")},
                {"label": "Résultats admin", "url": _safe_reverse("admin:outreach_jobvisaeligibilityassessment_changelist")},
                {"label": "Opportunités", "url": _safe_reverse("outreach:verified_opportunities", "/opportunites-verifiees/")},
            ],
            "metric": stats["job_visa_assessments"],
            "metric_label": "profils évalués",
        },
        {
            "group": "Prospection internationale",
            "name": "Agent cibles employeurs",
            "status": "Actif",
            "description": "Analyse les candidats et recherches emploi pour générer des cibles employeurs par secteur et pays.",
            "links": [
                {"label": "Contacts recruteurs", "url": _safe_reverse("admin:outreach_recruitercontact_changelist")},
                {"label": "Campagnes", "url": _safe_reverse("admin:outreach_outreachcampaign_changelist")},
            ],
            "metric": stats["recruiter_contacts"],
            "metric_label": "contacts",
        },
        {
            "group": "Emploi et candidature",
            "name": "Job Agent",
            "status": "Actif",
            "description": "Centralise recherches, offres, matching CV, packs de candidature et suivi Kanban.",
            "links": [
                {"label": "Dashboard", "url": _safe_reverse("job_agent:dashboard", "/jobs/")},
                {"label": "Offres", "url": _safe_reverse("job_agent:lead_list", "/jobs/offres/")},
                {"label": "Offres publiques", "url": _safe_reverse("job_agent:public_offers", "/jobs/offres-publiques/")},
            ],
            "metric": stats["job_leads"],
            "metric_label": "leads emploi",
        },
        {
            "group": "Emploi et candidature",
            "name": "Matching IA CV-Offre",
            "status": "Actif",
            "description": "Compare le CV et les descriptions d'offres avec scoring heuristique et embeddings OpenAI si disponibles.",
            "links": [
                {"label": "Documents candidat", "url": _safe_reverse("job_agent:documents_edit", "/jobs/documents/")},
                {"label": "Ajouter une offre", "url": _safe_reverse("job_agent:lead_add", "/jobs/offres/ajouter/")},
            ],
            "metric": stats["public_offers"],
            "metric_label": "offres publiques",
        },
        {
            "group": "Emploi et candidature",
            "name": "Agent relance candidature",
            "status": "Actif",
            "description": "Envoie les relances automatiques apres candidature selon les templates de suivi.",
            "links": [
                {"label": "Templates relance", "url": _safe_reverse("admin:job_agent_followuptemplate_changelist")},
                {"label": "Commande", "url": "#followup-command"},
            ],
            "metric": "",
            "metric_label": "daily follow-up",
        },
        {
            "group": "Documents IA",
            "name": "CV IA",
            "status": "Actif",
            "description": "Génération, amélioration et export de CV adaptés Canada, Europe et ATS.",
            "links": [
                {"label": "Créer un CV", "url": _safe_reverse("cv_generator:create_cv", "/cv-generator/")},
                {"label": "Mes CV", "url": _safe_reverse("cv_generator:cv_list", "/cv-generator/")},
            ],
            "metric": "",
            "metric_label": "CV",
        },
        {
            "group": "Documents IA",
            "name": "Lettres de motivation IA",
            "status": "Actif",
            "description": "Génère et organise les lettres de motivation selon le poste et le pays cible.",
            "links": [
                {"label": "Générateur", "url": _safe_reverse("motivation_letter:home", "/motivation/")},
            ],
            "metric": "",
            "metric_label": "lettres",
        },
        {
            "group": "Formation et examens",
            "name": "Agents CE/CO/EE/EO",
            "status": "Actif",
            "description": "Agents pédagogiques pour compréhension écrite/orale, expression écrite/orale et examens blancs.",
            "links": [
                {"label": "Préparation tests", "url": _safe_reverse("preparation_tests:home", "/prep/")},
                {"label": "API IA", "url": "/api/ai/"},
            ],
            "metric": "4",
            "metric_label": "agents",
        },
        {
            "group": "Immigration",
            "name": "Assistant visa et résidence",
            "status": "Actif",
            "description": "Outils de stratégie résidence permanente, visas, checklist et accompagnement.",
            "links": [
                {"label": "Résidence permanente", "url": "/residence-permanente/"},
                {"label": "Visa travail", "url": "/visa-travail/"},
                {"label": "Visa tourisme", "url": "/visa-tourisme/"},
            ],
            "metric": "",
            "metric_label": "immigration",
        },
    ]

    return render(request, "core/arsenal_ia.html", {"agents": agents, "stats": stats})


def home(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    top_week = (
        NewsItem.objects
        .filter(is_published=True, publish_date__gte=week_ago, publish_date__lte=now)
        .order_by("-views_count", "-publish_date")[:6]
    )

    if not top_week.exists():
        top_week = (
            NewsItem.objects
            .filter(is_published=True)
            .order_by("-is_featured", "-views_count", "-publish_date")[:6]
        )

    return render(request, "home.html", {"top_week": top_week})


# ======================================================
# CONSULTATION / ACCOMPAGNEMENT
# ======================================================

def consultation_request(request):
    """Page publique : demande de consultation / accompagnement personnalisé."""
    if request.method == "POST":
        form = ConsultationForm(request.POST, user=request.user if request.user.is_authenticated else None)
        if form.is_valid():
            obj = form.save(commit=False)
            if request.user.is_authenticated:
                obj.user = request.user
            obj.save()
            return redirect("consultation_success")
    else:
        form = ConsultationForm(user=request.user if request.user.is_authenticated else None)

    return render(request, "consultation/request.html", {"form": form})


def consultation_success(request):
    """Page de confirmation après soumission d'une demande."""
    return render(request, "consultation/success.html")
