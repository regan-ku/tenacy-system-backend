
from django.contrib import admin
from .models import IntegrationLog, MessageLog, WebhookEvent, PaymentTransaction, Campaign

@admin.register(IntegrationLog)
class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ("id_short", "provider", "endpoint", "status", "status_code", "retry_count", "created_at")
    list_filter = ("provider", "status", "created_at")
    search_fields = ("endpoint",)
    readonly_fields = ("id", "request_payload", "response_payload", "created_at")

    def id_short(self, obj): return str(obj.id)[:8]

@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ("id_short", "recipient", "channel", "status", "delivered_at", "created_at")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("recipient__email", "external_ref")
    readonly_fields = ("id", "message_content", "sent_at", "delivered_at", "created_at")

    def id_short(self, obj): return str(obj.id)[:8]

@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("id_short", "source", "event_type", "processed", "processed_at", "created_at")
    list_filter = ("source", "processed", "event_type", "created_at")
    search_fields = ("source", "event_type")
    readonly_fields = ("id", "payload", "created_at", "processed_at")

    def id_short(self, obj): return str(obj.id)[:8]

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id_short", "transaction_id", "user", "amount", "currency", "status", "reference", "created_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("transaction_id", "reference", "phone_number")
    readonly_fields = ("id", "provider_response", "created_at", "completed_at")

    def id_short(self, obj): return str(obj.id)[:8]

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "channel", "status", "total_sent", "total_delivered", "scheduled_at", "created_at")
    list_filter = ("channel", "status", "created_at")
    search_fields = ("title", "created_by__email")
    readonly_fields = ("id", "total_sent", "total_delivered", "created_at")