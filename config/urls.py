from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse
from django.shortcuts import render
from django.urls import path, include
from django.views.generic import RedirectView
from django.contrib.staticfiles import finders


def _serve_sw(request):
    """Sert sw.js depuis /sw.js (scope root pour le Service Worker)."""
    path = finders.find('sw.js')
    if not path:
        from django.http import Http404
        raise Http404
    resp = FileResponse(open(path, 'rb'), content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-cache'
    return resp


def _serve_ads_txt(request):
    """Sert ads.txt depuis /ads.txt pour Google AdSense."""
    from django.http import HttpResponse
    content = "google.com, pub-8153544065381730, DIRECT, f08c47fec0942fa0\n"
    return HttpResponse(content, content_type='text/plain')

def about_page(request):
    return render(request, "about.html")

def services_page(request):
    return render(request, "services.html")
from permanent_residence import views as pr_views
from core.views import (
    wizard_page,
    wizard_result_page,
    wizard_pdf,
    wizard_steps_page,
    dashboard_page,
    arsenal_ia_page,
    consultation_request,
    consultation_success,
)

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from django.contrib.sitemaps.views import sitemap
from actualite.sitemaps import NewsItemSitemap


def home(request):
    from billing.models import SubscriptionPlan
    from actualite.models import NewsItem
    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    top_week = (NewsItem.objects.filter(is_published=True, publish_date__gte=week_ago, publish_date__lte=now)
                .order_by("-views_count", "-publish_date")[:6])
    if not top_week.exists():
        top_week = NewsItem.objects.filter(is_published=True).order_by("-is_featured", "-views_count", "-publish_date")[:6]
    candidate_plans = list(SubscriptionPlan.objects.filter(is_active=True, plan_type="candidate").order_by("order", "price_xaf"))
    recruiter_plans = list(SubscriptionPlan.objects.filter(is_active=True, plan_type="recruiter").order_by("order"))
    return render(request, "home.html", {
        "top_week": top_week,
        "candidate_plans": candidate_plans,
        "recruiter_plans": recruiter_plans,
    })


sitemaps = {"actualite": NewsItemSitemap}


urlpatterns = [
    path("sw.js", _serve_sw, name="service_worker"),
    path("ads.txt", _serve_ads_txt, name="ads_txt"),
    path("admin/", admin.site.urls),
    path("", home, name="home"),

    path(
        "authentification/",
        include(("authentification.urls", "authentification"), namespace="authentification"),
    ),

    path("documents/", include("DocumentsApp.urls")),

    path("visa-photo/", include("photos.urls")),

    path(
        "cv-generator/",
        include(("cv_generator.urls", "cv_generator"), namespace="cv_generator"),
    ),

    path(
        "motivation/",
        include(("MotivationLetterApp.urls", "motivation_letter"), namespace="motivation_letter"),
    ),

    path("visa-etudes/", include("visaetude.urls")),

    path("billing/", include(("billing.urls", "billing"), namespace="billing")),

    path(
        "prep/",
        include(("preparation_tests.urls", "preparation_tests"), namespace="preparation_tests"),
    ),

    path("visa-travail/", include("VisaTravailApp.urls")),
    path("visa-tourisme/", include("VisaTourismeApp.urls")),

    path("residence-permanente/", pr_views.home_view, name="residence_permanente"),
    path("rp/", pr_views.home_view, name="rp_shortcut"),
    path("pr/", include("permanent_residence.urls")),

    path("actualite/", include(("actualite.urls", "actualite"), namespace="actualite")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),

    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/eligibility/", include("eligibility.urls")),
    path("api/radar/", include("radar.urls")),

    path("wizard/", wizard_page, name="wizard"),
    path("wizard/result/<int:session_id>/", wizard_result_page, name="wizard_result"),
    path("wizard/checklist.pdf", wizard_pdf, name="wizard_pdf"),
    path("wizard/steps/", wizard_steps_page, name="wizard_steps"),
    path("dashboard/", dashboard_page, name="dashboard"),
    path("arsenal-ia/", arsenal_ia_page, name="arsenal_ia"),
    path("business/arsenal-ia/", arsenal_ia_page, name="business_arsenal_ia"),

    path("langue/english/", include(("EnglishPrepApp.urls", "englishprep"), namespace="englishprep")),
    path("langue/german/", include(("GermanPrepApp.urls", "germanprep"), namespace="germanprep")),

    path("profiles/", include("profiles.urls")),
    path("recruteur/", include(("recruiters.urls", "recruiters"), namespace="recruiters")),

    path("italien/", include("italian_courses.urls")),

    path("jobs/", include(("job_agent.urls", "job_agent"), namespace="job_agent")),
    path("consultation/", consultation_request, name="consultation_request"),
    path("consultation/merci/", consultation_success, name="consultation_success"),
    path("about/", about_page, name="about"),
    path("services/", services_page, name="services"),
    path("protected-media/", include("mediafiles.urls")),
    path("api/ai/", include("ai_engine.urls")),
    path("ressources/", include(("resources.urls", "resources"), namespace="resources")),
    path("", include(("outreach.urls", "outreach"), namespace="outreach")),
    path("edu/", include("edu_platform.urls", namespace="edu")),

    
    # Legacy URL aliases for backward compatibility
    path("prep-langues/", RedirectView.as_view(url="/prep/", permanent=False), name="prep_langues"),
    path("motivation-letter/", RedirectView.as_view(url="/motivation/", permanent=False), name="motivation_letter_legacy"),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
