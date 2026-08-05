from rest_framework import serializers


class ContractDocumentUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    original_file = serializers.FileField()
    recipient_email = serializers.EmailField()


class SigningRequestSerializer(serializers.Serializer):
    recipient_email = serializers.EmailField()


class SignatureSubmitSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    acceptance = serializers.BooleanField()
    signature_data = serializers.CharField()
    viewed = serializers.BooleanField()
