from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import models
import json
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .models import (
    VisaCountry, VisaResource, UserProfile,
    VisaProgress, UserProgress, University,
    CountryAdvice, Scholarship, StudentProfile,
    PublicScholarshipOffer,
)
from .forms import UserProfileForm, StudentProfileForm
from billing.services import has_candidate_access
from outreach.scholarship_scraper import is_direct_scholarship_url
from resources.models import Resource


RESOURCE_DESTINATION_MAP = {
    "canada": "canada",
    "france": "france",
    "belgique": "belgique",
    "allemagne": "allemagne",
    "italie": "italie",
    "usa": "international",
    "chine": "international",
}


# ── Helper paywall ──────────────────────────────────────────────
def _require_premium(request):
    """
    Retourne None si l'accès est OK, sinon un redirect vers billing:pricing.
    Usage : resp = _require_premium(request); if resp: return resp
    """
    if not request.user.is_authenticated:
        return redirect(f"{reverse('authentification:login')}?next={request.path}")
    if not has_candidate_access(request.user):
        messages.error(
            request,
            "🔒 Cette fonctionnalité est réservée aux abonnés Premium. "
            "Accédez à toutes les ressources pour 6 500 XAF/mois."
        )
        return redirect(f"{reverse('billing:pricing')}?next={request.path}")
    return None


# ── PAGES GRATUITES ─────────────────────────────────────────────

def home(request):
    return render(request, "visaetude/home.html")


def countries_list(request):
    """Liste des pays — GRATUIT (vitrine)."""
    user = request.user if request.user.is_authenticated else None
    if user:
        progress, _ = UserProgress.objects.get_or_create(user=user)
        if not progress.step_2_country:
            progress.step_2_country = True
            progress.save()

    db_countries = list(VisaCountry.objects.filter(is_active=True))
    if db_countries:
        countries = [
            {
                "code": c.slug,
                "nom": c.name,
                "short": c.short_label or "",
                "resource_dest": RESOURCE_DESTINATION_MAP.get(c.slug, "international"),
            }
            for c in db_countries
        ]
    else:
        countries = [
            {"code": "canada",    "nom": "Canada",       "short": "", "resource_dest": "canada"},
            {"code": "france",    "nom": "France",        "short": "", "resource_dest": "france"},
            {"code": "belgique",  "nom": "Belgique",      "short": "", "resource_dest": "belgique"},
            {"code": "usa",       "nom": "États-Unis",    "short": "", "resource_dest": "international"},
            {"code": "allemagne", "nom": "Allemagne",     "short": "", "resource_dest": "allemagne"},
            {"code": "italie",    "nom": "Italie",        "short": "", "resource_dest": "italie"},
            {"code": "chine",     "nom": "Chine",         "short": "", "resource_dest": "international"},
        ]

    has_premium = request.user.is_authenticated and has_candidate_access(request.user)
    featured_scholarships = PublicScholarshipOffer.objects.filter(is_active=True).order_by(
        "-confidence_score",
        "-created_at",
    )[:6]

    return render(request, "visaetude/countries_list.html", {
        "countries": countries,
        "has_premium": has_premium,
        "featured_scholarships": featured_scholarships,
    })


def scholarship_offers(request):
    """Bourses vérifiées par l'agent Immigration97."""
    offers = (
        PublicScholarshipOffer.objects.filter(is_active=True)
        .exclude(url="")
        .order_by("-confidence_score", "-updated_at", "-created_at")
    )
    query = (request.GET.get("q") or "").strip()
    country = (request.GET.get("country") or "").strip()
    level = (request.GET.get("level") or "").strip()
    funding = (request.GET.get("funding") or "").strip()

    if query:
        offers = offers.filter(
            models.Q(title__icontains=query)
            | models.Q(organization__icontains=query)
            | models.Q(country__icontains=query)
            | models.Q(description_text__icontains=query)
            | models.Q(requirements__icontains=query)
        )
    if country:
        offers = offers.filter(country__icontains=country)
    if level:
        offers = offers.filter(study_level=level)
    if funding:
        offers = offers.filter(funding_type=funding)

    africa_candidate_signals = (
        models.Q(confidence_score__gte=55)
        | models.Q(eligible_countries__icontains="Afrique")
        | models.Q(eligible_countries__icontains="Africa")
        | models.Q(eligible_countries__icontains="African")
        | models.Q(eligible_countries__icontains="Cameroun")
        | models.Q(eligible_countries__icontains="Cameroon")
        | models.Q(eligible_countries__icontains="International")
        | models.Q(description_text__icontains="Africa")
        | models.Q(description_text__icontains="Afrique")
        | models.Q(description_text__icontains="African")
        | models.Q(description_text__icontains="Cameroun")
        | models.Q(description_text__icontains="Cameroon")
        | models.Q(description_text__icontains="developing countries")
        | models.Q(requirements__icontains="Africa")
        | models.Q(requirements__icontains="Afrique")
        | models.Q(requirements__icontains="developing countries")
        | models.Q(source__icontains="daad")
        | models.Q(source__icontains="campusfrance")
        | models.Q(source__icontains="chevening")
        | models.Q(source__icontains="commonwealth")
        | models.Q(source__icontains="educanada")
    )
    offers = offers.filter(africa_candidate_signals)

    countries = (
        PublicScholarshipOffer.objects.filter(is_active=True)
        .exclude(country="")
        .order_by("country")
        .values_list("country", flat=True)
        .distinct()
    )
    offers = _dedupe_scholarship_offers(offers)
    offers_count = len(offers)
    for offer in offers:
        parsed_url = urlparse(offer.url or "")
        host = parsed_url.netloc.removeprefix("www.")
        offer.website_label = host or "Source officielle"
        offer.direct_apply_label = "Postuler sur la page officielle"
        offer.africa_focus_note = _scholarship_focus_note(offer)
    return render(request, "visaetude/scholarship_offers.html", {
        "offers": offers[:120],
        "offers_count": offers_count,
        "query": query,
        "selected_country": country,
        "selected_level": level,
        "selected_funding": funding,
        "countries": countries,
        "level_choices": PublicScholarshipOffer.LEVEL_CHOICES,
        "funding_choices": PublicScholarshipOffer.FUNDING_CHOICES,
    })


def _dedupe_scholarship_offers(offers):
    seen = set()
    unique_offers = []
    for offer in offers:
        if not is_direct_scholarship_url(offer.url):
            continue
        key = _canonical_scholarship_url(offer.url)
        if not key or key in seen:
            continue
        seen.add(key)
        unique_offers.append(offer)
    return unique_offers


def _canonical_scholarship_url(url: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.scheme or not parsed.netloc:
        return (url or "").strip().lower()
    ignored_prefixes = ("utm_",)
    ignored_keys = {"fbclid", "gclid", "msclkid", "source", "ref", "referrer"}
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in ignored_keys and not key.lower().startswith(ignored_prefixes)
    ]
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower().removeprefix("www."),
        query=urlencode(query, doseq=True),
        fragment="",
    )
    return urlunparse(normalized).rstrip("/").lower()


def _scholarship_focus_note(offer: PublicScholarshipOffer) -> str:
    text = " ".join(
        [
            offer.eligible_countries or "",
            offer.requirements or "",
            offer.description_text or "",
            offer.verification_label or "",
            offer.url or "",
        ]
    ).lower()
    if any(term in text for term in ("cameroon", "cameroun")):
        return "Signal Cameroun"
    if any(term in text for term in ("africa", "african", "afrique", "africain")):
        return "Ouverte aux Africains"
    if any(term in text for term in ("developing countries", "international", "global south")):
        return "Ouverte international"
    return "Éligibilité à vérifier"


# ── PAGES PREMIUM ────────────────────────────────────────────────

@login_required
def student_profile(request):
    """Profil étudiant — PREMIUM."""
    gate = _require_premium(request)
    if gate:
        return gate

    user = request.user
    instance, _ = StudentProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        form = StudentProfileForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            progress, _ = UserProgress.objects.get_or_create(user=user)
            if not progress.step_1_profile:
                progress.step_1_profile = True
                progress.save()
            messages.success(request, "✅ Profil étudiant enregistré.")
    else:
        form = StudentProfileForm(instance=instance)

    return render(request, "visaetude/student_profile.html", {
        "form": form,
        "user_is_authenticated": True,
    })


@login_required
def profile(request):
    """Profil visa de base — PREMIUM."""
    gate = _require_premium(request)
    if gate:
        return gate

    user = request.user
    instance, _ = UserProfile.objects.get_or_create(user=user)

    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            progress, _ = UserProgress.objects.get_or_create(user=user)
            if not progress.step_1_profile:
                progress.step_1_profile = True
                progress.save()
    else:
        form = UserProfileForm(instance=instance)

    return render(request, "visaetude/profile.html", {
        "form": form,
        "user_is_authenticated": True,
    })


def country_detail(request, country):
    """Détail d'un pays — PREMIUM pour le contenu complet."""
    country_obj = VisaCountry.objects.filter(slug=country, is_active=True).first()

    guides = {
        "canada":    "Guide complet pour étudier au Canada...",
        "france":    "Détails du visa étudiant France...",
        "usa":       "Étudier aux USA...",
        "belgique":  "Étudier en Belgique...",
        "allemagne": "Visa étudiant Allemagne...",
        "italie":    "Visa étudiant Italie...",
        "chine":     "Visa étudiant Chine...",
    }

    if not country_obj and country not in guides:
        return redirect("visaetude:countries_list")

    has_premium = request.user.is_authenticated and has_candidate_access(request.user)
    resource_dest = RESOURCE_DESTINATION_MAP.get(country, "international")
    guide_resources = Resource.objects.filter(
        is_active=True,
        category="guides_pdf",
        destination=resource_dest,
    )[:6]
    public_scholarships = PublicScholarshipOffer.objects.filter(
        is_active=True,
        country__icontains=country_obj.name if country_obj else country,
    ).order_by("-confidence_score", "-created_at")[:6]

    context = {
        "country": country_obj.name if country_obj else country.capitalize(),
        "country_slug": country,
        "resource_dest": resource_dest,
        "guide_resources": guide_resources,
        "guide": guides.get(country, guides.get("canada", "")),
        "universities": University.objects.filter(country=country_obj) if (country_obj and has_premium) else [],
        "advices": CountryAdvice.objects.filter(country=country_obj) if (country_obj and has_premium) else [],
        "scholarships": Scholarship.objects.filter(country=country_obj) if (country_obj and has_premium) else [],
        "public_scholarships": public_scholarships,
        "resources": country_obj.resources.all() if (country_obj and has_premium) else [],
        "has_premium": has_premium,
    }
    return render(request, "visaetude/country_detail.html", context)


def roadmap(request):
    """Parcours visa — PREMIUM."""
    gate = _require_premium(request)
    if gate:
        return gate

    visa_progress, _ = VisaProgress.objects.get_or_create(user=request.user)
    total_steps = 5
    completed_steps = visa_progress.completed_steps
    progress_percent = int((completed_steps / total_steps) * 100)
    progress_label = f"Étape {visa_progress.current_stage}/{total_steps}"

    return render(request, "visaetude/roadmap.html", {
        "visa_progress": visa_progress,
        "visa_progress_percent": progress_percent,
        "visa_progress_label": progress_label,
    })


def checklist(request):
    """Checklist documents — PREMIUM."""
    gate = _require_premium(request)
    if gate:
        return gate
    return render(request, "visaetude/checklist.html")


def coach_ai(request):
    """Coach IA — PREMIUM."""
    gate = _require_premium(request)
    if gate:
        return gate

    if request.user.is_authenticated:
        progress, _ = UserProgress.objects.get_or_create(user=request.user)
        if not progress.step_5_coach:
            progress.step_5_coach = True
            progress.save()

    return render(request, "visaetude/coach_ai.html")


def resource_view(request, resource_id):
    """Ressource individuelle — PREMIUM."""
    gate = _require_premium(request)
    if gate:
        return gate

    r = VisaResource.objects.filter(id=resource_id).first()
    if not r:
        return redirect("visaetude:countries_list")
    return render(request, "visaetude/resource_view.html", {"resource": r})


# ── API Coach IA ─────────────────────────────────────────────────

@csrf_exempt
def coach_ai_api(request):
    """API Coach IA — PREMIUM (vérifié côté API aussi)."""
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    if not request.user.is_authenticated or not has_candidate_access(request.user):
        return JsonResponse({"error": "Abonnement Premium requis."}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))
        user_message = data.get("message", "").strip()
        if not user_message:
            return JsonResponse({"error": "Message vide"}, status=400)

        # Placeholder IA — à brancher sur OpenAI
        bot_reply = (
            "Je suis le Coach IA Immigration97. Pour une réponse personnalisée, "
            "posez votre question sur votre destination et votre situation."
        )
        return JsonResponse({"reply": bot_reply})
    except Exception as e:
        return JsonResponse({"error": "Erreur interne"}, status=500)
