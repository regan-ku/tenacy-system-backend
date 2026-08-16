from rest_framework import serializers, viewsets, mixins, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import (
    PaymentAccountSerializer, InvoiceSerializer, PaymentSerializer, 
    ArrearsSerializer, TenantBalanceSerializer, WaiverRequestSerializer,
    RefundRequestSerializer, STKRequestSerializer, ManualReconciliationSerializer, 
    WaiverHistorySerializer,
)
# ✅ FIX: Changed 'waiver' to 'Waiver' (capital W)
from ..models import PaymentAccount, PaymentAccountVerification, Invoice, Payment, Arrears, TenantBalance, Receipt, Waiver
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
from ..services.reconciliation_service import ReconciliationService
from ..integrations.stk_push_service import PaymentStkOrchestrator

# ================= PAYMENT ACCOUNTS =================
class PaymentAccountViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentAccountSerializer
    permission_classes = [IsAuthenticated, CanManagePaymentAccounts]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return PaymentAccount.objects.none()
        user = self.request.user
        qs = PaymentAccount.objects.filter(owner=user)
        if getattr(user, 'role', None) == 'admin': qs = PaymentAccount.objects.all()
        return qs.order_by("-is_default", "-is_verified", "-created_at")

    def perform_create(self, serializer):
        account = serializer.save(owner=self.request.user)
        PaymentAccountVerification.objects.create(
            payment_account=account, requested_by=self.request.user, method="manual_review", status="pending"
        )

    @extend_schema(responses={200: OpenApiResponse(description="Verification initiated")})
    @action(detail=True, methods=["post"])
    def request_verification(self, request, id=None):
        account = self.get_object()
        ver = PaymentVerificationService.initiate_verification(str(account.id), request.user.id)
        return Response({"status": "initiated", "verification_id": str(ver.id)})

    @extend_schema(responses={200: OpenApiResponse(description="Account activated")})
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
        
        qs = Invoice.objects.select_related(
            "tenancy__tenant", "tenancy__property", "tenancy__unit"
        ).prefetch_related("line_items", "financial_waivers")
        
        role = getattr(user, 'role', 'tenant')
        if role == 'admin': pass
        elif role == 'tenant': qs = qs.filter(tenancy__tenant=user)
        elif role == 'landlord': qs = qs.filter(tenancy__property__created_by=user)
        elif role in ['agency', 'manager', 'agent']: qs = qs.filter(tenancy__property__current_manager=user)
        else: qs = qs.none()
            
        return qs.order_by("-created_at")

    @extend_schema(responses={200: OpenApiResponse(description="Tenant invoice summary for KPIs")})
    @action(detail=False, methods=["get"], url_path="my-summary")
    def my_summary(self, request):
        user = request.user
        invoices = Invoice.objects.filter(tenancy__tenant=user)
        total_due = invoices.filter(status__in=["pending", "partial", "overdue"]).aggregate(Sum("balance_due"))["balance_due__sum"] or 0
        overdue_count = invoices.filter(status="overdue").count()
        
        return Response({
            "total_outstanding": float(total_due),
            "overdue_invoices_count": overdue_count
        })

# ================= PAYMENTS & FINANCIAL HISTORY =================
class PaymentHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Payment.objects.none()
        user = self.request.user
        qs = Payment.objects.select_related("payer").prefetch_related("allocations__invoice__tenancy__property")
        
        role = getattr(user, 'role', 'tenant')
        if role == 'admin': pass
        elif role == 'tenant': qs = qs.filter(payer=user)
        elif role == 'landlord': qs = qs.filter(allocations__invoice__tenancy__property__created_by=user).distinct()
        elif role in ['agency', 'manager', 'agent']: qs = qs.filter(allocations__invoice__tenancy__property__current_manager=user).distinct()
        else: qs = qs.none()
            
        return qs.order_by("-paid_at")

class FinancialDashboardView(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = ArrearsSerializer
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    
    def get_queryset(self):
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

# ================= TENANT PAYMENT PROFILE =================
class TenantPaymentProfileView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiResponse(description="Tenant payment preferences")})
    @action(detail=False, methods=["get"], url_path="preferences")
    def preferences(self, request):
        user = request.user
        last_payment = Payment.objects.filter(payer=user, status__in=["success", "completed"]).order_by("-paid_at").first()
        preferred_phone = getattr(last_payment, 'payer_phone', None) or getattr(user, 'phone_number', '')
        return Response({"preferred_phone": preferred_phone or ""})

# ================= FINANCIAL ACTIONS =================
class FinancialActionView(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, CanTriggerPaymentRequest]

    @extend_schema(request=STKRequestSerializer, responses={200: OpenApiResponse(description="STK Push initiated")})
    @action(detail=False, methods=["post"], url_path="stk-push")
    def request_stk_push(self, request):
        serializer = STKRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        invoice_id = serializer.validated_data.get("invoice_id")
        tenancy_id = serializer.validated_data.get("tenancy_id")
        
        tenancy = None
        invoice_ref = None
        
        # ✅ FIX: Resolve tenancy from invoice OR direct tenancy_id (Pay Early fallback)
        if invoice_id:
            invoice = Invoice.objects.filter(id=invoice_id).first()
            if invoice:
                tenancy = invoice.tenancy
                invoice_ref = str(invoice.id)
        elif tenancy_id:
            from apps.tenancy.models import Tenancy
            tenancy = Tenancy.objects.filter(id=tenancy_id).first()
            
        if not tenancy:
            return Response({"error": "Valid tenancy or invoice reference is required."}, status=status.HTTP_400_BAD_REQUEST)

        result = PaymentStkOrchestrator.request_payment(
            tenancy=tenancy,
            phone=serializer.validated_data["phone"],
            amount=serializer.validated_data["amount"],
            invoice_ref=invoice_ref
        )
        return Response(result)

    @extend_schema(request=WaiverRequestSerializer, responses={200: OpenApiResponse(description="Waiver applied")})
    @action(detail=False, methods=["post"], url_path="waiver")
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

    @extend_schema(request=RefundRequestSerializer, responses={201: OpenApiResponse(description="Refund requested")})
    @action(detail=False, methods=["post"], url_path="refund")
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

# ================= MANUAL RECONCILIATION =================
class ManualReconciliationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, CanReconcileTransactions]
    lookup_field = "pk"

    @extend_schema(request=ManualReconciliationSerializer, responses={200: OpenApiResponse(description="Payment reconciled")})
    @action(detail=True, methods=["post"], url_path="reconcile")
    def reconcile(self, request, pk=None):
        serializer = ManualReconciliationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        result = ReconciliationService.match_payment_to_invoice(
            payment_id=str(pk),
            invoice_id=str(serializer.validated_data["invoice_id"]),
            notes=serializer.validated_data.get("notes", "")
        )
        return Response({"status": "reconciled", "reconciliation_id": str(result.id)})

# ================= WAIVER HISTORY =================
class WaiverHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WaiverHistorySerializer
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Waiver.objects.none()
        user = self.request.user
        role = getattr(user, 'role', 'tenant')
        
        qs = Waiver.objects.select_related('tenancy', 'invoice')
        
        if role == 'tenant':
            return qs.filter(tenancy__tenant=user).order_by("-created_at")
        elif role == 'landlord':
            return qs.filter(tenancy__property__created_by=user).order_by("-created_at")
        elif role in ['agency', 'manager', 'agent']:
            return qs.filter(tenancy__property__current_manager=user).order_by("-created_at")
        return qs.none()

# ================= RECEIPTS =================
class ReceiptDownloadSerializer(serializers.Serializer):
    download_url = serializers.URLField()
    expires_at = serializers.DateTimeField()

class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReceiptDownloadSerializer
    permission_classes = [IsAuthenticated, IsFinancialStakeholder]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False): return Receipt.objects.none()
        return Receipt.objects.none()

    @extend_schema(responses={200: ReceiptDownloadSerializer})
    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, id=None):
        receipt_data = ReceiptService.get_receipt_data(id)
        if not receipt_data:
            return Response({"error": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(receipt_data)