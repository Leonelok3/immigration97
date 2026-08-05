import os
import secrets
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage
from django.urls import reverse
from django.utils import timezone
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from pypdf import PdfReader, PdfWriter

from .models import SignatureEvent


def generate_secure_token() -> str:
    return secrets.token_urlsafe(48)


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def build_audit_log(request, signing_request, validated_data):
    return {
        "signing_request_id": str(signing_request.uuid),
        "recipient_email": signing_request.recipient_email,
        "contract_id": str(signing_request.contract.uuid),
        "created_at": timezone.now().isoformat(),
        "client_ip": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
        "accepted_terms": validated_data.get("acceptance"),
        "viewed_document": validated_data.get("viewed"),
        "signature_submitted": bool(validated_data.get("signature_data")),
    }


def build_signed_filename(original_name: str) -> str:
    base_name = Path(original_name).stem
    return f"esignature/signed/{base_name}-signed-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf"


def attach_signature_to_pdf(original_pdf_path: str, signature_event: SignatureEvent, signed_file_path: str) -> str:
    reader = PdfReader(original_pdf_path)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_overlay:
        overlay_graphics = canvas.Canvas(temp_overlay.name, pagesize=A4)
        overlay_graphics.setFont("Helvetica", 10)
        overlay_graphics.setFillColor(black)
        overlay_graphics.drawString(40, 90, f"Signataire : {signature_event.full_name}")
        overlay_graphics.drawString(40, 75, f"Date : {signature_event.signed_at.strftime('%Y-%m-%d %H:%M:%S')}")
        overlay_graphics.drawString(40, 60, "Document signé électroniquement.")
        overlay_graphics.drawString(40, 45, "Signature (hachée) :")
        overlay_graphics.drawString(40, 30, signature_event.signature_data[:80])
        overlay_graphics.save()

        overlay_reader = PdfReader(temp_overlay.name)
        last_page = reader.pages[-1]
        last_page.merge_page(overlay_reader.pages[0])

        signed_full_path = os.path.join(settings.MEDIA_ROOT, signed_file_path)
        os.makedirs(os.path.dirname(signed_full_path), exist_ok=True)
        with open(signed_full_path, "wb") as signed_output:
            writer.write(signed_output)

    os.unlink(temp_overlay.name)
    return signed_file_path


def send_signing_email(request, signing_request):
    subject = "Signature requise : contrat à signer"
    signing_url = request.build_absolute_uri(reverse("esignature:sign_contract", args=[signing_request.token]))
    body = (
        f"Bonjour,\n\n"
        f"Un contrat est en attente de signature. Cliquez sur le lien sécurisé ci-dessous :\n\n"
        f"{signing_url}\n\n"
        f"Ce lien expire le {signing_request.expires_at.strftime('%Y-%m-%d %H:%M:%S')}.\n\n"
        f"Merci."
    )
    email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [signing_request.recipient_email])
    email.send(fail_silently=False)


def send_signed_document_email(signing_request, contract):
    subject = "Contrat signé électroniquement"
    body = (
        f"Bonjour,\n\n"
        f"Le contrat '{contract.title}' a été signé par {signing_request.signature_event.full_name}.\n"
        f"Date et heure : {signing_request.signature_event.signed_at.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"Vous trouverez le document signé en pièce jointe.\n\n"
        f"Cordialement."
    )
    recipients = [signing_request.recipient_email, contract.owner.email]
    email = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, recipients)
    email.attach_file(contract.signed_file.path)
    email.send(fail_silently=False)
