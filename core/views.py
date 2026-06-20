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
    orchestration = None
    orchestration_goal = ""
    if request.method == "POST":
        orchestration_goal = (request.POST.get("goal") or "").strip()
        try:
            from ai_engine.orchestrator import orchestrate_immigration97

            orchestration = orchestrate_immigration97(
                request.user if request.user.is_authenticated else None,
                orchestration_goal,
            )
        except Exception:
            orchestration = None

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

    return render(
        request,
        "core/arsenal_ia.html",
        {
            "agents": agents,
            "stats": stats,
            "orchestration": orchestration,
            "orchestration_goal": orchestration_goal,
        },
    )


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


# ======================================================
# MODE FACILE / ASSISTANT LOCAL SANS OPENAI
# ======================================================

OFFICIAL_LINK_GROUPS = [
    {
        "title": "Canada",
        "links": [
            {"label": "Immigration Canada - site officiel", "url": "https://www.canada.ca/fr/immigration-refugies-citoyennete.html"},
            {"label": "Permis d'études Canada", "url": "https://www.canada.ca/fr/immigration-refugies-citoyennete/services/etudier-canada.html"},
            {"label": "Permis de travail Canada", "url": "https://www.canada.ca/fr/immigration-refugies-citoyennete/services/travailler-canada.html"},
            {"label": "Guichet emplois Canada", "url": "https://www.guichetemplois.gc.ca/"},
        ],
    },
    {
        "title": "Allemagne",
        "links": [
            {"label": "Make it in Germany", "url": "https://www.make-it-in-germany.com/fr/"},
            {"label": "Visa et immigration Allemagne", "url": "https://www.auswaertiges-amt.de/fr/service/visa-und-aufenthalt"},
            {"label": "Reconnaissance des diplômes", "url": "https://www.anerkennung-in-deutschland.de/html/fr/index.php"},
            {"label": "Agence fédérale pour l'emploi", "url": "https://www.arbeitsagentur.de/en"},
        ],
    },
    {
        "title": "Europe et France",
        "links": [
            {"label": "Portail immigration UE", "url": "https://immigration-portal.ec.europa.eu/index_fr"},
            {"label": "EURES - emplois en Europe", "url": "https://eures.europa.eu/index_fr"},
            {"label": "France-Visas", "url": "https://france-visas.gouv.fr/"},
            {"label": "Campus France", "url": "https://www.campusfrance.org/fr"},
        ],
    },
    {
        "title": "Bourses et études",
        "links": [
            {"label": "DAAD - bourses Allemagne", "url": "https://www.daad.de/en/studying-in-germany/scholarships/"},
            {"label": "Erasmus+", "url": "https://erasmus-plus.ec.europa.eu/fr"},
            {"label": "Bourses du gouvernement français", "url": "https://www.campusfrance.org/fr/bourses-etudiants-etrangers"},
            {"label": "Bourses Canada", "url": "https://www.educanada.ca/scholarships-bourses/index.aspx?lang=fra"},
        ],
    },
]

LOCAL_ASSISTANT_ANSWERS = {
    "commencer": "Commence par choisir un objectif: étudier, travailler, chercher une bourse ou préparer un test de langue. Ensuite, prépare passeport, diplôme, CV et preuves financières.",
    "bourse": "Pour les bourses, vise les sources officielles: Campus France, DAAD, Erasmus+ et EduCanada. Prépare relevés, diplôme, CV, lettre de motivation et passeport.",
    "travail": "Pour le travail, commence par un CV clair, un métier précis, des offres avec lien officiel, et vérifie les signaux visa/sponsoring avant de postuler.",
    "canada": "Pour le Canada, utilise Canada.ca et Guichet-Emplois. Ne paie jamais quelqu'un qui promet un visa garanti.",
    "allemagne": "Pour l'Allemagne, utilise Make it in Germany, l'ambassade et Anerkennung in Deutschland pour vérifier visa, emploi et reconnaissance du diplôme.",
    "langue": "Pour les tests de langue, fais une leçon et un exercice par jour. Le dimanche, fais un examen blanc pour mesurer tes progrès.",
    "document": "Les documents de base sont: passeport, acte de naissance, diplômes, relevés, CV, preuves financières, photos et justificatifs d'expérience.",
}


def _official_links_for_route(route_key: str) -> list[dict[str, str]]:
    """Retourne quelques liens officiels prioritaires selon le parcours."""

    flat_links = [link for group in OFFICIAL_LINK_GROUPS for link in group["links"]]
    keywords = {
        "study": ("études", "Campus", "Permis d'études", "France", "Canada"),
        "work": ("travail", "emploi", "EURES", "Germany", "Agence"),
        "scholarship": ("bourses", "DAAD", "Erasmus", "Bourses"),
        "language": ("Campus", "Canada", "Germany"),
        "documents": ("France-Visas", "Immigration", "Canada"),
    }.get(route_key, ())

    selected = [
        link for link in flat_links
        if any(word.lower() in link["label"].lower() for word in keywords)
    ]
    return selected[:4] or flat_links[:4]


def _build_easy_recommendation(form_data) -> dict[str, object]:
    """Construit une orientation simple et une checklist sans appel IA."""

    goal = (form_data.get("goal") or "").strip()
    budget = (form_data.get("budget") or "").strip()
    job = (form_data.get("job") or "").strip()
    study_level = (form_data.get("study_level") or "").strip()
    country = (form_data.get("country") or "").strip()

    route_map = {
        "study": {
            "title": "Visa études",
            "url": _safe_reverse("visaetude:home", "/visa-etudes/"),
            "steps": ["Choisir un pays et une formation", "Préparer les documents scolaires", "Vérifier visa et preuves financières"],
        },
        "work": {
            "title": "Travail à l'international",
            "url": _safe_reverse("job_agent:public_offers", "/jobs/offres-publiques/"),
            "steps": ["Créer un CV clair", "Postuler via les liens officiels", "Vérifier visa, contrat et employeur"],
        },
        "scholarship": {
            "title": "Bourses d'études",
            "url": _safe_reverse("visaetude:scholarship_offers", "/visa-etudes/bourses/"),
            "steps": ["Identifier les bourses ouvertes aux étrangers", "Préparer CV, notes et motivation", "Postuler sur le site officiel"],
        },
        "language": {
            "title": "Tests de langue",
            "url": _safe_reverse("preparation_tests:home", "/prep/"),
            "steps": ["Faire la leçon du jour", "Faire l'exercice du jour", "Passer l'examen blanc du dimanche"],
        },
        "documents": {
            "title": "Documents et dossier",
            "url": "/documents/",
            "steps": ["Lister les documents", "Scanner en PDF lisible", "Classer par pays et objectif"],
        },
    }
    route_key = goal if goal in route_map else "study"
    route = route_map[route_key]

    checklist = [
        "Passeport valide",
        "Acte de naissance",
        "CV simple et à jour",
        "Diplômes et relevés disponibles en PDF",
        "Preuves financières ou plan de financement",
    ]
    if route_key == "study":
        checklist.extend(["Attestation d'admission ou liste d'écoles", "Lettre de motivation académique"])
    elif route_key == "work":
        checklist.extend(["Expérience professionnelle résumée", "Liens directs des offres ciblées", "Preuves de compétences"])
    elif route_key == "scholarship":
        checklist.extend(["Relevés de notes", "Recommandations si demandées", "Calendrier des dates limites"])
    elif route_key == "language":
        checklist.extend(["Niveau actuel estimé", "Objectif de score", "Planning quotidien CO/CE/EE/EO"])
    else:
        checklist.extend(["Photos conformes", "Traductions certifiées si demandées", "Nom des fichiers clair"])

    note = "Parcours économique: utilise d'abord les pages gratuites, les liens officiels et les contenus du jour."
    if budget in {"low", "very_low"}:
        note = "Budget faible: vise les bourses, les liens officiels gratuits et évite tout paiement non vérifié."

    return {
        "route_key": route_key,
        "route_title": route["title"],
        "route_url": route["url"],
        "steps": route["steps"],
        "checklist": checklist,
        "official_links": _official_links_for_route(route_key),
        "profile": {
            "age": form_data.get("age", "").strip(),
            "country": country or "Non précisé",
            "study_level": study_level or "Non précisé",
            "job": job or "Non précisé",
            "budget": budget or "Non précisé",
        },
        "note": note,
    }


def _local_assistant_answer(question: str) -> str:
    """Répond avec des règles locales pour éviter tout coût API."""

    normalized = question.lower().strip()
    if not normalized:
        return "Écris une question courte, par exemple: je veux commencer, bourse Canada, travail Allemagne."
    for keyword, answer in LOCAL_ASSISTANT_ANSWERS.items():
        if keyword in normalized:
            return answer
    return (
        "Je peux t'aider sans OpenAI. Dis si ton objectif est: études, travail, bourse, langue ou documents. "
        "Je te donnerai les prochaines étapes et les liens officiels."
    )


def easy_start_view(request):
    """Parcours ultra simple pour orienter les utilisateurs peu à l'aise au téléphone."""

    from django.contrib import messages
    from django.db import IntegrityError

    result = None
    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "alerts":
            from .models import ImmigrationAlertSubscriber

            email = (request.POST.get("email") or "").strip()
            whatsapp = (request.POST.get("whatsapp") or "").strip()
            if not email and not whatsapp:
                messages.error(request, "Ajoute au moins un email ou un numéro WhatsApp.")
            else:
                try:
                    ImmigrationAlertSubscriber.objects.create(
                        email=email,
                        whatsapp=whatsapp,
                        country=(request.POST.get("country") or "").strip(),
                        project_type=request.POST.get("project_type") or "news",
                        channel=request.POST.get("channel") or "email",
                    )
                    messages.success(request, "Alerte enregistrée. Tu recevras les nouveautés utiles.")
                except IntegrityError:
                    messages.info(request, "Cette alerte existe déjà. Aucun doublon ajouté.")
            return redirect("easy_start")

        result = _build_easy_recommendation(request.POST)

    return render(
        request,
        "core/start_easy.html",
        {
            "result": result,
            "official_link_groups": OFFICIAL_LINK_GROUPS,
            "local_answer": _local_assistant_answer(request.GET.get("q", "")),
        },
    )


def official_links_view(request):
    """Page publique de liens officiels uniquement."""

    return render(request, "core/official_links.html", {"official_link_groups": OFFICIAL_LINK_GROUPS})


def local_assistant_api(request):
    """Assistant local JSON, volontairement sans OpenAI."""

    from django.http import JsonResponse

    question = request.GET.get("q") or request.POST.get("q") or ""
    return JsonResponse(
        {
            "answer": _local_assistant_answer(question),
            "source": "local_fallback",
            "openai_used": False,
        }
    )
