from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ContractDocument, SigningRequest
from .services import generate_secure_token

User = get_user_model()


class EsignatureFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", email="admin@example.com", password="pass1234", is_staff=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_upload_and_signing_request_creation(self):
        pdf_content = b"%PDF-1.4\n%Dummy PDF content\n"
        pdf_file = SimpleUploadedFile("contract.pdf", pdf_content, content_type="application/pdf")
        response = self.client.post(
            reverse("esignature:upload_contract"),
            {
                "title": "Contrat de test",
                "recipient_email": "recipient@example.com",
                "original_file": pdf_file,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("signing_url", response.json())
        contract = ContractDocument.objects.first()
        self.assertIsNotNone(contract)
        self.assertEqual(contract.owner, self.user)
        signing_request = SigningRequest.objects.first()
        self.assertIsNotNone(signing_request)
        self.assertFalse(signing_request.is_completed)
        self.assertGreater(signing_request.expires_at, timezone.now())

    def test_generate_secure_token_length(self):
        token = generate_secure_token()
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)
