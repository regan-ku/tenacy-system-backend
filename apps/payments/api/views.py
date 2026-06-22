from rest_framework import serializers, viewsets, mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import (
    PaymentAccountSerializer, InvoiceSerializer, PaymentSerializer, 
    ArrearsSerializer, TenantBalanceSerializer, WaiverRequestSerializer,
    RefundRequestSerializer, STKRequestSerializer
)
from ..models import PaymentAccount, Invoice, Payment, Arrears, TenantBalance, Receipt
from ..permissions.payment_permissions import (
    IsFinancialStakeholder, CanTriggerPaymentRequest, CanApproveFinancialOverride,
    CanManagePaymentAccounts, CanReconcileTransactions
)
from ..services.payment_account_service import PaymentAccountService
from ..services.payment_verification_service import PaymentVerificationService
from ..services.payment_service import PaymentService
from ..services.arrears_service import ArrearsService
from ..services.waiver_service import WaiverService
from ..services.refund_service import RefundService
from ..services.receipt_service import ReceiptService
from ..integrations.stk_push_service import PaymentStkOrchestrator

# ================= PAYMENT ACCOUNTS =================
class PaymentAccountViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentAccountSerializer
    permission_classes = [IsAuthenticated, CanManagePaymentAccounts]
    lookup_field = "id"

    def get_queryset(self):
        # ✅ SPECTACULAR GUARD: Prevents AnonymousUser crashes
        if getattr(self, "swagger_fake_view", False):
            return PaymentAccount.objects.none()
        user = self.request.user
        qs = PaymentAccount.objects.filter(owner=user)
        if user.is_staff:
            qs = PaymentAccount.objects.all()
        return qs.order_by("-is_default", "-is_verified", "-created_at")

    @extend_schema(responses={200: OpenApiResponse(description="Verification initiated successfully")})
    @action(detail=True, methods=["post"])
    def request_verification(self, request, id=None):
        account = self.get_object()
        ver = PaymentVerificationService.initiate_verification(str(account.id), request.user.id)
        return Response({"status": "initiated", "verification_id": str(ver.id)})

    @extend_schema(responses={200: OpenApiResponse(description="Account activated successfully")})
    @action(detail=True, methods=["post"])
    def activate(self, request, id=None):
        account = self.get_object()
        updated = PaymentAccountService.toggle_active(str(account.id), request.user.id, activate=True)
        return Response({"status": "activated", "account_id": str(updated.id)})

# ================= INVOICES =================
class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Invoice.objects.none()
        user = self.request.user
        qs = Invoice.objects.select_related("tenancy__tenant", "tenancy__target_property")
        if user.is_staff:
            return qs.order_by("-created_at")
        return qs.filter(tenancy__tenant=user).order_by("-created_at")

# ================= PAYMENTS & FINANCIAL HISTORY =================
class PaymentHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Payment.objects.none()
        user = self.request.user
        qs = Payment.objects.select_related("payer")
        if user.is_staff:
            return qs.order_by("-paid_at")
        return qs.filter(payer=user).order_by("-paid_at")

class FinancialDashboardView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Aggregates arrears & balance data for tenant/owner dashboards."""
    serializer_class = ArrearsSerializer  # ✅ Added for schema compliance
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    
    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return TenantBalance.objects.none()
        return TenantBalance.objects.none()

    @extend_schema(responses={200: OpenApiResponse(description="Financial dashboard summary")})
    def list(self, request, *args, **kwargs):
        tenancy_id = request.query_params.get("tenancy_id")
        if not tenancy_id:
            return Response({"error": "tenancy_id required"}, status=status.HTTP_400_BAD_REQUEST)

        arrears = ArrearsService.get_arrears_summary(tenancy_id)
        try:
            balance = TenantBalance.objects.get(tenancy_id=tenancy_id)
        except TenantBalance.DoesNotExist:
            balance = None

        return Response({
            "arrears": ArrearsSerializer(arrears).data if arrears else None,
            "balance": TenantBalanceSerializer(balance).data if balance else None
        })

# ================= FINANCIAL ACTIONS =================
class FinancialActionView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, CanTriggerPaymentRequest]

    @extend_schema(request=STKRequestSerializer, responses={200: OpenApiResponse(description="STK Push initiated")})
    @action(detail=False, methods=["post"])
    def request_stk_push(self, request):
        serializer = STKRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PaymentStkOrchestrator.request_payment(
            tenancy=None,
            phone=serializer.validated_data["phone"],
            amount=serializer.validated_data["amount"],
            invoice_ref=str(serializer.validated_data["invoice_id"])
        )
        return Response(result)

    @extend_schema(request=WaiverRequestSerializer, responses={200: OpenApiResponse(description="Waiver applied successfully")})
    @action(detail=False, methods=["post"])
    def apply_waiver(self, request):
        self.permission_classes = [IsAuthenticated, CanApproveFinancialOverride]
        self.check_permissions(request)
        serializer = WaiverRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = WaiverService.apply_waiver(
            invoice_id=str(serializer.validated_data["invoice_id"]),
            amount=serializer.validated_data["amount"],
            reason=serializer.validated_data["reason"],
            approved_by_user=request.user
        )
        return Response(result)

    @extend_schema(request=RefundRequestSerializer, responses={201: OpenApiResponse(description="Refund requested successfully")})
    @action(detail=False, methods=["post"])
    def request_refund(self, request):
        self.permission_classes = [IsAuthenticated, CanApproveFinancialOverride]
        self.check_permissions(request)
        serializer = RefundRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        refund = RefundService.create_refund_request(
            tenancy=None,
            amount=serializer.validated_data["amount"],
            reason=serializer.validated_data["reason"],
            requested_by_user=request.user
        )
        return Response({"status": "requested", "refund_id": str(refund.id)})

# ================= RECEIPTS =================
class ReceiptDownloadSerializer(serializers.Serializer):
    """Explicitly named serializer for OpenAPI compliance"""
    download_url = serializers.URLField(help_text="Secure presigned download link")
    expires_at = serializers.DateTimeField(help_text="URL expiration timestamp")

class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReceiptDownloadSerializer  # ✅ Named class
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Receipt.objects.none()
        return Receipt.objects.none()  # Fetched dynamically via action

    @extend_schema(responses={200: ReceiptDownloadSerializer})
    @action(detail=True, methods=["get"])
    def download(self, request, id=None):
        receipt_data = ReceiptService.get_receipt_data(id)
        if not receipt_data:
            return Response({"error": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(receipt_data)