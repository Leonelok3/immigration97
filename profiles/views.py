from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse

from billing.services import has_active_access, has_session_access, has_candidate_access, has_recruiter_access
from cv_generator.models import CV

from .models import Profile, Category, Skill, ProfileSkill, PortfolioItem
from .forms import ProfileForm, PortfolioItemForm, ContactCandidateForm, AvatarUploadForm, SkillForm

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import RecruiterFavorite, ProfileView

# ======================================================
# LISTE DES PROFILS (visible aux recruteurs)
# ======================================================
class ProfileListView(ListView):
    model = Profile
    template_name = "profiles/profile_list.html"
    context_object_name = "profiles"
    paginate_by = 12

    def get_queryset(self):
        queryset = super().get_queryset().filter(is_public=True)

        category = self.request.GET.get("category", "")
        query = self.request.GET.get("q", "")
        level = self.request.GET.get("level", "")
        sort = self.request.GET.get("sort", "-created_at")

        if category:
            queryset = queryset.filter(category__slug=category)

        if level:
            queryset = queryset.filter(level=level)

        if query:
            queryset = queryset.filter(
                Q(headline__icontains=query) |
                Q(bio__icontains=query) |
                Q(location__icontains=query) |
                Q(user__first_name__icontains=query) |
                Q(user__last_name__icontains=query)
            )

        allowed_sorts = ["-created_at", "created_at", "level", "location"]
        if sort in allowed_sorts:
            queryset = queryset.order_by(sort)

        return queryset.select_related("user", "category").prefetch_related("portfolio_items", "skills")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        context["level_choices"] = [("A1","A1"),("A2","A2"),("B1","B1"),("B2","B2"),("C1","C1"),("C2","C2")]
        fav_ids = set()
        if self.request.user.is_authenticated:
            fav_ids = set(
                RecruiterFavorite.objects.filter(recruiter=self.request.user)
                .values_list("profile_id", flat=True)
            )
        context["fav_ids"] = fav_ids
        context["total_profiles"] = Profile.objects.filter(is_public=True).count()
        return context


# ======================================================
# DETAIL D'UN PROFIL (page recruteur)
# + envoi d'invitation
# ======================================================
# profiles/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import DetailView
from django.contrib import messages

from billing.services import has_active_access
from recruiters.models import InterviewInvite
from .models import Profile
from .forms import ContactCandidateForm
from django.db import models


class ProfileDetailView(DetailView):
    model = Profile
    template_name = "profiles/profile_detail.html"
    context_object_name = "profile"
    

    def get_queryset(self):
        """
        - Recruteur/public: seulement les profils publiés
        - Propriétaire: peut voir même si non publié
        """
        qs = super().get_queryset()
        if self.request.user.is_authenticated:
            return qs.filter(models.Q(is_public=True) | models.Q(user=self.request.user))
        return qs.filter(is_public=True)

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Track profile view (only from others, not from owner)
        if request.user.is_authenticated and request.user != self.object.user:
            ProfileView.objects.create(profile=self.object, viewer=request.user)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["contact_form"] = ContactCandidateForm()
        if self.request.user.is_authenticated:
            context["is_favorited"] = RecruiterFavorite.objects.filter(
                recruiter=self.request.user, profile=self.object
            ).exists()
            context["has_access"] = True  # invitations gratuites pour tout recruteur connecté
        else:
            context["is_favorited"] = False
            context["has_access"] = False
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = ContactCandidateForm(request.POST)

        # ✅ Doit être connecté
        if not request.user.is_authenticated:
            messages.error(request, "Connectez-vous pour envoyer une invitation.")
            return redirect("authentification:login")

        if form.is_valid():
            invite = InterviewInvite.objects.create(
                recruiter=request.user,
                candidate_user=self.object.user,
                subject="Invitation à entretien",
                message=form.cleaned_data["message"],
            )
            from recruiters.emails import send_invite_received
            send_invite_received(invite)
            messages.success(request, "✅ Invitation envoyée. Le candidat pourra répondre depuis son espace.")
            return redirect("profiles:detail", pk=self.object.pk)

        context = self.get_context_data()
        context["contact_form"] = form
        return render(request, self.template_name, context)


# ======================================================
# CREATION DE PROFIL
# ======================================================
class ProfileCreateView(LoginRequiredMixin, CreateView):
    model = Profile
    form_class = ProfileForm
    template_name = "profiles/profile_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Profil créé avec succès !")
        return super().form_valid(form)


# ======================================================
# EDITION DE PROFIL
# ======================================================
class ProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Profile
    form_class = ProfileForm
    template_name = "profiles/profile_form.html"

    def test_func(self):
        return self.request.user == self.get_object().user

    def get_success_url(self):
        return reverse("profiles:edit", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile = self.object
        context["profile_skills"] = ProfileSkill.objects.filter(profile=profile).select_related("skill").order_by("-level", "skill__name")
        context["portfolio_items"] = PortfolioItem.objects.filter(profile=profile).order_by("-id")
        context["all_skills"] = list(Skill.objects.values_list("name", flat=True).order_by("name")[:200])
        context["skill_form"] = SkillForm()
        return context


# ======================================================
# AJOUT PORTFOLIO
# ======================================================
@login_required
def add_portfolio_item(request, pk):
    profile = get_object_or_404(Profile, pk=pk)

    if request.user != profile.user:
        return redirect("profiles:list")

    if request.method == "POST":
        form = PortfolioItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.profile = profile
            item.save()
            messages.success(request, "✅ Document ajouté au portfolio.")
            return redirect("profiles:detail", pk=pk)
    else:
        form = PortfolioItemForm()

    return render(
        request,
        "profiles/portfolio_form.html",
        {"form": form, "profile": profile},
    )


# ======================================================
# MON ESPACE CANDIDAT
# ======================================================
@login_required
def my_space(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    has_premium = has_candidate_access(request.user)
    has_temp_access = has_session_access(request)

    if not has_premium and profile.is_public:
        profile.is_public = False
        profile.save(update_fields=["is_public"])

    recent_cvs = CV.objects.filter(user=request.user).order_by("-created_at")[:5]
    profile_skills = ProfileSkill.objects.filter(profile=profile).select_related("skill").order_by("-level", "skill__name")
    portfolio_items = PortfolioItem.objects.filter(profile=profile).order_by("-id")
    all_skills = list(Skill.objects.values_list("name", flat=True).order_by("name")[:200])
    recommended_offers = []

    if profile.category_id:
        try:
            from job_agent.models import JobLead, PublicJobOffer

            imported_urls = JobLead.objects.filter(user=request.user).values_list("url", flat=True)
            recommended_offers = (
                PublicJobOffer.objects.filter(is_active=True, category=profile.category)
                .exclude(url__in=imported_urls)
                .select_related("category")
                .order_by("-created_at")[:6]
            )
        except Exception:
            recommended_offers = []

    # Score de complétion
    checks = {
        "Photo de profil": bool(profile.avatar),
        "Titre professionnel": bool(profile.headline),
        "À propos (bio)": bool(profile.bio),
        "Localisation": bool(profile.location),
        "LinkedIn": bool(profile.linkedin_url),
        "Compétences (≥ 3)": profile_skills.count() >= 3,
        "Portfolio (≥ 1 document)": portfolio_items.exists(),
    }
    done = sum(1 for v in checks.values() if v)
    profile_progress = int(done / len(checks) * 100)

    context = {
        "profile": profile,
        "has_premium": has_premium,
        "has_temp_access": has_temp_access,
        "recent_cvs": recent_cvs,
        "profile_skills": profile_skills,
        "portfolio_items": portfolio_items,
        "all_skills": all_skills,
        "skill_form": SkillForm(),
        "profile_checks": checks,
        "profile_progress": profile_progress,
        "test_results": [],
        "recommended_offers": recommended_offers,
    }
    return render(request, "profiles/my_space.html", context)


# ======================================================
# UPLOAD AVATAR
# ======================================================
@login_required
def upload_avatar(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = AvatarUploadForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Photo de profil mise à jour.")
            return redirect("profiles:my_space")
    else:
        form = AvatarUploadForm(instance=profile)

    return render(
        request,
        "profiles/avatar_upload.html",
        {"profile": profile, "form": form},
    )


# ======================================================
# TOGGLE VISIBILITE (PUBLIC/PRIVATE)
# ======================================================
@require_POST
@login_required
def toggle_public(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    has_premium = has_candidate_access(request.user)
    if not has_premium:
        messages.error(request, "🔒 Un abonnement Premium Candidat est requis pour publier votre profil.")
        return redirect("billing:pricing")

    profile.is_public = not profile.is_public
    profile.save(update_fields=["is_public"])

    if profile.is_public:
        messages.success(request, "✅ Profil publié : visible par les recruteurs.")
    else:
        messages.success(request, "Profil dépublié : vous n’êtes plus visible.")
    return redirect("profiles:my_space")


# ======================================================
# INVITATIONS — CANDIDAT (reçues)
# ======================================================
@login_required
def my_invitations(request):
    from recruiters.models import InterviewInvite

    profile, _ = Profile.objects.get_or_create(user=request.user)

    invites = InterviewInvite.objects.filter(
        candidate_user=request.user
    ).order_by("-created_at")

    return render(
        request,
        "profiles/my_invitations.html",
        {"invites": invites, "profile": profile},
    )


# ======================================================
# INVITATIONS — ACTIONS CANDIDAT
# ======================================================
@require_POST
@login_required
def invite_accept(request, invite_id):
    from recruiters.models import InterviewInvite

    invite = get_object_or_404(
        InterviewInvite,
        id=invite_id,
        candidate_user=request.user
    )

    if invite.status != "sent":
        messages.info(request, "Cette invitation a déjà été traitée.")
        return redirect("profiles:my_invitations")

    invite.accept()
    from recruiters.emails import send_invite_accepted
    send_invite_accepted(invite)
    messages.success(request, "✅ Invitation acceptée.")
    return redirect("profiles:my_invitations")


@require_POST
@login_required
def invite_decline(request, invite_id):
    from recruiters.models import InterviewInvite

    invite = get_object_or_404(
        InterviewInvite,
        id=invite_id,
        candidate_user=request.user
    )

    if invite.status != "sent":
        messages.info(request, "Cette invitation a déjà été traitée.")
        return redirect("profiles:my_invitations")

    invite.decline()
    from recruiters.emails import send_invite_declined
    send_invite_declined(invite)
    messages.success(request, "Invitation refusée.")
    return redirect("profiles:my_invitations")


# ======================================================
# INVITATIONS — RECRUTEUR (envoyées)
# ======================================================
@login_required
def recruiter_invites(request):
    from recruiters.models import InterviewInvite

    invites = InterviewInvite.objects.filter(
        recruiter=request.user
    ).order_by("-created_at")

    return render(
        request,
        "profiles/recruiter_invites.html",
        {"invites": invites},
    )
@login_required
def favorites_list(request):
    favorites = RecruiterFavorite.objects.filter(
        recruiter=request.user
    ).select_related("profile", "profile__user", "profile__category").order_by("-created_at")

    return render(request, "profiles/favorites_list.html", {"favorites": favorites})


@require_POST
@login_required
def toggle_favorite(request, pk):
    profile = get_object_or_404(Profile, pk=pk)

    obj, created = RecruiterFavorite.objects.get_or_create(
        recruiter=request.user,
        profile=profile
    )

    if not created:
        obj.delete()
        messages.success(request, "Retiré des favoris.")
    else:
        messages.success(request, "Ajouté aux favoris ⭐")

    # Retour à la page précédente (list ou detail)
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", reverse("profiles:list")))



def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context["categories"] = Category.objects.all()

    fav_ids = set()
    if self.request.user.is_authenticated:
        fav_ids = set(
            RecruiterFavorite.objects.filter(recruiter=self.request.user)
            .values_list("profile_id", flat=True)
        )
    context["fav_ids"] = fav_ids
    return context


# ======================================================
# DASHBOARD RECRUTEUR
# ======================================================
@login_required
def recruiter_dashboard(request):
    from recruiters.models import InterviewInvite
    from django.db.models import Q as DQ

    has_premium = has_recruiter_access(request.user)

    recent_invites = (
        InterviewInvite.objects
        .filter(recruiter=request.user)
        .select_related("candidate_user")
        .order_by("-created_at")[:5]
    )
    favorites = (
        RecruiterFavorite.objects
        .filter(recruiter=request.user)
        .select_related("profile", "profile__user")
        .order_by("-created_at")[:5]
    )
    invites_accepted = (
        InterviewInvite.objects
        .filter(status="accepted")
        .filter(DQ(recruiter=request.user) | DQ(candidate_user=request.user))
        .select_related("recruiter", "candidate_user")
        .prefetch_related("messages")
        .order_by("-responded_at")[:5]
    )
    conversations = []
    for inv in invites_accepted:
        unread = inv.messages.filter(is_read=False).exclude(sender=request.user).count()
        last_msg = inv.messages.last()
        other = inv.candidate_user if inv.recruiter == request.user else inv.recruiter
        conversations.append({"invite": inv, "other": other, "unread": unread, "last_msg": last_msg})

    total_invites = InterviewInvite.objects.filter(recruiter=request.user).count()
    accepted_invites = InterviewInvite.objects.filter(recruiter=request.user, status="accepted").count()
    total_favorites = RecruiterFavorite.objects.filter(recruiter=request.user).count()
    total_profiles = Profile.objects.filter(is_public=True).count()

    return render(request, "profiles/recruiter_dashboard.html", {
        "has_premium": has_premium,
        "recent_invites": recent_invites,
        "favorites": favorites,
        "conversations": conversations,
        "total_invites": total_invites,
        "accepted_invites": accepted_invites,
        "total_favorites": total_favorites,
        "total_profiles": total_profiles,
    })


# ======================================================
# ANALYTICS CANDIDAT
# ======================================================
@login_required
def my_analytics(request):
    from recruiters.models import InterviewInvite
    from django.db.models import Count
    from django.db.models.functions import TruncMonth

    try:
        profile = Profile.objects.get(user=request.user)
    except Profile.DoesNotExist:
        profile = None

    total_views = 0
    invites_received = 0
    invites_accepted = 0
    invites_declined = 0
    monthly_views_labels = []
    monthly_views_data = []

    if profile:
        total_views = profile.views.count()
        monthly = list(
            profile.views
            .annotate(month=TruncMonth("viewed_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")[:6]
        )
        monthly_views_labels = [m["month"].strftime("%b %Y") if m["month"] else "" for m in monthly]
        monthly_views_data = [m["count"] for m in monthly]

    invites_qs = InterviewInvite.objects.filter(candidate_user=request.user)
    invites_received = invites_qs.count()
    invites_accepted = invites_qs.filter(status="accepted").count()
    invites_declined = invites_qs.filter(status="declined").count()
    invites_pending = invites_qs.filter(status="sent").count()
    recent_invites = (
        invites_qs.select_related("recruiter", "recruiter__recruiter_profile")
        .order_by("-created_at")[:5]
    )

    # Completion score (simple)
    if profile:
        fields = [profile.headline, profile.bio, profile.location, profile.avatar, profile.linkedin_url]
        completion = int(sum(1 for f in fields if f) / len(fields) * 100)
    else:
        completion = 0

    return render(request, "profiles/my_analytics.html", {
        "profile": profile,
        "total_views": total_views,
        "monthly_views_labels": monthly_views_labels,
        "monthly_views_data": monthly_views_data,
        "invites_received": invites_received,
        "invites_accepted": invites_accepted,
        "invites_declined": invites_declined,
        "invites_pending": invites_pending,
        "recent_invites": recent_invites,
        "completion": completion,
    })


# ======================================================
# MESSAGERIE INTERNE
# ======================================================
@login_required
def conversation_list(request):
    from recruiters.models import InterviewInvite, Message
    from django.db.models import OuterRef, Subquery, Count, Q as DQ

    # Toutes les conversations acceptées où l'utilisateur est recruteur ou candidat
    invites = (
        InterviewInvite.objects
        .filter(status="accepted")
        .filter(DQ(recruiter=request.user) | DQ(candidate_user=request.user))
        .select_related("recruiter__recruiter_profile", "candidate_user__profile")
        .prefetch_related("messages")
        .order_by("-responded_at")
    )

    # Compter les messages non lus pour chaque conversation
    conversations = []
    for inv in invites:
        unread = inv.messages.filter(is_read=False).exclude(sender=request.user).count()
        last_msg = inv.messages.last()
        other = inv.candidate_user if inv.recruiter == request.user else inv.recruiter
        conversations.append({
            "invite": inv,
            "other": other,
            "unread": unread,
            "last_msg": last_msg,
        })

    return render(request, "profiles/conversation_list.html", {
        "conversations": conversations,
    })


@login_required
def conversation_thread(request, invite_id):
    from recruiters.models import InterviewInvite, Message
    from django.db.models import Q as DQ

    invite = get_object_or_404(
        InterviewInvite,
        id=invite_id,
        status="accepted",
    )

    # Seuls les deux participants peuvent accéder
    if request.user not in (invite.recruiter, invite.candidate_user):
        messages.error(request, "Accès refusé.")
        return redirect("profiles:conversation_list")

    # Marquer les messages reçus comme lus
    invite.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if body:
            Message.objects.create(invite=invite, sender=request.user, body=body)
        return redirect("profiles:conversation_thread", invite_id=invite_id)

    thread_messages = invite.messages.select_related("sender").all()
    other = invite.candidate_user if invite.recruiter == request.user else invite.recruiter

    return render(request, "profiles/conversation_thread.html", {
        "invite": invite,
        "thread_messages": thread_messages,
        "other": other,
    })


# ======================================================
# COMPÉTENCES — Ajouter / Supprimer
# ======================================================
@require_POST
@login_required
def add_skill(request, pk):
    profile = get_object_or_404(Profile, pk=pk, user=request.user)
    form = SkillForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data["skill_name"].strip()
        level = form.cleaned_data["level"]
        years = form.cleaned_data.get("years") or 0
        skill, _ = Skill.objects.get_or_create(
            name__iexact=name,
            defaults={"name": name},
        )
        ProfileSkill.objects.update_or_create(
            profile=profile, skill=skill,
            defaults={"level": level, "years": years},
        )
        messages.success(request, f"✅ Compétence « {skill.name} » ajoutée.")
    else:
        messages.error(request, "Formulaire invalide — vérifiez les champs.")
    return redirect("profiles:my_space")


@require_POST
@login_required
def delete_skill(request, ps_id):
    ps = get_object_or_404(ProfileSkill, pk=ps_id, profile__user=request.user)
    name = ps.skill.name
    ps.delete()
    messages.success(request, f"Compétence « {name} » supprimée.")
    return redirect("profiles:my_space")


# ======================================================
# PORTFOLIO — Supprimer un document
# ======================================================
@require_POST
@login_required
def delete_portfolio_item(request, item_id):
    item = get_object_or_404(PortfolioItem, pk=item_id, profile__user=request.user)
    title = item.title
    item.file.delete(save=False)
    item.delete()
    messages.success(request, f"Document « {title} » supprimé.")
    return redirect("profiles:my_space")
