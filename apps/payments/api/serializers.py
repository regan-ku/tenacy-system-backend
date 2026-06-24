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
            "verification_status",  # ✅ ADDED: Now visible to frontend
            "created_at"
        ]
        # ✅ ADDED: Prevent frontend from manually changing verification status
        read_only_fields = ["is_verified", "is_active", "verification_status", "created_at"] 


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ["item_type", "description", "amount", "quantity", "unit_price", "is_taxable"]


class InvoiceSerializer(serializers.ModelSerializer):
    line_items = InvoiceItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "period_start", "period_end", "due_date", 
            "total_amount", "amount_paid", "balance_due", "status", "status_display", 
            "line_items", "created_at"
        ]
        read_only_fields = ["invoice_number", "amount_paid", "balance_due", "status", "created_at"]


class PaymentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            "id", "payment_id", "amount", "source", "source_display", 
            "status", "status_display", "account_received_at", "paid_at", "created_at"
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


class WaiverRequestSerializer(serializers.Serializer):
    invoice_id = serializers.UUIDField(help_text="ID of the invoice to apply waiver to")
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('0.01'),  # ✅ STRICTLY DECIMAL TYPE
        help_text="Waiver amount in KES"
    )
    reason = serializers.CharField(max_length=500, help_text="Justification for the financial waiver")


class RefundRequestSerializer(serializers.Serializer):
    tenancy_id = serializers.UUIDField(help_text="ID of the tenancy requesting refund")
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('0.01'),  # ✅ STRICTLY DECIMAL TYPE
        help_text="Refund amount in KES"
    )
    reason = serializers.CharField(max_length=500, help_text="Detailed reason for the refund request")


class STKRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(
        max_length=20, help_text="Format: 2547XXXXXXXX or 2541XXXXXXXX"
    )
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('0.01'),  # ✅ STRICTLY DECIMAL TYPE
        help_text="Amount to charge in KES"
    )
    invoice_id = serializers.UUIDField(
        help_text="Invoice reference for payment routing & reconciliation"
    )