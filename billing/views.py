# billing/views.py
from datetime import timedelta
from decimal import Decimal
import uuid
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from .forms import WalletReloadForm
from .models import SubscriptionPlan, CreditCode, Subscription, Transaction
from .services import (
    activate_pass,  # garde si tu l'utilises ailleurs
    has_active_access,
    grant_session_access,
    has_session_access,
)

# ✅ Parrainage / Commissions (affiliate)
# Si ce fichier n'existe pas encore, crée-le (je peux te le renvoyer).
from .affiliates import create_commission_for_transaction


def _redirect_next_or(default_path, request):
    nxt = request.GET.get("next") or request.POST.get("next")
    return redirect(nxt if nxt else default_path)


def rate_limit_redeem(request, limit=5, window_seconds=60):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"redeem:{ip}"
    current = cache.get(key, 0)

    if current >= limit:
        return True

    try:
        if current == 0:
            cache.set(key, 1, timeout=window_seconds)
        else:
            cache.incr(key)
    except Exception:
        cache.set(key, current + 1, timeout=window_seconds)

    return False


# =============================================================================
# PAGES PUBLIQUES
# =============================================================================

def pricing(request):
    from django.conf import settings as django_settings
    candidate_plans = SubscriptionPlan.objects.filter(
        is_active=True, plan_type="candidate"
    ).order_by("order", "duration_days")
    recruiter_plans = SubscriptionPlan.objects.filter(
        is_active=True, plan_type="recruiter"
    ).order_by("order")

    has_active_sub = request.user.is_authenticated and has_active_access(request.user)
    notchpay_available = bool(getattr(django_settings, "NOTCHPAY_PUBLIC_KEY", ""))
    payunit_available = bool(getattr(django_settings, "PAYUNIT_AVAILABLE", False))

    return render(request, "billing/pricing.html", {
        "candidate_plans": candidate_plans,
        "recruiter_plans": recruiter_plans,
        "plans": candidate_plans,
        "has_active_sub": has_active_sub,
        "payunit_available": payunit_available,
        "notchpay_available": notchpay_available,
        "next": request.GET.get("next", ""),
    })


def access(request):
    now = timezone.now()
    active_sub = None
    expires = None

    if request.user.is_authenticated:
        active_sub = (
            Subscription.objects
            .filter(user=request.user, expires_at__gt=now)
            .select_related("plan")
            .order_by("-expires_at")
            .first()
        )
        expires = active_sub.expires_at if active_sub else None

    session_active = has_session_access(request)
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("price_usd")

    return render(request, "billing/access.html", {
        "expires": expires,
        "active_subscription": active_sub,
        "session_active": session_active,
        "plans": plans,
        "next": request.GET.get("next", ""),
    })


# =============================================================================
# ACHAT - DEMO
# =============================================================================

def buy(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by("price_usd")
    if request.method == "POST":
        grant_session_access(request, minutes=30)
        messages.success(request, "✅ Accès activé pendant 30 minutes (DEMO).")
        return _redirect_next_or(reverse("billing:access"), request)

    return render(request, "billing/buy.html", {
        "plans": plans,
        "next": request.GET.get("next", ""),
    })


# =============================================================================
# CODES PRÉPAYÉS (STAFF)
# =============================================================================

@login_required
def generate_code(request):
    if not request.user.is_staff:
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("billing:pricing")

    plans = SubscriptionPlan.objects.filter(is_active=True)

    if request.method == "POST":
        plan_slug = request.POST.get("plan")
        quantity = int(request.POST.get("quantity", 1))
        quantity = min(max(quantity, 1), 1000)

        plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)

        batch_id = str(uuid.uuid4())[:8]
        expires_at = timezone.now() + timedelta(days=90)

        generated_codes = []
        for _ in range(quantity):
            tries = 0
            while True:
                tries += 1
                code_str = CreditCode.generate_unique()
                try:
                    credit_code = CreditCode.objects.create(
                        code=code_str,
                        plan=plan,
                        expiration_date=expires_at,
                        created_by_staff=request.user,
                        batch_id=batch_id,
                        notes=f"Généré via vue staff (batch {batch_id})",
                        max_uses=1,
                    )
                    generated_codes.append(credit_code)
                    break
                except IntegrityError:
                    if tries >= 5:
                        messages.error(request, "Erreur génération code (collision répétée).")
                        break

        return render(request, "billing/generate_code.html", {
            "codes": generated_codes,
            "plans": plans,
            "batch_id": batch_id,
        })

    return render(request, "billing/generate_code.html", {"plans": plans})


# =============================================================================
# REDEEM (CODES)
# =============================================================================

def redeem(request):
    if request.method == "POST":
        if rate_limit_redeem(request, limit=5, window_seconds=60):
            messages.error(request, "⛔ Trop de tentatives. Réessaie dans 1 minute.")
            return _redirect_next_or(reverse("billing:redeem"), request)

        code = (request.POST.get("code") or "").strip().upper()
        if not code:
            messages.error(request, "❌ Entre un code.")
            return _redirect_next_or(reverse("billing:redeem"), request)

        try:
            cc = CreditCode.objects.select_related("plan").get(code__iexact=code)
        except CreditCode.DoesNotExist:
            messages.error(request, "❌ Code invalide.")
            return _redirect_next_or(reverse("billing:redeem"), request)

        try:
            cc.use(
                user=request.user if request.user.is_authenticated else None,
                ip=request.META.get("REMOTE_ADDR"),
            )
        except ValueError as e:
            messages.error(request, f"❌ {str(e)}")
            return _redirect_next_or(reverse("billing:redeem"), request)

        if request.user.is_authenticated:
            sub, created = Subscription.activate_or_extend(user=request.user, plan=cc.plan)

            # ✅ TX COMPLETED (base commission = prix plan même si amount=0)
            tx = Transaction.objects.create(
                user=request.user,
                plan=cc.plan,
                amount=Decimal("0.00"),
                currency="USD",
                type="CREDIT",
                status="COMPLETED",
                payment_method="CODE",
                description=f"Activation via code {cc.code}",
                related_code=cc,
                related_subscription=sub,
                metadata={
                    "stacking": True,
                    "created_new_subscription": created,
                    "ip": request.META.get("REMOTE_ADDR"),
                    "code": cc.code,
                    "commission_base": str(cc.plan.price_usd),  # ✅ pour parrainage sur codes
                },
            )

            # ✅ Commission si le user a été parrainé
            create_commission_for_transaction(tx)

            from .emails import send_welcome_subscription
            send_welcome_subscription(request.user, cc.plan, sub)

            expire_str = sub.expires_at.strftime("%d/%m/%Y %H:%M")
            messages.success(
                request,
                "Code valide ! Acces active jusqu’au " + expire_str + "."
            )
        else:
            grant_session_access(request, minutes=60)
            messages.success(request, "Code valide ! Acces temporaire active (1h).")

        return _redirect_next_or(reverse("billing:access"), request)

    active_sub = None
    if request.user.is_authenticated:
        active_sub = (
            Subscription.objects
            .filter(user=request.user, expires_at__gt=timezone.now())
            .select_related("plan")
            .order_by("-expires_at")
            .first()
        )
    return render(request, "billing/redeem.html", {
        "next": request.GET.get("next", ""),
        "active_sub": active_sub,
    })


# =============================================================================
# DASHBOARD WALLET
# =============================================================================

@login_required
def wallet_dashboard(request):
    now = timezone.now()

    active_sub = (
        Subscription.objects
        .filter(user=request.user, expires_at__gt=now)
        .select_related("plan")
        .order_by("-expires_at")
        .first()
    )

    subscriptions = (
        Subscription.objects
        .filter(user=request.user)
        .select_related("plan")
        .order_by("-starts_at")[:10]
    )

    transactions = (
        Transaction.objects
        .filter(user=request.user)
        .select_related("plan")
        .order_by("-created_at")[:20]
    )

    codes_used = (
        CreditCode.objects
        .filter(used_by=request.user)
        .select_related("plan")
        .order_by("-used_at")[:10]
    )

    return render(request, "billing/wallet.html", {
        "active_subscription": active_sub,
        "subscriptions": subscriptions,
        "transactions": transactions,
        "codes_used": codes_used,
        "has_access": active_sub is not None,
        "now": now,
        "wallet": None,  # pour tes templates
    })


# =============================================================================
# FLOW PAIEMENT (placeholder)
# =============================================================================

def _complete_paid_transaction(tx, *, provider, provider_metadata=None):
    if tx.status == "COMPLETED" and tx.related_subscription_id:
        return tx.related_subscription

    provider_metadata = provider_metadata or {}
    payment_method = provider
    if provider == "PAYUNIT":
        channel = (
            provider_metadata.get("payunit_channel")
            or (tx.metadata or {}).get("payunit_channel")
            or ""
        )
        payment_method = "CARD" if channel == "card" else "MOBILE_MONEY"

    tx.status = "COMPLETED"
    tx.payment_method = payment_method
    tx.metadata = {
        **(tx.metadata or {}),
        "provider": provider,
        **provider_metadata,
    }
    tx.save(update_fields=["status", "payment_method", "metadata"])

    sub, _ = Subscription.activate_or_extend(user=tx.user, plan=tx.plan)
    tx.related_subscription = sub
    tx.save(update_fields=["related_subscription"])

    create_commission_for_transaction(tx)

    from .emails import send_welcome_subscription
    send_welcome_subscription(tx.user, tx.plan, sub)
    return sub


def _payunit_status_from_payload(payload):
    status = (
        payload.get("status")
        or payload.get("transaction_status")
        or payload.get("transactionStatus")
        or payload.get("payment_status")
        or payload.get("state")
        or ""
    )
    return str(status).strip().lower()


def _payunit_status_is_success(status):
    return status in {"success", "successful", "complete", "completed", "paid", "approved"}


def _payunit_status_is_failure(status):
    return status in {"failed", "failure", "cancelled", "canceled", "declined", "expired", "error"}


def _whatsapp_code_url(plan, request):
    text = (
        "Bonjour Immigration97, je veux payer l'abonnement "
        f"{plan.name} ({plan.price_usd} USD / environ {plan.price_xaf} FCFA) "
        "et recevoir un code d'abonnement."
    )
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url:
        text += f" Mon lien de retour: {request.build_absolute_uri(next_url)}"
    return "https://wa.me/237693649944?text=" + quote(text)


@login_required
def buy_plan(request, plan_slug):
    plan = get_object_or_404(SubscriptionPlan, slug=plan_slug, is_active=True)

    from django.conf import settings
    notchpay_available = bool(getattr(settings, "NOTCHPAY_PUBLIC_KEY", ""))
    payunit_available = bool(getattr(settings, "PAYUNIT_AVAILABLE", False))

    tx = Transaction.objects.create(
        user=request.user,
        plan=plan,
        amount=plan.price_xaf,
        currency="XAF",
        type="CREDIT",
        status="PENDING",
        description=f"Achat {plan.name}",
        payment_method="MOBILE_MONEY" if payunit_available else "OTHER",
        metadata={"provider": "PAYUNIT" if payunit_available else "NOTCHPAY"},
    )

    return render(request, "billing/buy_plan.html", {
        "plan": plan,
        "transaction": tx,
        "payunit_available": payunit_available,
        "notchpay_available": notchpay_available,
        "cinetpay_available": False,
        "stripe_available": False,
        "next": request.GET.get("next", ""),
    })


@login_required
def initiate_payment(request, transaction_id):
    from django.conf import settings
    from .notchpay_service import initialize_payment, make_reference

    tx = get_object_or_404(Transaction, id=transaction_id, user=request.user)

    if tx.status != "PENDING":
        messages.error(request, "Cette transaction a déjà été traitée.")
        return redirect("billing:wallet")

    if request.method != "POST":
        return redirect("billing:buy_plan", plan_slug=tx.plan.slug)

    selected_method = (request.POST.get("payment_method") or "").upper()
    if selected_method == "WHATSAPP_CODE":
        tx.metadata = {
            **(tx.metadata or {}),
            "provider": "WHATSAPP",
            "payment_choice": "whatsapp_code",
        }
        tx.save(update_fields=["metadata"])
        return redirect(_whatsapp_code_url(tx.plan, request))

    payunit_methods = {
        "PAYUNIT": ("mobile_money", "Mobile Money"),
        "PAYUNIT_MTN": ("mtn_momo", "MTN Mobile Money"),
        "PAYUNIT_ORANGE": ("orange_money", "Orange Money"),
        "PAYUNIT_CARD": ("card", "Carte bancaire"),
    }

    if selected_method in payunit_methods:
        from .payunit_service import initialize_payunit_payment, make_payunit_refs

        payunit_available = bool(getattr(settings, "PAYUNIT_AVAILABLE", False))
        if not payunit_available:
            messages.warning(
                request,
                "Paiement en ligne indisponible pour le moment. Contacte-nous sur WhatsApp pour recevoir un code.",
            )
            return redirect(_whatsapp_code_url(tx.plan, request))

        payunit_channel, payunit_label = payunit_methods[selected_method]
        refs = make_payunit_refs()
        tx.metadata = {
            **(tx.metadata or {}),
            "provider": "PAYUNIT",
            "payment_choice": selected_method,
            "payunit_channel": payunit_channel,
            "payunit_channel_label": payunit_label,
            "payunit_purchase_ref": refs["purchase_ref"],
            "payunit_transaction_id": refs["transaction_id"],
        }
        tx.payment_method = "CARD" if payunit_channel == "card" else "MOBILE_MONEY"
        tx.description = f"Achat {tx.plan.name} - {payunit_label}"
        tx.save(update_fields=["payment_method", "description", "metadata"])

        return_url = request.build_absolute_uri(
            reverse("billing:payunit_return") + f"?tx={tx.id}&ref={refs['purchase_ref']}"
        )
        notify_url = request.build_absolute_uri(
            reverse("billing:payunit_notify") + f"?tx={tx.id}&ref={refs['purchase_ref']}"
        )
        result = initialize_payunit_payment(
            amount_xaf=int(tx.amount),
            description=f"Immigration97 - {tx.plan.name} - {payunit_label}",
            return_url=return_url,
            notify_url=notify_url,
            refs=refs,
        )
        if result["success"]:
            tx.metadata = {
                **(tx.metadata or {}),
                "payunit_initialized": True,
                "payunit_init_response": result.get("raw"),
            }
            tx.save(update_fields=["metadata"])
            return redirect(result["payment_url"])

        tx.status = "FAILED"
        tx.metadata = {
            **(tx.metadata or {}),
            "payunit_error": result.get("error"),
            "payunit_init_response": result.get("raw"),
        }
        tx.save(update_fields=["status", "metadata"])
        messages.error(request, f"Erreur PayUnit : {result.get('error', 'initialisation impossible')}")
        return redirect(reverse("billing:payment_failed") + f"?tx={tx.id}")

    notchpay_available = bool(getattr(settings, "NOTCHPAY_PUBLIC_KEY", ""))
    if not notchpay_available:
        messages.warning(request, "Paiement en ligne bientôt disponible. Utilise un code prépayé.")
        return redirect("billing:redeem")

    reference = make_reference()
    tx.metadata = {**(tx.metadata or {}), "notchpay_ref": reference}
    tx.save(update_fields=["metadata"])

    callback_url = request.build_absolute_uri(
        reverse("billing:notchpay_callback") + f"?tx={tx.id}&ref={reference}"
    )

    result = initialize_payment(
        amount_xaf=int(tx.amount),
        email=request.user.email,
        reference=reference,
        description=f"Immigration97 — {tx.plan.name}",
        callback_url=callback_url,
        name=request.user.get_full_name() or request.user.username,
    )

    if result["success"]:
        return redirect(result["authorization_url"])

    messages.error(request, f"Erreur paiement : {result['error']}")
    return redirect("billing:buy_plan", plan_slug=tx.plan.slug)


# =============================================================================
# NOTCHPAY — CALLBACK (retour après paiement)
# =============================================================================

@login_required
def notchpay_callback(request):
    """NotchPay redirige l'utilisateur ici après paiement (succès ou échec)."""
    from .notchpay_service import verify_payment

    tx_id = request.GET.get("tx")
    reference = request.GET.get("ref")
    trxref = request.GET.get("trxref") or reference  # NotchPay peut envoyer trxref

    if not tx_id or not trxref:
        messages.error(request, "Paramètres de paiement manquants.")
        return redirect("billing:pricing")

    tx = get_object_or_404(Transaction, id=tx_id, user=request.user)

    if tx.status == "COMPLETED":
        messages.success(request, "✅ Ton abonnement est déjà actif !")
        return redirect("billing:wallet")

    result = verify_payment(trxref)

    if result["success"] and result["status"] == "complete":
        sub = _complete_paid_transaction(
            tx,
            provider="NOTCHPAY",
            provider_metadata={"notchpay_verified": True, "notchpay_ref": trxref},
        )
        return redirect(reverse("billing:payment_success") + f"?sub={sub.id}")

    # Paiement échoué ou en attente
    tx.status = "FAILED"
    tx.metadata = {**(tx.metadata or {}), "notchpay_status": result.get("status"), "notchpay_ref": trxref}
    tx.save(update_fields=["status", "metadata"])

    messages.error(request, "❌ Paiement non confirmé. Réessaie ou utilise un code.")
    return redirect("billing:buy_plan", plan_slug=tx.plan.slug)


# =============================================================================
# NOTCHPAY — WEBHOOK (notification serveur-à-serveur)
# =============================================================================

from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import json as _json

@csrf_exempt
def notchpay_webhook(request):
    """
    NotchPay POST ce endpoint dès qu'un paiement change de statut.
    Configurer dans NotchPay dashboard → Webhooks → https://immigration97.com/billing/notchpay/webhook/
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    from .notchpay_service import verify_webhook_signature, verify_payment

    payload_bytes = request.body
    signature = request.headers.get("X-Notch-Signature", "")

    if not verify_webhook_signature(payload_bytes, signature):
        return HttpResponse("Signature invalide", status=403)

    try:
        data = _json.loads(payload_bytes)
    except _json.JSONDecodeError:
        return HttpResponse("JSON invalide", status=400)

    event = data.get("event", "")
    txn = data.get("transaction", {})
    reference = txn.get("reference", "")

    if not reference:
        return HttpResponse("OK", status=200)

    # Cherche la transaction Django via metadata notchpay_ref
    tx = (
        Transaction.objects
        .filter(metadata__notchpay_ref=reference)
        .select_related("plan", "user")
        .first()
    )

    if not tx:
        return HttpResponse("OK", status=200)  # pas notre transaction

    if event == "payment.complete" and txn.get("status", "").lower() == "complete":
        if tx.status != "COMPLETED":
            tx.status = "COMPLETED"
            tx.payment_method = "NOTCHPAY"
            tx.metadata = {**(tx.metadata or {}), "webhook_event": event}
            tx.save(update_fields=["status", "payment_method", "metadata"])

            sub, _ = Subscription.activate_or_extend(user=tx.user, plan=tx.plan)
            tx.related_subscription = sub
            tx.save(update_fields=["related_subscription"])

            create_commission_for_transaction(tx)

    return HttpResponse("OK", status=200)


@login_required
def payunit_return(request):
    tx_id = request.GET.get("tx")
    purchase_ref = request.GET.get("ref") or request.GET.get("purchaseRef")
    status = _payunit_status_from_payload(request.GET)
    if not tx_id:
        messages.error(request, "Paramètres PayUnit manquants.")
        return redirect("billing:pricing")

    tx = get_object_or_404(Transaction.objects.select_related("plan", "user"), id=tx_id, user=request.user)
    if tx.status == "COMPLETED":
        messages.success(request, "Ton abonnement est déjà actif.")
        return redirect("billing:wallet")

    if _payunit_status_is_failure(status):
        tx.status = "FAILED"
        tx.metadata = {
            **(tx.metadata or {}),
            "payunit_return": True,
            "payunit_status": status,
            "payunit_purchase_ref": purchase_ref or (tx.metadata or {}).get("payunit_purchase_ref"),
            "payunit_query": dict(request.GET.items()),
        }
        tx.save(update_fields=["status", "metadata"])
        messages.error(request, "Paiement PayUnit non confirmé. Tu peux réessayer.")
        return redirect(reverse("billing:payment_failed") + f"?tx={tx.id}")

    sub = _complete_paid_transaction(
        tx,
        provider="PAYUNIT",
        provider_metadata={
            "payunit_return": True,
            "payunit_status": status or "return_without_status",
            "payunit_purchase_ref": purchase_ref or (tx.metadata or {}).get("payunit_purchase_ref"),
            "payunit_query": dict(request.GET.items()),
        },
    )
    messages.success(request, "Paiement confirmé. Ton accès Premium est actif.")
    return redirect(reverse("billing:payment_success") + f"?sub={sub.id}")


@csrf_exempt
def payunit_notify(request):
    payload = {}
    if request.method == "POST":
        try:
            payload = _json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            payload = request.POST.dict()
    else:
        payload = request.GET.dict()

    tx_id = request.GET.get("tx") or payload.get("tx") or payload.get("transaction")
    purchase_ref = (
        request.GET.get("ref")
        or payload.get("purchaseRef")
        or payload.get("purchase_ref")
        or payload.get("ref")
    )
    payunit_transaction_id = payload.get("transaction_id") or payload.get("transactionId")

    tx_qs = Transaction.objects.select_related("plan", "user")
    tx = None
    if tx_id:
        tx = tx_qs.filter(id=tx_id).first()
    if not tx and purchase_ref:
        tx = tx_qs.filter(metadata__payunit_purchase_ref=purchase_ref).first()
    if not tx and payunit_transaction_id:
        tx = tx_qs.filter(metadata__payunit_transaction_id=payunit_transaction_id).first()

    if not tx:
        return HttpResponse("OK", status=200)

    status = _payunit_status_from_payload(payload)
    if not status or _payunit_status_is_success(status):
        _complete_paid_transaction(
            tx,
            provider="PAYUNIT",
            provider_metadata={
                "payunit_notify": True,
                "payunit_status": status or "notification_received",
                "payunit_payload": payload,
            },
        )
    elif tx.status == "PENDING":
        tx.status = "FAILED"
        tx.metadata = {**(tx.metadata or {}), "payunit_status": status, "payunit_payload": payload}
        tx.save(update_fields=["status", "metadata"])

    return HttpResponse("OK", status=200)


# =============================================================================
# RECHARGE WALLET (DEMO)
# =============================================================================

@login_required
def reload_wallet(request):
    form = WalletReloadForm(request.POST or None)
    wallet = None

    if request.method == "POST":
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            note = form.cleaned_data.get("note") or ""

            tx = Transaction.objects.create(
                user=request.user,
                plan=None,
                amount=Decimal(amount),
                currency="USD",
                type="CREDIT",
                status="COMPLETED",
                payment_method="WALLET_TOPUP",
                description="Recharge wallet (DEMO)",
                metadata={
                    "note": note,
                    "at": timezone.now().isoformat(),
                    "ip": request.META.get("REMOTE_ADDR"),
                },
            )

            # ✅ Optionnel : commission si tu veux récompenser aussi les recharges
            # Si tu ne veux PAS de commission sur wallet, supprime la ligne suivante.
            create_commission_for_transaction(tx)

            messages.success(request, f"✅ Recharge enregistrée : +{amount} USD (DEMO).")
            return redirect("billing:wallet")

        messages.error(request, "❌ Vérifie le montant et réessaie.")

    return render(request, "billing/reload.html", {"form": form, "wallet": wallet})




################################## facture ###################################

from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
from .models import Receipt
from .pdf import build_receipt_pdf


def receipt_detail(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    return render(request, "billing/receipt_detail.html", {"receipt": receipt})


def receipt_pdf(request, receipt_id):
    receipt = get_object_or_404(Receipt, id=receipt_id)
    pdf_bytes = build_receipt_pdf(receipt)

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{receipt.receipt_number}.pdf"'
    return response


def contract_protection(request):
    """
    Page bilingue (FR/EN) : Contrat de protection Immigration97.
    """
    return render(request, "billing/contract_protection.html")


@login_required
def payment_success(request):
    """Page de confirmation post-paiement."""
    sub_id = request.GET.get("sub")
    subscription = None
    if sub_id:
        subscription = (
            Subscription.objects
            .filter(id=sub_id, user=request.user)
            .select_related("plan")
            .first()
        )
    return render(request, "billing/payment_success.html", {"subscription": subscription})


@login_required
def payment_failed(request):
    tx_id = request.GET.get("tx")
    transaction = None
    if tx_id:
        transaction = (
            Transaction.objects
            .filter(id=tx_id, user=request.user)
            .select_related("plan")
            .first()
        )
    return render(request, "billing/payment_failed.html", {"transaction": transaction})


def politique_remboursement(request):
    return render(request, "billing/politique_remboursement.html")


def conditions_utilisation(request):
    return render(request, "billing/conditions_utilisation.html")



from django.http import Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.utils import timezone

from .models import Receipt


def render_receipt_pdf(receipt: Receipt, response: HttpResponse) -> None:
    # même fonction que dans admin (copie-colle si besoin)
    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4
    x, y = 50, height - 60

    p.setFont("Helvetica-Bold", 18)
    p.drawString(x, y, "IMMIGRATION97")
    p.setFont("Helvetica", 10)
    p.drawString(x, y - 18, "Plateforme d'immigration légale — www.immigration97.com")

    y -= 60
    p.setFont("Helvetica-Bold", 14)
    p.drawString(x, y, "REÇU / FACTURE")

    y -= 22
    p.setFont("Helvetica", 10)
    p.drawString(x, y, f"N° Reçu : {receipt.receipt_number}")
    p.drawString(x + 260, y, f"Date : {timezone.localtime(receipt.issued_at).strftime('%d/%m/%Y %H:%M')}")

    y -= 18
    p.drawString(x, y, f"Statut : {receipt.get_status_display()}")
    p.drawString(x + 260, y, f"Méthode : {receipt.payment_method or '-'}")

    y -= 35
    p.setFont("Helvetica-Bold", 11)
    p.drawString(x, y, "Client")
    y -= 16
    p.setFont("Helvetica", 10)
    p.drawString(x, y, receipt.client_full_name)

    y -= 35
    p.setFont("Helvetica-Bold", 12)
    p.drawString(x, y, "Total")
    y -= 18
    p.setFont("Helvetica-Bold", 16)
    p.drawString(x, y, f"{receipt.amount} {receipt.currency}")

    p.setFont("Helvetica", 9)
    p.drawString(x, 55, "Ce reçu est généré automatiquement par Immigration97.")
    p.drawString(x, 40, "support@immigration97.com")

    p.showPage()
    p.save()


@login_required
def receipt_pdf(request, pk):
    try:
        receipt = Receipt.objects.get(pk=pk)
    except Receipt.DoesNotExist:
        raise Http404("Reçu introuvable")

    filename = f"recu-{receipt.receipt_number}.pdf"
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{filename}"'
    render_receipt_pdf(receipt, response)
    return response
