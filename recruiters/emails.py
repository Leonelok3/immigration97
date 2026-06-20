"""
Email notifications for recruiter <-> candidate interactions.
"""
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)

FROM = getattr(settings, "DEFAULT_FROM_EMAIL", "Immigration97 <contact@immigration97.com>")


def send_invite_received(invite):
    """Email envoyé au candidat quand un recruteur lui envoie une invitation."""
    candidate = invite.candidate_user
    recruiter = invite.recruiter
    company = getattr(recruiter, "recruiter_profile", None)
    company_name = company.company_name if company and company.company_name else recruiter.get_full_name() or recruiter.username

    subject = f"[Immigration97] {company_name} vous a envoyé une invitation d'entretien"
    message = f"""Bonjour {candidate.get_full_name() or candidate.username},

{company_name} vous a envoyé une invitation d'entretien sur Immigration97.

Message :
{invite.message}

Pour accepter ou refuser cette invitation, connectez-vous à votre espace :
https://immigration97.com/profiles/me/invitations/

Cordialement,
L'équipe Immigration97
"""
    try:
        send_mail(subject, message, FROM, [candidate.email], fail_silently=False)
        logger.info("Email invite_received envoyé à %s", candidate.email)
    except Exception as e:
        logger.error("Erreur envoi email invite_received à %s : %s", candidate.email, e)


def send_invite_accepted(invite):
    """Email envoyé au recruteur quand le candidat accepte l'invitation."""
    recruiter = invite.recruiter
    candidate = invite.candidate_user
    candidate_name = candidate.get_full_name() or candidate.username

    subject = f"[Immigration97] {candidate_name} a accepté votre invitation d'entretien"
    message = f"""Bonjour {recruiter.get_full_name() or recruiter.username},

Bonne nouvelle ! {candidate_name} a accepté votre invitation d'entretien.

Vous pouvez contacter le candidat directement ou consulter son profil :
https://immigration97.com/profiles/

Suivez vos invitations depuis votre tableau de bord :
https://immigration97.com/recruteur/invitations/

Cordialement,
L'équipe Immigration97
"""
    try:
        send_mail(subject, message, FROM, [recruiter.email], fail_silently=False)
        logger.info("Email invite_accepted envoyé à %s", recruiter.email)
    except Exception as e:
        logger.error("Erreur envoi email invite_accepted à %s : %s", recruiter.email, e)


def send_invite_declined(invite):
    """Email envoyé au recruteur quand le candidat refuse l'invitation."""
    recruiter = invite.recruiter
    candidate = invite.candidate_user
    candidate_name = candidate.get_full_name() or candidate.username

    subject = f"[Immigration97] {candidate_name} a refusé votre invitation d'entretien"
    message = f"""Bonjour {recruiter.get_full_name() or recruiter.username},

{candidate_name} a décliné votre invitation d'entretien.

Vous pouvez continuer à chercher des candidats :
https://immigration97.com/profiles/

Suivez vos invitations depuis votre tableau de bord :
https://immigration97.com/recruteur/invitations/

Cordialement,
L'équipe Immigration97
"""
    try:
        send_mail(subject, message, FROM, [recruiter.email], fail_silently=False)
        logger.info("Email invite_declined envoyé à %s", recruiter.email)
    except Exception as e:
        logger.error("Erreur envoi email invite_declined à %s : %s", recruiter.email, e)
