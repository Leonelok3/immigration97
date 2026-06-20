from django.db import IntegrityError
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse, resolve
from django.views.decorators.http import require_POST
import logging


logger = logging.getLogger(__name__)


# ============================================================
# Utilitaires
# ============================================================

def _safe_next_url(request, fallback_name="home"):
    """
    Retourne l'URL de redirection post-login:
      1) ?next= si présent et interne
      2) sinon page HOME
    """
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt:
        try:
            resolve(nxt)
            return nxt
        except Exception:
            pass
    return reverse(fallback_name)
######################### sen activation mal

def send_activation_email(request, user):
    """
    Envoi de l'email d'activation de compte.
    """
    from django.utils import timezone

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    activate_url = request.build_absolute_uri(
        reverse(
            "authentification:activate_account",
            kwargs={"uidb64": uid, "token": token},
        )
    )

    subject = "Confirmez votre adresse email – Immigration97"
    message = render_to_string(
        "account/email/email_confirmation_message.html",
        {
            "user": user,
            "activate_url": activate_url,
            "now": timezone.now(),
        },
        request=request,
    )

    email = EmailMessage(subject, message, to=[user.email])
    email.content_subtype = "html"
    email.send()

#######################

def _try_send_activation_email(request, user):
    try:
        send_activation_email(request, user)
    except Exception:
        logger.exception("Impossible d'envoyer l'email d'activation pour user_id=%s", user.pk)
        messages.warning(
            request,
            "Votre compte a été créé, mais l'email d'activation n'a pas pu être envoyé. "
            "Contactez le support si vous ne recevez rien.",
        )
        return False
    return True


# ============================================================
# Vues
# ============================================================

def register(request):
    """
    Inscription + choix du rôle (candidat / recruteur) + email d’activation.
    """
    role_prefill = request.GET.get("role", "candidate")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        role = request.POST.get("role", "candidate")
        if role not in ("candidate", "recruiter"):
            role = "candidate"

        prefill = {"username": username, "email": email, "role": role}

        if password != confirm_password:
            messages.error(request, "❌ Les mots de passe ne correspondent pas.")
            return render(request, "authentification/register.html", {"prefill": prefill})

        if User.objects.filter(username=username).exists():
            messages.error(request, "❌ Ce nom d’utilisateur est déjà utilisé.")
            return render(request, "authentification/register.html", {"prefill": prefill})

        if User.objects.filter(email=email).exists():
            messages.error(request, "❌ Cet email est déjà utilisé.")
            return render(request, "authentification/register.html", {"prefill": prefill})

        try:
            user = User.objects.create_user(
                username=username, email=email, password=password
            )
            user.is_active = False
            user.save()

            # Sauvegarder le rôle dans UserProfile (créé automatiquement via signal)
            try:
                profile = user.userprofile
                profile.role = role
                profile.save(update_fields=["role"])
            except Exception:
                pass

            if _try_send_activation_email(request, user):
                messages.success(request, "📩 Un email de confirmation vous a été envoyé.")
            return redirect("authentification:email_sent")

        except IntegrityError:
            messages.error(request, "❌ Ce nom d’utilisateur ou cet email existe déjà.")

    return render(request, "authentification/register.html", {
        "prefill": {"role": role_prefill},
    })


def activate_account(request, uidb64, token):
    """
    Activation du compte via email.
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(
            request,
            "✅ Votre compte a été activé avec succès. Vous pouvez vous connecter.",
        )
        return redirect("authentification:login")

    return HttpResponse("❌ Lien invalide ou expiré.")


def home(request):
    """
    Page d’accueil du module d’authentification.
    """
    return render(request, "home.html")


# ============================================================
# LOGIN (USERNAME OU EMAIL + REDIRECTION PRO)
# ============================================================

def login(request):
    if request.method == "POST":
        identifier = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = None

        # Connexion avec EMAIL
        if "@" in identifier:
            try:
                user_obj = User.objects.get(email__iexact=identifier)
                user = authenticate(
                    request,
                    username=user_obj.username,
                    password=password,
                )
            except User.DoesNotExist:
                user = None
        else:
            # Connexion avec USERNAME
            user = authenticate(
                request,
                username=identifier,
                password=password,
            )

        if user is not None:
            if not user.is_active:
                messages.warning(
                    request,
                    "⚠️ Votre compte n’est pas encore activé. Vérifiez votre email.",
                )
            else:
                auth_login(request, user)
                return redirect(_safe_next_url(request))

        else:
            messages.error(
                request,
                "Identifiant ou mot de passe incorrect.",
            )

    return render(request, "authentification/login.html")


# ============================================================
# LOGOUT
# ============================================================

def logout(request):
    auth_logout(request)
    messages.success(request, "Déconnexion réussie 👋")
    return redirect("home")


# ============================================================
# EMAILS
# ============================================================

def email_sent(request):
    return render(request, "authentification/email_sent.html")


@require_POST
def resend_activation_email(request):
    email = request.POST.get("email", "").strip().lower()

    try:
        user = User.objects.get(email=email)
        if not user.is_active:
            if _try_send_activation_email(request, user):
                messages.success(
                    request, "📩 Un nouvel email de confirmation vous a été envoyé."
                )
        else:
            messages.info(request, "✅ Ce compte est déjà activé.")
    except User.DoesNotExist:
        messages.error(request, "❌ Aucun compte associé à cet email.")

    return redirect("authentification:login")


def resend_activation(request):
    if request.method == "POST":
        return resend_activation_email(request)

    return render(request, "authentification/resend_activation.html")
