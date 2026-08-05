import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


def _upload_contract_path(instance, filename):
    return f"esignature/contracts/{instance.uuid}/{filename}"


def _upload_signed_path(instance, filename):
    return f"esignature/signed/{instance.uuid}/{filename}"


class ContractDocument(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="esignature_contracts",
    )
    title = models.CharField(max_length=255)
    original_file = models.FileField(upload_to=_upload_contract_path)
    signed_file = models.FileField(upload_to=_upload_signed_path, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_signed = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ContractDocument({self.title}, signed={self.is_signed})"


class SigningRequest(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    contract = models.ForeignKey(
        ContractDocument,
        on_delete=models.CASCADE,
        related_name="signing_requests",
    )
    recipient_email = models.EmailField()
    token = models.CharField(max_length=128, unique=True, editable=False)
    is_completed = models.BooleanField(default=False)
    is_expired = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SigningRequest({self.recipient_email}, completed={self.is_completed})"


class SignatureEvent(models.Model):
    signing_request = models.OneToOneField(
        SigningRequest,
        on_delete=models.CASCADE,
        related_name="signature_event",
    )
    full_name = models.CharField(max_length=255)
    signature_data = models.TextField()
    signed_at = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    audit_log = models.JSONField(default=dict)

    class Meta:
        ordering = ["-signed_at"]

    def __str__(self):
        return f"SignatureEvent({self.full_name}, signed_at={self.signed_at.isoformat()})"
