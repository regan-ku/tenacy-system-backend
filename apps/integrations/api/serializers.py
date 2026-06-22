from decimal import Decimal  # ✅ ADDED IMPORT
from rest_framework import serializers
from ..models import PaymentTransaction, MessageLog, IntegrationLog, Campaign


class PaymentTransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    class Meta:
        model = PaymentTransaction
        fields = ["id", "transaction_id", "amount", "currency", "phone_number", "status", "status_display", "reference", "created_at"]
        read_only_fields = ["id", "transaction_id", "status", "created_at"]


class MessageLogSerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source="get_channel_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    class Meta:
        model = MessageLog
        fields = ["id", "recipient", "channel", "channel_display", "message_type", "status", "status_display", "external_ref", "sent_at", "delivered_at"]
        read_only_fields = ["id", "status", "sent_at", "delivered_at"]


class IntegrationLogSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    class Meta:
        model = IntegrationLog
        fields = ["id", "provider", "endpoint", "status", "status_display", "status_code", "retry_count", "created_at"]
        read_only_fields = fields


# ✅ Renamed to prevent OpenAPI schema collision with communications.CampaignSerializer
class IntegrationCampaignSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    channel_display = serializers.CharField(source="get_channel_display", read_only=True)
    
    class Meta:
        model = Campaign
        fields = ["id", "title", "message_template", "channel", "channel_display", "target_audience", "status", "status_display", "scheduled_at", "total_sent", "total_delivered", "created_at"]
        read_only_fields = ["id", "status", "total_sent", "total_delivered", "created_at"]


class IntegrationCampaignCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campaign
        fields = ["id", "title", "message_template", "channel", "target_audience", "scheduled_at"]
        read_only_fields = ["id"]


class StkPushRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(
        max_length=15, 
        help_text="Format: 2547XXXXXXXX or 2541XXXXXXXX"
    )
    amount = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=Decimal('1.00'),  # ✅ FIXED: Use Decimal type for min_value to satisfy strict type checkers
        help_text="Amount in KES"
    )
    account_ref = serializers.CharField(
        max_length=50,
        help_text="Invoice ID, Tenancy ID, or Payment Reference"
    )
    transaction_desc = serializers.CharField(
        max_length=100, required=False, default="Property Platform Payment"
    )


class SmsDispatchRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    message = serializers.CharField(max_length=160)
    sender_id = serializers.CharField(max_length=11, required=False, help_text="Max 11 chars, alphanumeric")


class WhatsAppDispatchRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=15)
    template_name = serializers.CharField(required=False, help_text="WhatsApp Cloud API template name")
    text = serializers.CharField(required=False, help_text="Raw text if not using template")
    language_code = serializers.CharField(default="en", required=False)

    def validate(self, data):
        if not data.get("template_name") and not data.get("text"):
            raise serializers.ValidationError("Either template_name or text must be provided.")
        return data