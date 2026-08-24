from decimal import Decimal
from rest_framework import serializers
from ..models import (
    PaymentAccount, PaymentAccountVerification, Invoice, InvoiceItem,
    Payment, PaymentAllocation, Arrears, Waiver, Refund, Receipt, TenantBalance
)


# ================= SETTLEMENT ACCOUNTS =================
class PaymentAccountSerializer(serializers.ModelSerializer):
    """
    PLATFORM SETTLEMENT MODEL:
    Serializes the landlord/agency accounts used for platform payouts.
    Verification and Active status are strictly read-only and managed
    by the backend verification service.
    """
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    verification_status_display = serializers.SerializerMethodField()

    class Meta:
        model = PaymentAccount
        fields = [
            "id",
            "property",                    # ✅ Added: links account to specific property (or null for global)
            "account_type",
            "account_type_display",
            "account_name",
            "paybill_number",
            "till_number",
            "phone_number",
            "is_default",
            "is_active",
            "is_verified",
            "verification_status",
            "verification_status_display",
            "verified_at",                 # ✅ Added: audit visibility
            "created_at",
        ]
        # ✅ CRITICAL: Landlords cannot manually set their account to verified or active.
        read_only_fields = [
            "is_verified",
            "is_active",
            "verification_status",
            "verified_at",
            "created_at",
        ]

    def get_verification_status_display(self, obj):
        status_map = {
            "pending": "Pending Verification",
            "verified": "Verified",
            "rejected": "Rejected",
            "suspended": "Suspended",
        }
        return status_map.get(obj.verification_status, obj.verification_status)


class PaymentAccountVerificationSerializer(serializers.ModelSerializer):
    """
    Exposes verification lifecycle details for audit and admin review.
    """
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    requested_by_email = serializers.CharField(source="requested_by.email", read_only=True, default=None)
    verified_by_email = serializers.CharField(source="verified_by.email", read_only=True, default=None)

    class Meta:
        model = PaymentAccountVerification
        fields = [
            "id",
            "payment_account",
            "method",
            "status",
            "status_display",
            "reference",
            "notes",
            "requested_by",
            "requested_by_email",
            "verified_by",
            "verified_by_email",
            "verified_at",
            "created_at",
        ]
        read_only_fields = fields


# ================= INVOICES =================
class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ["item_type", "description", "amount", "quantity", "unit_price", "is_taxable"]


class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    amount_waived = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "period_start", "period_end", "due_date",
            "total_amount", "amount_paid", "balance_due", "amount_waived",
            "status", "status_display", "line_items", "created_at"
        ]
        read_only_fields = ["invoice_number", "amount_paid", "balance_due", "status", "created_at"]

    def get_amount_waived(self, obj):
        return float(sum(w.amount for w in obj.financial_waivers.all()))


# ================= PAYMENTS =================
class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, default=None)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "amount", "allocation_type", "invoice_number"]


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    tenancy_id = serializers.UUIDField(source="tenancy.id", read_only=True, default=None)  # ✅ Added

    class Meta:
        model = Payment
        fields = [
            "id", "payment_id", "amount", "source", "source_display",
            "status", "status_display", "account_received_at", "account_reference",
            "tenancy", "tenancy_id",  # ✅ Added tenancy fields
            "paid_at", "allocations", "created_at"
        ]
        read_only_fields = ["payment_id", "status", "paid_at", "created_at"]


# ================= FINANCIAL SUMMARIES =================
class ArrearsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Arrears
        fields = ["id", "total_outstanding", "oldest_overdue_date", "days_overdue", "status", "last_updated"]
        read_only_fields = ["last_updated"]


class TenantBalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantBalance
        fields = ["id", "total_paid", "total_invoiced", "current_balance", "last_updated"]
        read_only_fields = ["last_updated"]


# ================= WAIVERS =================
class WaiverHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Waiver
        fields = ['id', 'tenancy', 'invoice', 'amount', 'reason', 'approved_by', 'created_at']


class WaiverRequestSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField(help_text="ID of the invoice to apply waiver to")
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=500)


# ================= REFUNDS =================
class RefundRequestSerializer(serializers.Serializer):
    tenancy_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=500)


# ================= STK PUSH (PLATFORM COLLECTION) =================
class STKRequestSerializer(serializers.Serializer):
    """
    PLATFORM COLLECTION MODEL:
    Tenant pays the Platform's global Paybill. The platform then settles
    with the landlord/agency via B2C payout to their verified account.
    """
    phone = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    tenancy_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if not data.get("invoice_id") and not data.get("tenancy_id"):
            raise serializers.ValidationError(
                "Either invoice_id or tenancy_id must be provided."
            )
        return data


# ================= MANUAL RECONCILIATION =================
class ManualReconciliationSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField(help_text="The invoice this manual payment should be allocated to")
    notes = serializers.CharField(required=False, allow_blank=True, help_text="Optional manager notes")