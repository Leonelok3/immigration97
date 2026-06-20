from django.core.paginator import Paginator
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.contrib import messages
from django.shortcuts import redirect
from .forms import NewsletterForm
from .models import NewsletterSubscriber

from .filters import NewsItemFilter
from .models import NewsItem


from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import F
from django.shortcuts import render
from django.utils import timezone

from .filters import NewsItemFilter
from .models import NewsItem


def news_list(request):
    base_qs = NewsItem.objects.filter(is_published=True)

    # ✅ Filtrage (pays/catégorie/recherche) via django-filter
    f = NewsItemFilter(request.GET, queryset=base_qs)
    qs = f.qs.prefetch_related("tags").order_by("-publish_date")

    # ✅ À la une (featured)
    featured = (
        base_qs.filter(is_featured=True)
        .order_by("-publish_date")[:4]
    )

    # ✅ Top articles de la semaine (automatique)
    week_ago = timezone.now() - timedelta(days=7)
    top_week = (
        base_qs.filter(publish_date__gte=week_ago)
        .order_by("-views_count", "-publish_date")[:8]
    )

    # ✅ Pagination
    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    # ✅ SEO GEO dynamique (titre)
    country = request.GET.get("country")
    category = request.GET.get("category")
    q = request.GET.get("q")

    seo_title_parts = ["Actualités Immigration"]
    if country:
        seo_title_parts.append(country.upper())
    if category:
        seo_title_parts.append(category)
    if q:
        seo_title_parts.append(q)

    seo_title = " — ".join(seo_title_parts)

    return render(
        request,
        "actualite/news_list.html",
        {
            "filter": f,
            "featured": featured,
            "top_week": top_week,   # ✅ IMPORTANT : à afficher dans template
            "page_obj": page_obj,
            "seo_title": seo_title,
        },
    )



def news_detail(request, slug):
    """
    Page détail /actualite/<slug>/
    - increment views_count (safe)
    - suggestions (related + by_tags)
    """
    article = get_object_or_404(
        NewsItem.objects.prefetch_related("tags"),
        slug=slug,
        is_published=True,
    )

    # ✅ Increment views (safe & concurrent-proof)
    NewsItem.objects.filter(pk=article.pk).update(views_count=F("views_count") + 1)
    article.refresh_from_db(fields=["views_count"])

    # Articles similaires : même pays
    related = (
        NewsItem.objects.filter(
            is_published=True,
            country_target=article.country_target,
        )
        .exclude(pk=article.pk)
        .prefetch_related("tags")
        .order_by("-publish_date")[:6]
    )

    # Liés par tags
    tag_slugs = list(article.tags.values_list("slug", flat=True))
    by_tags = []
    if tag_slugs:
        by_tags = (
            NewsItem.objects.filter(is_published=True, tags__slug__in=tag_slugs)
            .exclude(pk=article.pk)
            .distinct()
            .prefetch_related("tags")
            .order_by("-publish_date")[:6]
        )

    return render(
        request,
        "actualite/news_detail.html",
        {
            "article": article,
            "related": related,
            "by_tags": by_tags,
        },
    )


def news_by_country(request, country_slug):
    """
    Page pays /actualite/pays/<country_slug>/
    - SEO title + description
    - pagination
    - top_items (views)
    - recent_items (publish_date)
    - FAQ schema helper
    """
    COUNTRY_MAP = {
        "usa": ("US", "USA"),
        "canada": ("CA", "Canada"),
        "allemagne": ("DE", "Allemagne"),
        "europe": ("EU", "Europe"),
        "italie": ("IT", "Italie"),
        "france": ("FR", "France"),
    }

    if country_slug not in COUNTRY_MAP:
        raise Http404("Pays non supporté")

    country_code, country_label = COUNTRY_MAP[country_slug]

    qs = (
        NewsItem.objects.filter(is_published=True, country_target=country_code)
        .prefetch_related("tags")
        .order_by("-publish_date")
    )

    # ✅ Sidebar “Top” + “Récents”
    top_items = (
        NewsItem.objects.filter(is_published=True, country_target=country_code)
        .order_by("-views_count", "-publish_date")[:5]
    )

    recent_items = (
        NewsItem.objects.filter(is_published=True, country_target=country_code)
        .order_by("-publish_date")[:6]
    )

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    seo_title = f"Actualités Immigration {country_label} – Opportunités, visas et lois"
    seo_description = (
        f"Découvrez les dernières actualités immigration {country_label} : "
        "visas, travail, études, résidence permanente et opportunités officielles."
    )

    # ✅ FAQ (pour FAQ Schema + UX)
    faq = {
        "USA": [
            (
                "Quels sont les visas les plus demandés ?",
                "Travail, études, regroupement familial et diversité (DV Lottery) selon les profils.",
            ),
            (
                "Où vérifier une information officielle ?",
                "Sur les sites du gouvernement et des ambassades. Évitez les annonces non officielles.",
            ),
            (
                "Combien de temps prennent les démarches ?",
                "Cela dépend du programme et du consulat. Préparez un dossier complet pour éviter les retards.",
            ),
        ],
        "Canada": [
            (
                "Quels programmes dominent au Canada ?",
                "Entrée Express, PNP, études puis permis de travail, et regroupement familial.",
            ),
            (
                "Le Canada recrute-t-il des travailleurs ?",
                "Oui, certains secteurs et provinces ont des pénuries. Les opportunités varient selon l’année.",
            ),
            (
                "Quel est le point clé pour réussir ?",
                "Dossier cohérent : études/expérience, langue, fonds, documents et historique clair.",
            ),
        ],
        "Allemagne": [
            (
                "Quels profils recrutent en Allemagne ?",
                "Profils techniques, santé, industrie, IT, métiers en tension selon les régions.",
            ),
            ("Faut-il parler allemand ?", "Souvent oui, mais certains jobs acceptent l’anglais. La langue augmente fortement vos chances."),
            (
                "Le dossier le plus important ?",
                "Contrat/offre, diplômes reconnus, preuve de ressources, assurance et documents traduits.",
            ),
        ],
        "Italie": [
            (
                "Quels visas existent pour l’Italie ?",
                "Études, travail selon quotas, regroupement familial et mobilité UE selon statut.",
            ),
            (
                "Les quotas travail sont-ils importants ?",
                "Oui, l’accès dépend souvent du calendrier officiel et des secteurs.",
            ),
            (
                "Quel conseil clé ?",
                "Suivre les annonces officielles et préparer les documents à l’avance (traductions légales).",
            ),
        ],
        "France": [
            (
                "Quels titres de séjour sont fréquents ?",
                "Étudiant, salarié, regroupement familial, et statuts spécifiques selon situation.",
            ),
            (
                "Doit-on passer par Campus France ?",
                "Souvent oui pour études, selon le pays et l’établissement.",
            ),
            (
                "Comment éviter un refus ?",
                "Dossier solide : ressources, projet clair, documents cohérents, preuves vérifiables.",
            ),
        ],
    }.get(country_label, [])

    return render(
        request,
        "actualite/news_country.html",
        {
            "country_slug": country_slug,
            "country_label": country_label,
            "page_obj": page_obj,
            "seo_title": seo_title,
            "seo_description": seo_description,
            "faq": faq,
            "top_items": top_items,
            "recent_items": recent_items,
        },
    )
def newsletter_subscribe(request):
    if request.method != "POST":
        return redirect("actualite:list")

    form = NewsletterForm(request.POST)
    if not form.is_valid():
        messages.error(request, "❌ Email invalide. Réessaie avec une adresse correcte.")
        return redirect(request.META.get("HTTP_REFERER", "actualite:list"))

    email = form.cleaned_data["email"].lower().strip()
    country_interest = (form.cleaned_data.get("country_interest") or "").strip()
    source_page = (form.cleaned_data.get("source_page") or "").strip()

    obj, created = NewsletterSubscriber.objects.get_or_create(
        email=email,
        defaults={
            "country_interest": country_interest,
            "source_page": source_page,
            "is_active": True,
        },
    )

    # Si déjà existant : on réactive et on met à jour si besoin
    if not created:
        updates = []
        if not obj.is_active:
            obj.is_active = True
            updates.append("is_active")
        if country_interest and obj.country_interest != country_interest:
            obj.country_interest = country_interest
            updates.append("country_interest")
        if source_page and obj.source_page != source_page:
            obj.source_page = source_page
            updates.append("source_page")
        if updates:
            obj.save(update_fields=updates)

    messages.success(request, "✅ Inscription réussie. Tu recevras nos alertes importantes.")
    return redirect(request.META.get("HTTP_REFERER", "actualite:list"))
