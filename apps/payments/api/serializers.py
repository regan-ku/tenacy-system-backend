from decimal import Decimal
from rest_framework import serializers
from ..models import (
    PaymentAccount, Invoice, InvoiceItem, Payment, PaymentAllocation,
    Arrears, Waiver, Refund, Receipt, TenantBalance
)


class PaymentAccountSerializer(serializers.ModelSerializer):
    account_type_display = serializers.CharField(source="get_account_type_display", read_only=True)
    
    class Meta:
        model = PaymentAccount
        fields = [
            "id", "account_type", "account_type_display", "account_name", 
            "paybill_number", "till_number", "phone_number", 
            "is_default", "is_active", "is_verified", 
            "verification_status", "created_at"
        ]
        read_only_fields = ["is_verified", "is_active", "verification_status", "created_at"] 


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


class PaymentAllocationSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True, default=None)
    
    class Meta:
        model = PaymentAllocation
        fields = ["id", "amount", "allocation_type", "invoice_number"]


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id", "payment_id", "amount", "source", "source_display", 
            "status", "status_display", "account_received_at", "paid_at", 
            "allocations", "created_at"
        ]
        read_only_fields = ["payment_id", "status", "paid_at", "created_at"]


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


class WaiverHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Waiver
        fields = ['id', 'tenancy', 'invoice', 'amount', 'reason', 'approved_by', 'created_at']


class WaiverRequestSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField(help_text="ID of the invoice to apply waiver to")
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=500)


class RefundRequestSerializer(serializers.Serializer):
    tenancy_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=500)


class STKRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    # ✅ FIX: Made invoice_id optional and added tenancy_id as fallback for "Pay Early"
    invoice_id = serializers.UUIDField(required=False, allow_null=True)
    tenancy_id = serializers.IntegerField(required=False, allow_null=True)


class ManualReconciliationSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField(help_text="The invoice this manual payment should be allocated to")
    notes = serializers.CharField(required=False, allow_blank=True, help_text="Optional manager notes")