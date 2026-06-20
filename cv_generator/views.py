# cv_generator/views.py
# ============================================================
# IMMIGRATION97 — CV GENERATOR (CLEAN + STABLE)
# - Wizard Step1 / Step2 / Step3
# - CRUD (single version)
# - IA endpoints (fallback safe)
# - PDF export unique (ReportLab)
# ============================================================

# ===============================
# IMPORTS PYTHON STANDARD
# ===============================
import json
import logging
import textwrap
from io import BytesIO
from datetime import datetime

# ===============================
# IMPORTS DJANGO
# ===============================
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from billing.decorators import subscription_required

# ===============================
# SERVICES INTERNES (optionnels)
# ===============================
try:
    from billing.services import has_active_access, has_session_access
except ImportError:
    has_active_access = None
    has_session_access = None

try:
    from .services.cv_parser import extract_text_from_cv
    from .services.cv_mapper import map_cv_text_to_models
except ImportError:
    extract_text_from_cv = None
    map_cv_text_to_models = None

# ===============================
# MODÈLES
# ===============================
from .models import (
    CV,
    CVTemplate,
    CVUpload,
    Experience,
    Formation,
    Skill,
    Competence,
    Langue,
    Certification,
    Volunteer,
    Project,
    Hobby,
)

# ===============================
# FORMULAIRES
# ===============================
from .forms import (
    Step1Form,
    Step3Form,  # si tu l'utilises ailleurs
    ExperienceForm,
    EducationForm,  # si tu l'utilises ailleurs
    SkillForm,      # si tu l'utilises ailleurs
    LangueForm,     # si tu l'utilises ailleurs
    CompetenceForm, # si tu l'utilises ailleurs
    CertificationForm,
    VolunteerForm,
    ProjectForm,
    HobbyForm,
    CVUploadForm,
)

# ===============================
# LOGGER
# ===============================
logger = logging.getLogger(__name__)

# ===============================
# SERVICE IA (optionnel)
# ===============================
try:
    from .services.openai_service import OpenAIService
    _ai_service = OpenAIService()
except Exception as e:
    logger.info("OpenAIService indisponible: %s", e)
    _ai_service = None


# ===============================
# HELPERS
# ===============================

def _json_body(request):
    """Parse JSON body de manière sécurisée"""
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}

def _has_field(model_instance, field_name):
    """Vérifie si un modèle possède un champ donné"""
    try:
        return any(f.name == field_name for f in model_instance._meta.fields)
    except Exception:
        return False

def _parse_date_yyyy_mm_dd(value: str):
    """Parse une date HTML input (YYYY-MM-DD) -> date() ou None"""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None

def _user_has_premium_access(user) -> bool:
    """
    Accès premium:
    - si billing.services.has_active_access existe, on l'utilise
    - sinon -> False (safe)
    """
    try:
        if has_active_access:
            return bool(has_active_access(user))
    except Exception:
        pass
    return False


# ===============================
# PAGES PRINCIPALES
# ===============================

def index(request):
    return render(request, "cv_generator/index.html")


@login_required
def cv_list(request):
    cvs = CV.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "cv_generator/cv_list.html", {"cvs": cvs})


# ===============================
# TEMPLATES CV
# ===============================

@login_required
def template_selection(request, cv_id=None):
    """Page de sélection/changement de template"""
    cv = None
    if cv_id:
        cv = get_object_or_404(CV, id=cv_id, user=request.user)

    templates_free = CVTemplate.objects.filter(
        is_active=True,
        is_premium=False
    ).order_by("order", "name")

    templates_premium = CVTemplate.objects.filter(
        is_active=True,
        is_premium=True
    ).order_by("order", "name")

    total_templates = templates_free.count() + templates_premium.count()

    logger.info("[TEMPLATE_SELECTION] gratuits=%s premium=%s total=%s",
                templates_free.count(), templates_premium.count(), total_templates)

    if total_templates == 0:
        logger.warning("[TEMPLATE_SELECTION] ⚠️ Aucun template en base (admin Django ?)")

    context = {
        "cv": cv,
        "templates_free": templates_free,
        "templates_premium": templates_premium,
        "total_templates": total_templates,
        "templates": list(templates_free) + list(templates_premium),  # compat template
    }
    return render(request, "cv_generator/template_selection.html", context)


@login_required
def choose_template(request, template_id):
    """Créer un nouveau CV avec le template choisi"""
    template = get_object_or_404(CVTemplate, id=template_id, is_active=True)

    # si premium -> vérifier accès
    if template.is_premium and not _user_has_premium_access(request.user):
        messages.error(request, "⚠️ Ce template est réservé aux abonnés Premium.")
        return redirect("cv_generator:template_selection")

    cv = CV.objects.create(
        user=request.user,
        template=template,
        nom="",
        prenom="",
        titre_poste="",
        email=getattr(request.user, "email", "") or "",
        telephone="",
        ville="",
        province="",
        linkedin="",
        current_step=1,
        is_published=False,
        is_completed=False,
        step1_completed=False,
        step2_completed=False,
        step3_completed=False,
    )

    messages.success(request, f"✅ Nouveau CV créé avec le template '{template.name}'")
    return redirect("cv_generator:create_cv", cv_id=cv.id)


@login_required
@require_POST
def change_template(request, cv_id):
    """Changer le template d'un CV existant"""
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    template_id = request.POST.get("template_id")
    if not template_id:
        messages.error(request, "❌ Template invalide")
        return redirect("cv_generator:template_selection", cv_id=cv.id)

    template = get_object_or_404(CVTemplate, id=template_id, is_active=True)

    if template.is_premium and not _user_has_premium_access(request.user):
        messages.error(request, "⚠️ Ce template est réservé aux abonnés Premium.")
        return redirect("cv_generator:template_selection", cv_id=cv.id)

    cv.template = template
    cv.save(update_fields=["template"])

    messages.success(request, f"✅ Template changé : {template.name}")
    return redirect("cv_generator:finalize_cv", cv_id=cv.id)


@login_required
@require_POST
def set_template(request):
    """API endpoint pour créer un CV avec un template (JSON)"""
    data = _json_body(request)
    template_id = data.get("template_id")

    if not template_id:
        return JsonResponse({"success": False, "error": "template_id manquant"}, status=400)

    template = get_object_or_404(CVTemplate, id=template_id, is_active=True)

    if template.is_premium and not _user_has_premium_access(request.user):
        return JsonResponse({"success": False, "error": "Template premium - accès requis"}, status=403)

    cv = CV.objects.create(
        user=request.user,
        template=template,
        nom="",
        prenom="",
        titre_poste="",
        email=getattr(request.user, "email", "") or "",
        telephone="",
        ville="",
        province="",
        linkedin="",
        current_step=1,
        is_published=False,
        is_completed=False,
        step1_completed=False,
        step2_completed=False,
        step3_completed=False,
    )

    redirect_url = redirect("cv_generator:create_cv", cv_id=cv.id).url
    return JsonResponse({"success": True, "data": {"cv_id": cv.id, "redirect_url": redirect_url}})


# ===============================
# WIZARD MULTI-ÉTAPES
# ===============================

@login_required
def create_cv(request, cv_id):
    cv = get_object_or_404(
        CV.objects.select_related("template", "user").prefetch_related(
            "experiences", "formations", "competences", "langues",
            "skills", "certifications", "volunteers", "projects", "hobbies"
        ),
        id=cv_id,
        user=request.user
    )

    current_step = cv.current_step or 1

    # ==================== STEP 1 ====================
    if current_step == 1:
        if request.method == "POST":
            form = Step1Form(request.POST, request.FILES, instance=cv)
            if form.is_valid():
                form.save()

                # Marquer step1
                if not cv.step1_completed:
                    cv.step1_completed = True
                    cv.save(update_fields=["step1_completed"])

                # Avancer step2
                if cv.current_step < 2:
                    cv.current_step = 2
                    cv.save(update_fields=["current_step"])

                messages.success(request, "✅ Étape 1 complétée !")
                return redirect("cv_generator:create_cv", cv_id=cv.id)
        else:
            form = Step1Form(instance=cv)

        return render(request, "cv_generator/steps/step_1_personal.html", {
            "cv": cv,
            "form": form,
            "current_step": 1,
        })

    # ==================== STEP 2 ====================
    if current_step == 2:
        return redirect("cv_generator:create_cv_step2", cv_id=cv.id)

    # ==================== STEP 3 ====================
    if current_step == 3:
        return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

    # Fallback
    cv.current_step = 1
    cv.save(update_fields=["current_step"])
    return redirect("cv_generator:create_cv", cv_id=cv.id)


@login_required
def create_cv_step2(request, cv_id):
    """Étape 2 : Expériences"""
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    if not cv.step1_completed:
        messages.warning(request, "⚠️ Veuillez d'abord compléter l'étape 1.")
        return redirect("cv_generator:create_cv", cv_id=cv.id)

    # Forcer step2
    if (cv.current_step or 1) != 2:
        cv.current_step = 2
        cv.save(update_fields=["current_step"])

    experience_form = ExperienceForm()

    if request.method == "POST":
        experience_form = ExperienceForm(request.POST)
        if experience_form.is_valid():
            exp = experience_form.save(commit=False)
            exp.cv = cv
            exp.save()

            if not cv.step2_completed:
                cv.step2_completed = True
                cv.save(update_fields=["step2_completed"])

            messages.success(request, "✅ Expérience ajoutée avec succès !")
            return redirect("cv_generator:create_cv_step2", cv_id=cv.id)

        messages.error(request, "❌ Erreur dans le formulaire. Vérifiez les champs.")

    # ✅ IMPORTANT : ne plus trier par date_debut (inexistant)
    experiences = cv.experiences.all().order_by("-start_date", "-id")


    return render(request, "cv_generator/steps/step_2_experience.html", {
        "cv": cv,
        "experiences": experiences,
        "experience_form": experience_form,
        "current_step": 2,
    })


@login_required
def create_cv_step3(request, cv_id):
    """Étape 3 : Formations + Compétences + Langues + Résumé"""
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    # Vérification étape 2
    if not cv.step2_completed:
        messages.warning(request, "⚠️ Complétez d'abord vos expériences professionnelles.")
        return redirect("cv_generator:create_cv_step2", cv_id=cv.id)

    # Forcer l’étape 3
    if (cv.current_step or 1) != 3:
        cv.current_step = 3
        cv.save(update_fields=["current_step"])

    # ==================== RÉSUMÉ ====================
    if request.method == "POST" and ("save_summary" in request.POST or ("summary" in request.POST and "action" not in request.POST)):
        summary = (request.POST.get("summary") or "").strip()
        if summary:
            # ✅ décision simple : on remplit summary (EN) + si CV en FR, on copie aussi en FR
            cv.summary = summary
            if (cv.language or "").lower().startswith("fr"):
                cv.resume_professionnel = summary
                cv.save(update_fields=["summary", "resume_professionnel"])
            else:
                cv.save(update_fields=["summary"])

            messages.success(request, "✅ Résumé professionnel sauvegardé !")
            return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

        messages.error(request, "❌ Le résumé ne peut pas être vide.")

    # ==================== ACTIONS ====================
    if request.method == "POST" and "action" in request.POST:
        action = (request.POST.get("action") or "").strip()

        # ----- AJOUT FORMATION -----
        if action == "add_formation":
            diplome = (request.POST.get("diplome") or "").strip()
            etablissement = (request.POST.get("etablissement") or "").strip()
            start_date = _parse_date_yyyy_mm_dd(request.POST.get("start_date"))
            end_date = _parse_date_yyyy_mm_dd(request.POST.get("end_date"))

            if diplome and etablissement:
                formation = Formation.objects.create(
                    cv=cv,
                    diplome=diplome,
                    etablissement=etablissement,
                    # Compat EN (utile si certains templates lisent ces champs)
                    diploma=diplome,
                    institution=etablissement,
                    start_date=start_date,
                    end_date=end_date,
                )

                if end_date:
                    formation.annee_obtention = str(end_date.year)
                    formation.save(update_fields=["annee_obtention"])

                messages.success(request, "✅ Formation ajoutée avec succès !")
                return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

            messages.error(request, "❌ Le diplôme et l'établissement sont obligatoires.")

        # ----- AJOUT COMPÉTENCE -----
        elif action == "add_competence":
            competence_nom = (request.POST.get("competence") or "").strip()
            if competence_nom:
                Competence.objects.create(cv=cv, nom=competence_nom)
                messages.success(request, "✅ Compétence ajoutée !")
                return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

            messages.error(request, "❌ Le nom de la compétence est obligatoire.")

        # ----- AJOUT LANGUE -----
        elif action == "add_langue":
            langue = (request.POST.get("langue") or "").strip()
            niveau = (request.POST.get("niveau") or "").strip()

            if langue and niveau:
                # ✅ IMPORTANT : on écrit uniquement dans les champs qui existent sûrement en base
                # (d'après tes erreurs : Langue = name/level)
                Langue.objects.create(
                    cv=cv,
                    name=langue,
                    level=niveau,
                )
                messages.success(request, "✅ Langue ajoutée !")
                return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

            messages.error(request, "❌ La langue et le niveau sont obligatoires.")

        # ----- TERMINER CV -----
        elif action == "complete_cv":
            cv.is_completed = True
            cv.step3_completed = True
            cv.current_step = 3
            cv.save(update_fields=["is_completed", "step3_completed", "current_step"])
            messages.success(request, "✅ CV marqué comme terminé !")
            return redirect("cv_generator:finalize_cv", cv_id=cv.id)

    # ==================== CONTEXT ====================
    context = {
        "cv": cv,
        "formations": Formation.objects.filter(cv=cv).order_by("-start_date", "-end_date", "-annee_obtention"),
        "competences": Competence.objects.filter(cv=cv).order_by("nom"),
        # ✅ IMPORTANT : ne plus trier/afficher sur langue/niveau si ces champs n’existent pas en base
        "langues": Langue.objects.filter(cv=cv).order_by("name", "level"),
        # ✅ IMPORTANT : ne plus trier par date_debut (inexistant)
        "experiences": cv.experiences.all().order_by("-start_date", "-created_at"),
        "current_step": 3,
    }
    return render(request, "cv_generator/steps/step_3_skills.html", context)



@login_required
def delete_experience(request, cv_id, exp_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    exp = get_object_or_404(Experience, id=exp_id, cv=cv)
    exp.delete()

    messages.success(request, "✅ Expérience supprimée.")

    # si plus d'expérience, step2 redevient incomplet
    if cv.experiences.count() == 0 and cv.step2_completed:
        cv.step2_completed = False
        cv.current_step = 2
        cv.save(update_fields=["step2_completed", "current_step"])

    return redirect("cv_generator:create_cv_step2", cv_id=cv.id)


@login_required
def delete_formation(request, cv_id, formation_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    formation = get_object_or_404(Formation, id=formation_id, cv=cv)
    formation.delete()
    messages.success(request, "✅ Formation supprimée.")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


@login_required
def delete_competence(request, cv_id, competence_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    competence = get_object_or_404(Competence, id=competence_id, cv=cv)
    competence.delete()
    messages.success(request, "✅ Compétence supprimée.")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


@login_required
def delete_langue(request, cv_id, langue_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    langue = get_object_or_404(Langue, id=langue_id, cv=cv)
    langue.delete()
    messages.success(request, "✅ Langue supprimée.")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


@login_required
def delete_language(request, cv_id, lang_id):
    """Alias compatible avec les routes/templates qui utilisent delete_language."""
    return delete_langue(request, cv_id, lang_id)


@login_required
def delete_certification(request, cv_id, cert_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    cert = get_object_or_404(Certification, id=cert_id, cv=cv)
    cert.delete()
    messages.success(request, "✅ Certification supprimée.")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


@login_required
def delete_volunteer(request, cv_id, vol_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    vol = get_object_or_404(Volunteer, id=vol_id, cv=cv)
    vol.delete()
    messages.success(request, "✅ Expérience bénévole supprimée.")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


@login_required
def delete_project(request, cv_id, proj_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    proj = get_object_or_404(Project, id=proj_id, cv=cv)
    proj.delete()
    messages.success(request, "✅ Projet supprimé.")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


@login_required
def delete_hobby(request, cv_id, hobby_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    hobby = get_object_or_404(Hobby, id=hobby_id, cv=cv)
    hobby.delete()
    messages.success(request, "✅ Centre d'intérêt supprimé.")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


# ===============================
# FINALISATION (APERÇU)
# ===============================
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import CV, Formation, Competence, Langue

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

@login_required
def finalize_cv(request, cv_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    # ✅ Garde-fous étapes
    if not cv.step1_completed:
        messages.warning(request, "⚠️ Complète d’abord l’étape 1.")
        return redirect("cv_generator:create_cv", cv_id=cv.id)

    if not cv.step2_completed:
        messages.warning(request, "⚠️ Complète d’abord l’étape 2 (expériences).")
        return redirect("cv_generator:create_cv_step2", cv_id=cv.id)

    # ✅ Expériences (tri simple + stable)
    experiences = cv.experiences.all().order_by("-start_date", "-id")

    # ✅ Formations (tri robuste même si end_date/start_date = NULL)
    # On trie d'abord par end_date (ou start_date si end_date vide), puis start_date, puis id
    formations = (
        Formation.objects.filter(cv=cv)
        .annotate(sort_date=Coalesce("end_date", "start_date"))
        .order_by(F("sort_date").desc(nulls_last=True), F("start_date").desc(nulls_last=True), "-id")
    )

    # ✅ Compétences : champ = nom
    competences = Competence.objects.filter(cv=cv).order_by("nom", "id")

    # ✅ Langues : SEULEMENT name / level
    langues = Langue.objects.filter(cv=cv).order_by("name", "level", "id")

    context = {
        "cv": cv,
        "experiences": experiences,
        "formations": formations,
        "competences": competences,
        "langues": langues,
    }

    return render(request, "cv_generator/steps/step_3_final.html", context)




# ===============================
# UPLOAD + PARSING CV (OPTIONNEL)
# ===============================

@login_required
def upload_cv(request, cv_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    try:
        upload = cv.upload
    except CVUpload.DoesNotExist:
        upload = None

    if request.method == "POST":
        form = CVUploadForm(request.POST, request.FILES, instance=upload)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.cv = cv
            upload.status = "uploaded"
            upload.save()

            try:
                if extract_text_from_cv and upload.file:
                    text = extract_text_from_cv(upload.file.path)
                    upload.extracted_text = text
                    upload.status = "parsed"
                    upload.save(update_fields=["extracted_text", "status"])

                    if map_cv_text_to_models:
                        map_cv_text_to_models(cv, text)

                    if cv.experiences.exists():
                        cv.step2_completed = True
                        cv.current_step = max(cv.current_step or 1, 3)
                        cv.save(update_fields=["step2_completed", "current_step"])

                    messages.success(request, "✅ CV importé et analysé avec succès !")
                else:
                    messages.warning(request, "⚠️ Service d'extraction non disponible.")
            except Exception as e:
                logger.error("Erreur parsing CV: %s", e)
                upload.status = "error"
                upload.save(update_fields=["status"])
                messages.error(request, f"❌ Erreur lors de l'analyse du CV: {str(e)}")

            return redirect("cv_generator:create_cv_step2", cv_id=cv.id)
    else:
        form = CVUploadForm(instance=upload)

    return render(request, "cv_generator/upload_cv.html", {"cv": cv, "form": form, "upload": upload})


# ===============================
# IA ENDPOINTS (SAFE)
# ===============================

@login_required
@require_POST
def generate_ai_summary(request, cv_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    job_title = cv.profession or cv.titre_poste or "Professionnel"
    country = cv.pays_cible or "International"
    industry = cv.template.name if cv.template else "Général"

    if _ai_service:
        try:
            items = _ai_service.generate_career_summaries(job_title, 0, industry, country)
            return JsonResponse({"success": True, "data": items})
        except Exception as e:
            logger.warning("IA generate_ai_summary erreur: %s", e)

    demos = [
        f"{job_title} orienté résultats avec une solide expérience en {industry}.",
        f"Professionnel {job_title} dynamique, spécialisé en {industry}, prêt pour {country}.",
        f"Expert {job_title} avec un parcours prouvé en gestion de projets complexes.",
    ]
    return JsonResponse({"success": True, "data": demos})


@login_required
@require_POST
def analyze_cv(request, cv_id=None):
    if cv_id:
        cv = get_object_or_404(CV, id=cv_id, user=request.user)
        cv_data = {
            "profession": cv.profession,
            "pays_cible": cv.pays_cible,
            "summary": cv.summary or cv.resume_professionnel,
        }
        industry = cv.template.name if cv.template else "Général"
        country = cv.pays_cible or "International"
    else:
        body = _json_body(request)
        cv_data = body.get("cv_data", {})
        industry = body.get("industry", "Général")
        country = body.get("country", "International")

    if _ai_service:
        try:
            res = _ai_service.analyze_cv_quality(cv_data, industry, country)
            return JsonResponse({"success": True, "data": res})
        except Exception as e:
            logger.warning("IA analyze_cv erreur: %s", e)

    return JsonResponse({"success": True, "data": {
        "ats_score": 65,
        "breakdown": {
            "ats_compatibility": 20,
            "action_verbs": 15,
            "quantification": 15,
            "grammar": 15
        },
        "recommendations": [
            "Ajoutez plus de métriques chiffrées",
            "Commencez chaque bullet par un verbe d'action",
            "Incorporez des mots-clés du secteur"
        ]
    }})


@login_required
@require_http_methods(["GET"])
def ats_score(request, cv_id):
    """Score ATS simple + feedback"""
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    score = 0
    feedback = []

    # résumé (25)
    if cv.summary and len(cv.summary.strip()) >= 30:
        score += 25
        if len(cv.summary.strip()) < 100:
            feedback.append("✅ Résumé présent. Ajoutez des mots-clés métier et quantifiez vos réalisations.")
    else:
        feedback.append("📝 Ajoutez un résumé professionnel (2-3 lignes)")

    # expériences (30)
    exp_count = cv.experiences.count()
    if exp_count >= 2:
        score += 30
    elif exp_count == 1:
        score += 15
        feedback.append("👔 Ajoutez une deuxième expérience (stage, bénévolat possible)")
    else:
        feedback.append("👔 Ajoutez au moins une expérience")

    # compétences (20)
    comp_count = cv.competences.count()
    if comp_count >= 5:
        score += 20
    elif comp_count >= 3:
        score += 10
        feedback.append("🔧 Ajoutez 2-3 compétences techniques supplémentaires")
    else:
        feedback.append("🔧 Ajoutez au moins 5 compétences clés")

    # formations (15)
    if cv.formations.count() >= 1:
        score += 15
    else:
        feedback.append("🎓 Ajoutez votre formation principale")

    # langues (10)
    lang_count = cv.langues.count()
    if lang_count >= 2:
        score += 10
    elif lang_count == 1:
        score += 5
        feedback.append("🌍 Ajoutez une deuxième langue (anglais conseillé)")
    else:
        feedback.append("🌍 Ajoutez vos langues")

    final_score = min(score, 100)

    if final_score >= 80:
        feedback.insert(0, "🎉 Excellent ! Votre CV est bien optimisé pour les ATS.")
    elif final_score >= 60:
        feedback.insert(0, "👍 Bon départ ! Quelques améliorations possibles.")
    else:
        feedback.insert(0, "📈 Des améliorations sont nécessaires pour maximiser vos chances.")

    return JsonResponse({"success": True, "score": final_score, "feedback": feedback})


# ===============================
# PDF EXPORT UNIQUE (REPORTLAB)
# ===============================
# cv_generator/views.py
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.staticfiles import finders

from .models import CV, Formation, Competence, Langue  # adapte si besoin
@subscription_required
@login_required
def export_pdf(request, cv_id):
    """
    Export PDF PRO via HTML -> PDF (WeasyPrint)
    - Respecte le rendu CSS du template Canada ATS
    - 1 seule URL, 1 seule fonction
    """

    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    experiences = cv.experiences.all().order_by("-start_date", "-id")
    formations = Formation.objects.filter(cv=cv).order_by("-end_date", "-start_date", "-id")
    competences = Competence.objects.filter(cv=cv).order_by("nom", "id")
    langues = Langue.objects.filter(cv=cv).order_by("name", "level", "id")

    context = {
        "cv": cv,
        "experiences": experiences,
        "formations": formations,
        "competences": competences,
        "langues": langues,
        "generated_at": timezone.now(),
    }

    template_name = "cv_generator/templates_pdf/cv_template_pdf.html"

    html_string = render_to_string(template_name, context=context, request=request)

    # CSS PDF dédié — sélection dynamique selon le template choisi
    _style = (cv.template.style if cv.template else "") or "canada_ats"
    _css_map = {
        "europe": "css/cv_pdf_europe.css",
        "modern": "css/cv_pdf_modern.css",
        "professional": "css/cv_pdf_professional.css",
        "pro": "css/cv_pdf_professional.css",
    }
    _css_key = next((k for k in _css_map if k in _style.lower()), None)
    _css_static = _css_map.get(_css_key, "css/cv_pdf_canada_ats.css")
    css_file = finders.find(_css_static)

    # WeasyPrint
    try:
        from weasyprint import HTML, CSS
    except Exception as e:
        return HttpResponse(
            "WeasyPrint n'est pas installé. Installe-le pour un rendu PDF fidèle au CSS.\n"
            "Commande: pip install weasyprint",
            content_type="text/plain",
            status=500,
        )

    base_url = request.build_absolute_uri("/")  # important pour résoudre les assets si besoin

    stylesheets = []
    if css_file:
        stylesheets.append(CSS(filename=css_file))

    pdf_bytes = HTML(string=html_string, base_url=base_url).write_pdf(stylesheets=stylesheets)

    filename = f"CV_{(cv.prenom or '').strip()}_{(cv.nom or '').strip()}.pdf".replace(" ", "_")
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response



#########################################################

@login_required
def update_summary(request, cv_id):
    """
    Sauvegarde du résumé (compatible avec tes templates qui postent vers update_summary).
    - Accepte summary (EN) et/ou resume_professionnel (FR)
    - Redirige vers l'étape 3
    """
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    if request.method != "POST":
        return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

    summary = (request.POST.get("summary") or "").strip()
    resume_fr = (request.POST.get("resume_professionnel") or "").strip()

    updated_fields = []

    # si ton template envoie "summary" (ton step3.html le fait)
    if summary:
        cv.summary = summary
        updated_fields.append("summary")

    # si un autre template envoie resume_professionnel
    if resume_fr:
        cv.resume_professionnel = resume_fr
        updated_fields.append("resume_professionnel")

    if not updated_fields:
        messages.error(request, "❌ Le résumé ne peut pas être vide.")
        return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

    cv.save(update_fields=updated_fields)
    messages.success(request, "✅ Résumé sauvegardé avec succès !")
    return redirect("cv_generator:create_cv_step3", cv_id=cv.id)


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect

from .models import CV


@login_required
def complete_cv(request, cv_id):
    """
    Marque le CV comme complété (compatibilité route /complete/).
    Redirige vers la page finalize.
    """
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    # on accepte POST (recommandé), mais on tolère GET pour éviter blocages
    if request.method not in ("POST", "GET"):
        return redirect("cv_generator:create_cv_step3", cv_id=cv.id)

    cv.is_completed = True
    cv.step3_completed = True
    cv.current_step = max(cv.current_step, 3)
    cv.save(update_fields=["is_completed", "step3_completed", "current_step"])

    messages.success(request, "✅ CV marqué comme terminé !")
    return redirect("cv_generator:finalize_cv", cv_id=cv.id)


import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .models import CV


@login_required
@require_POST
def generate_summary(request, cv_id):
    """
    Retourne un résumé IA (JSON). Version SAFE: fallback si IA pas branchée.
    """
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    # ✅ si tu veux brancher OpenAI après, tu remplaceras ce bloc
    # Pour l’instant on génère un résumé basique basé sur les champs.
    job = (cv.titre_poste or cv.profession or "").strip()
    city = (cv.ville or "").strip()
    target = (cv.pays_cible or "").strip()

    summary = f"{job} basé à {city}. Profil orienté résultats, avec compétences clés adaptées au poste. Objectif : décrocher un poste en {target}.".strip()
    summary = summary.replace("  ", " ")

    return JsonResponse({"summary": summary})

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .models import CV


@login_required
@require_POST
def translate_summary(request, cv_id):
    """
    Traduit le résumé (JSON).
    Version SAFE: traduction simple FR<->EN sans API externe.
    Tu pourras remplacer par DeepL/OpenAI plus tard.
    """
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    text = (cv.summary or "").strip() or (cv.resume_professionnel or "").strip()
    if not text:
        return JsonResponse({"error": "Aucun résumé à traduire."}, status=400)

    # --- Heuristique simple pour deviner la langue ---
    # Si beaucoup de mots FR courants -> on traduit vers EN (fallback)
    fr_markers = ["je ", "avec", "et", "pour", "dans", "expérience", "compétence", "poste", "recherche"]
    is_probably_fr = any(m in text.lower() for m in fr_markers)

    # --- Traduction placeholder (sans API) ---
    # Objectif: ne pas casser ton flow front, renvoyer un JSON.
    if is_probably_fr:
        translated = (
            "Professional profile: " + text
        )
    else:
        translated = (
            "Profil professionnel : " + text
        )

    return JsonResponse({"translated": translated})


import json
import re
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from .models import CV, Experience


def _bulletize(text: str) -> list[str]:
    """
    Transforme un texte libre en liste de bullets propres.
    """
    if not text:
        return []

    # split sur lignes ou tirets
    parts = re.split(r"(?:\r?\n)+|(?:^\s*-\s+)|(?:\s+-\s+)", text.strip(), flags=re.MULTILINE)
    bullets = []
    for p in parts:
        p = p.strip(" \t\r\n•-*")
        if p:
            bullets.append(p)

    # dédoublonnage simple
    seen = set()
    cleaned = []
    for b in bullets:
        key = b.lower()
        if key not in seen:
            seen.add(key)
            cleaned.append(b)

    return cleaned[:8]  # max 8 bullets


@login_required
@require_POST
def generate_experience_tasks(request, cv_id, experience_id):
    """
    Génère des tâches (bullets) pour une expérience.
    Retour JSON: {"tasks": [...]}.
    """
    cv = get_object_or_404(CV, id=cv_id, user=request.user)
    exp = get_object_or_404(Experience, id=experience_id, cv=cv)

    # Base texte à enrichir
    base = (exp.description_raw or exp.description or "").strip()

    # Si vide, on construit une base minimale à partir du poste/entreprise
    title = (exp.poste or exp.title or "").strip()
    company = (exp.entreprise or exp.company or "").strip()

    if not base:
        base = f"{title} - {company}".strip(" -")

    if not base:
        return JsonResponse({"error": "Ajoute d'abord une description ou un poste/entreprise."}, status=400)

    # ✅ VERSION SANS API (fallback) — bullets standards ATS
    # Tu pourras remplacer par OpenAI après (même signature JSON).
    generic = [
        f"Assuré les responsabilités clés du poste de {title or 'ce rôle'} avec rigueur et autonomie.",
        "Collaboré avec l’équipe pour atteindre les objectifs et améliorer les processus.",
        "Analysé les besoins, proposé des solutions et suivi la mise en œuvre.",
        "Rédigé / documenté les actions et assuré un reporting régulier.",
        "Optimisé la qualité et réduit les erreurs grâce à des contrôles et standards.",
    ]

    # Si l'utilisateur a déjà écrit des bullets, on les garde prioritairement
    user_bullets = _bulletize(base)

    tasks = user_bullets if len(user_bullets) >= 3 else (user_bullets + generic)[:6]

    # Stockage
    exp.description_ai = "\n".join([f"- {t}" for t in tasks])
    exp.save(update_fields=["description_ai"])

    return JsonResponse({
        "tasks": tasks,
        "description_ai": exp.description_ai,
        "experience_id": exp.id
    })


from .forms import CVForm


@login_required
def edit_cv(request, cv_id):
    cv = get_object_or_404(CV, id=cv_id, user=request.user)

    if request.method == "POST":
        form = CVForm(request.POST, request.FILES, instance=cv)
        if form.is_valid():
            form.save()
            messages.success(request, "CV mis à jour avec succès.")
            return redirect("cv_generator:edit_cv", cv_id=cv.id)
        messages.error(request, "Corrige les champs en erreur.")
    else:
        form = CVForm(instance=cv)

    return render(request, "cv_generator/edit_cv.html", {"cv": cv, "form": form})
