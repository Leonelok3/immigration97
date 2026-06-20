from django.urls import path
from . import views
from . import views_affiliate

app_name = "billing"

urlpatterns = [
    path("", views.pricing, name="pricing"),
    path("access/", views.access, name="access"),
    path("buy/", views.buy, name="buy"),
    path("redeem/", views.redeem, name="redeem"),
    path("wallet/", views.wallet_dashboard, name="wallet"),
    path("wallet/reload/", views.reload_wallet, name="reload"),
    path("generate/", views.generate_code, name="generate_code"),

    path("buy/<slug:plan_slug>/", views.buy_plan, name="buy_plan"),
    path("payment/initiate/<int:transaction_id>/", views.initiate_payment, name="initiate_payment"),
    path("payment/failed/", views.payment_failed, name="payment_failed"),

    # ✅ referral
    path("ref/<str:ref_code>/", views_affiliate.ref_redirect, name="ref_redirect"),
    path("ref/<str:ref_code>/", views_affiliate.ref_redirect, name="ref_redirect"),

    ################################ facture des clients #############################
    path("receipts/<uuid:receipt_id>/", views.receipt_detail, name="receipt_detail"),
    path("receipts/<uuid:receipt_id>/pdf/", views.receipt_pdf, name="receipt_pdf"),
    path("contract-protection/", views.contract_protection, name="contract_protection"),
    path("politique-remboursement/", views.politique_remboursement, name="politique_remboursement"),
    path("conditions-utilisation/", views.conditions_utilisation, name="conditions_utilisation"),

    path("payment/success/", views.payment_success, name="payment_success"),

    # NotchPay
    path("notchpay/callback/", views.notchpay_callback, name="notchpay_callback"),
    path("notchpay/webhook/", views.notchpay_webhook, name="notchpay_webhook"),
    path("payunit/return/", views.payunit_return, name="payunit_return"),
    path("payunit/notify/", views.payunit_notify, name="payunit_notify"),
    path("receipt/<uuid:pk>/pdf/", views.receipt_pdf, name="receipt_pdf"),
]
