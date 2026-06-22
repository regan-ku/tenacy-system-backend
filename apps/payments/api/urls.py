from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PaymentAccountViewSet, InvoiceViewSet, PaymentHistoryViewSet,
    FinancialDashboardView, FinancialActionView, ReceiptViewSet
)

router = DefaultRouter()
router.register(r"accounts", PaymentAccountViewSet, basename="payment-account")
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"payments", PaymentHistoryViewSet, basename="payment-history")
router.register(r"receipts", ReceiptViewSet, basename="receipt")

urlpatterns = [
    path("", include(router.urls)),
    path("dashboard/", FinancialDashboardView.as_view({"get": "list"}), name="financial-dashboard"),
    path("actions/stk-push/", FinancialActionView.as_view({"post": "request_stk_push"}), name="stk-request"),
    path("actions/waiver/", FinancialActionView.as_view({"post": "apply_waiver"}), name="waiver-apply"),
    path("actions/refund/", FinancialActionView.as_view({"post": "request_refund"}), name="refund-request"),
]