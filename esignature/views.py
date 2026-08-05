import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import ContractDocument, SigningRequest, SignatureEvent
from .serializers import (
    ContractDocumentUploadSerializer,
    SignatureSubmitSerializer,
)
from .services import (
    attach_signature_to_pdf,
    build_audit_log,
    build_signed_filename,
    generate_secure_token,
    send_signed_document_email,
    send_signing_email,
)

logger = logging.getLogger(__name__)


def _is_admin_or_owner(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(_is_admin_or_owner)
def upload_contract(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    data = request.POST.copy()
    data.update(request.FILES)
    serializer = ContractDocumentUploadSerializer(data=data)
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        contract = ContractDocument.objects.create(
            owner=request.user,
            title=serializer.validated_data["title"],
            original_file=serializer.validated_data["original_file"],
        )
        token = generate_secure_token()
        expires_at = timezone.now() + timedelta(days=7)
        signing_request = SigningRequest.objects.create(
            contract=contract,
            recipient_email=serializer.validated_data["recipient_email"],
            token=token,
            expires_at=expires_at,
        )

    send_signing_email(request, signing_request)

    return JsonResponse(
        {
            "id": contract.id,
            "signing_request_id": signing_request.id,
            "signing_url": request.build_absolute_uri(
                reverse("esignature:sign_contract", args=[signing_request.token])
            ),
        },
        status=201,
    )


def sign_contract(request, token: str):
    signing_request = get_object_or_404(SigningRequest, token=token)

    if signing_request.is_completed or signing_request.is_expired or signing_request.contract.is_locked:
        raise Http404("Le lien de signature n'est plus valide.")

    if signing_request.expires_at < timezone.now():
        signing_request.is_expired = True
        signing_request.save(update_fields=["is_expired"])
        raise Http404("Le lien de signature a expiré.")

    preview_url = request.build_absolute_uri(
        reverse("esignature:preview_contract", args=[signing_request.token])
    )
    return render(
        request,
        "esignature/sign_contract.html",
        {
            "signing_request": signing_request,
            "preview_url": preview_url,
        },
    )


def preview_contract(request, token: str):
    signing_request = get_object_or_404(SigningRequest, token=token)

    if signing_request.is_completed or signing_request.is_expired or signing_request.contract.is_locked:
        raise Http404("Le lien de signature n'est plus valide.")

    if signing_request.expires_at < timezone.now():
        signing_request.is_expired = True
        signing_request.save(update_fields=["is_expired"])
        raise Http404("Le lien de signature a expiré.")

    response = FileResponse(
        open(signing_request.contract.original_file.path, "rb"),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = "inline; filename=contract.pdf"
    return response


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def submit_signature(request, token: str):
    signing_request = get_object_or_404(SigningRequest, token=token)

    if signing_request.is_completed or signing_request.is_expired or signing_request.contract.is_locked:
        return Response({"detail": "Le lien n'est plus valide."}, status=status.HTTP_400_BAD_REQUEST)

    if signing_request.expires_at < timezone.now():
        signing_request.is_expired = True
        signing_request.save(update_fields=["is_expired"])
        return Response({"detail": "Le lien a expiré."}, status=status.HTTP_400_BAD_REQUEST)

    serializer = SignatureSubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    data = serializer.validated_data
    if not data["acceptance"]:
        return Response({"detail": "Vous devez accepter le contrat."}, status=status.HTTP_400_BAD_REQUEST)
    if not data["viewed"]:
        return Response({"detail": "Vous devez confirmer avoir consulté le contrat."}, status=status.HTTP_400_BAD_REQUEST)

    contract = signing_request.contract
    if contract.is_signed or contract.is_locked:
        return Response({"detail": "Le document est verrouillé."}, status=status.HTTP_400_BAD_REQUEST)

    client_ip = request.META.get("REMOTE_ADDR", "")
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    audit_log = build_audit_log(request, signing_request, serializer.validated_data)

    with transaction.atomic():
        signature_event = SignatureEvent.objects.create(
            signing_request=signing_request,
            full_name=data["full_name"],
            signature_data=data["signature_data"],
            ip_address=client_ip,
            user_agent=user_agent,
            audit_log=audit_log,
        )

        signed_path = build_signed_filename(contract.original_file.name)
        signed_file_path = attach_signature_to_pdf(
            contract.original_file.path,
            signature_event,
            signed_path,
        )

        contract.signed_file.name = signed_file_path
        contract.is_signed = True
        contract.is_locked = True
        contract.save(update_fields=["signed_file", "is_signed", "is_locked"])

        signing_request.is_completed = True
        signing_request.save(update_fields=["is_completed"])

    send_signed_document_email(signing_request, contract)

    return Response({"ok": True}, status=status.HTTP_200_OK)
