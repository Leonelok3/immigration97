from django.contrib import admin

from .models import ContractDocument, SigningRequest, SignatureEvent


@admin.register(ContractDocument)
class ContractDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "is_signed", "is_locked", "created_at")
    search_fields = ("title", "owner__email", "owner__username")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SigningRequest)
class SigningRequestAdmin(admin.ModelAdmin):
    list_display = ("recipient_email", "contract", "is_completed", "is_expired", "expires_at")
    list_filter = ("is_completed", "is_expired", "expires_at")
    search_fields = ("recipient_email", "token", "contract__title")


@admin.register(SignatureEvent)
class SignatureEventAdmin(admin.ModelAdmin):
    list_display = ("full_name", "signing_request", "signed_at", "ip_address")
    readonly_fields = ("signed_at", "audit_log")
