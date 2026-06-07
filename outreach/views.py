from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from outreach.forms import JobVisaEligibilityForm
from outreach.job_visa_eligibility import evaluate_job_visa_profile
from outreach.models import JobVisaEligibilityAssessment, RecruiterContact, ScrapedEmployerLead
from outreach.official_sources import get_sources


def verified_opportunities(request):
    country = request.GET.get("country", "").strip().upper()
    sector = request.GET.get("sector", "").strip().lower()
    risk = request.GET.get("risk", "").strip().lower()
    min_score = request.GET.get("min_score", "50").strip()
    q = request.GET.get("q", "").strip()

    try:
        min_score_int = max(0, min(int(min_score), 100))
    except ValueError:
        min_score_int = 50

    qs = (
        ScrapedEmployerLead.objects.select_related("scam_assessment")
        .filter(verification_score__gte=min_score_int)
        .exclude(status="rejected")
        .order_by("-verification_score", "-confidence_score", "-last_seen_at")
    )

    if country:
        if country == "EU":
            qs = qs.filter(country__in=["GB", "DE", "BE", "FR", "NL", "IE", "CH", "IT", "ES", "PT"])
        else:
            qs = qs.filter(country=country)
    if sector:
        qs = qs.filter(sector=sector)
    if risk:
        qs = qs.filter(scam_assessment__risk_level=risk)
    else:
        qs = qs.exclude(scam_assessment__risk_level="high")
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(company_name__icontains=q)
            | Q(location__icontains=q)
            | Q(evidence_text__icontains=q)
            | Q(visa_signal__icontains=q)
        )

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "filters": {
            "country": country,
            "sector": sector,
            "risk": risk,
            "min_score": min_score_int,
            "q": q,
        },
        "country_choices": ScrapedEmployerLead.COUNTRY_CHOICES,
        "sector_choices": RecruiterContact.SECTOR_CHOICES,
        "risk_choices": [("low", "Faible"), ("medium", "Moyen"), ("high", "Élevé")],
        "official_sources": get_sources(country=country, sector=sector),
        "total_count": qs.count(),
    }
    return render(request, "outreach/verified_opportunities.html", context)


def _candidate_initial(user) -> dict:
    initial = {"country": "Cameroun", "preferred_countries": "CA,NZ,AU,EU"}
    try:
        cp = user.candidate_profile
        initial.update(
            {
                "country": cp.country or "Cameroun",
                "city": cp.city,
                "preferred_countries": cp.preferred_location or "CA,NZ,AU,EU",
            }
        )
    except Exception:
        pass
    try:
        docs = user.candidate_documents
        initial["has_cv"] = bool(docs.cv_file or docs.cv_text)
    except Exception:
        pass
    return initial


@login_required
def job_visa_eligibility_start(request):
    if request.method == "POST":
        form = JobVisaEligibilityForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.user = request.user
            result = evaluate_job_visa_profile(form.cleaned_data)
            assessment.readiness_score = result["readiness_score"]
            assessment.recommended_countries = result["recommended_countries"]
            assessment.accessible_jobs = result["accessible_jobs"]
            assessment.missing_documents = result["missing_documents"]
            assessment.action_plan = result["action_plan"]
            assessment.result_summary = result["summary"]
            assessment.raw_result = result
            assessment.save()
            return redirect("outreach:job_visa_eligibility_result", pk=assessment.pk)
    else:
        form = JobVisaEligibilityForm(initial=_candidate_initial(request.user))

    return render(request, "outreach/job_visa_eligibility_form.html", {"form": form})


@login_required
def job_visa_eligibility_result(request, pk: int):
    assessment = get_object_or_404(JobVisaEligibilityAssessment, pk=pk, user=request.user)
    country_codes = [item.get("code") for item in assessment.recommended_countries if item.get("code")]
    opportunities = (
        ScrapedEmployerLead.objects.select_related("scam_assessment")
        .filter(country__in=country_codes, sector=assessment.sector, verification_score__gte=50)
        .exclude(status="rejected")
        .exclude(scam_assessment__risk_level="high")
        .order_by("-verification_score", "-confidence_score")[:6]
    )
    return render(
        request,
        "outreach/job_visa_eligibility_result.html",
        {"assessment": assessment, "opportunities": opportunities},
    )
