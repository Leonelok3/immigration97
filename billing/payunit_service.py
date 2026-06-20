import logging
import uuid

from django.conf import settings
import requests

logger = logging.getLogger(__name__)


def _extract_payment_url(response):
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("payment_url", "authorization_url", "redirect_url", "transaction_url", "url", "link"):
            value = response.get(key)
            if value:
                return value
        data = response.get("data")
        if isinstance(data, dict):
            for key in ("payment_url", "authorization_url", "redirect_url", "transaction_url", "url", "link"):
                value = data.get(key)
                if value:
                    return value
    return None


def make_payunit_refs():
    return {
        "purchase_ref": str(uuid.uuid4())[:10],
        "transaction_id": str(uuid.uuid4()).replace("-", "")[:19],
    }


def initialize_payunit_payment(*, amount_xaf, description, return_url, notify_url, refs):
    if not getattr(settings, "PAYUNIT_AVAILABLE", False):
        return {"success": False, "error": "PAYUNIT_API_PASSWORD ou PAYUNIT_API_KEY non configuré."}

    amount = int(amount_xaf)
    if amount <= 0:
        return {"success": False, "error": "Montant PayUnit invalide."}

    try:
        auth = requests.auth.HTTPBasicAuth(
            settings.PAYUNIT_API_USERNAME,
            settings.PAYUNIT_API_PASSWORD,
        )
        headers = {
            "x-api-key": settings.PAYUNIT_API_KEY,
            "content-type": "application/json",
            "mode": settings.PAYUNIT_MODE,
        }
        payload = {
            "notify_url": notify_url,
            "total_amount": str(amount),
            "return_url": return_url,
            "purchaseRef": refs["purchase_ref"],
            "description": description or "Paiement sur immigration97.com",
            "name": "Immigration97",
            "currency": settings.PAYUNIT_CURRENCY,
            "transaction_id": refs["transaction_id"],
        }

        response = requests.post(
            "https://app.payunit.net/api/gateway/initialize",
            json=payload,
            auth=auth,
            headers=headers,
            timeout=30,
        )
        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text}

        if response.status_code >= 400:
            return {
                "success": False,
                "error": data.get("message") or f"PayUnit HTTP {response.status_code}",
                "raw": data,
            }

        status_code = str(data.get("statusCode") or data.get("status_code") or "")
        if status_code and status_code not in {"200", "201"}:
            return {
                "success": False,
                "error": data.get("message") or "PayUnit a refusé l'initialisation.",
                "raw": data,
            }

        payment_url = _extract_payment_url(data)
        if not payment_url:
            return {"success": False, "error": "PayUnit n'a pas renvoyé de lien de paiement.", "raw": data}
        return {"success": True, "payment_url": payment_url, "raw": data}
    except requests.RequestException as exc:
        logger.exception("Erreur réseau initialisation PayUnit")
        return {"success": False, "error": f"Impossible de joindre PayUnit: {exc}"}
    except Exception as exc:
        logger.exception("Erreur initialisation PayUnit")
        return {"success": False, "error": str(exc)}


def initialize_payunit_payment_with_sdk(*, amount_xaf, description, return_url, notify_url, refs):
    """Ancien fallback conservé pour diagnostic; l'API directe ci-dessus évite webbrowser.open()."""
    try:
        from payUnit import payUnit

        payment = payUnit({
            "apiUsername": settings.PAYUNIT_API_USERNAME,
            "apiPassword": settings.PAYUNIT_API_PASSWORD,
            "api_key": settings.PAYUNIT_API_KEY,
            "return_url": return_url,
            "notify_url": notify_url,
            "mode": settings.PAYUNIT_MODE,
            "name": "Immigration97",
            "description": description or "Paiement sur immigration97.com",
            "purchaseRef": refs["purchase_ref"],
            "currency": settings.PAYUNIT_CURRENCY,
            "transaction_id": refs["transaction_id"],
        })
        response = payment.makePayment(int(amount_xaf))
        payment_url = _extract_payment_url(response)
        if not payment_url:
            return {"success": False, "error": "PayUnit n'a pas renvoyé de lien de paiement.", "raw": response}
        return {"success": True, "payment_url": payment_url, "raw": response}
    except Exception as exc:
        logger.exception("Erreur initialisation PayUnit")
        return {"success": False, "error": str(exc)}
