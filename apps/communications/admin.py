from django.contrib import admin
from .models import (
    MessageEvent, MessageTemplate, Notification, Message, 
    DeliveryLog, Campaign, CampaignAudience
)

class CampaignAudienceInline(admin.TabularInline):
    model = CampaignAudience
    extra = 0
    readonly_fields = ("resolved_at", "created_at")

class DeliveryLogInline(admin.StackedInline):
    model = DeliveryLog
    extra = 0
    readonly_fields = ("attempt_number", "raw_response", "attempted_at")

@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "channel", "is_active", "required_variables", "updated_at")
    list_filter = ("channel", "is_active", "updated_at")
    search_fields = ("name",)
    readonly_fields = ("updated_at",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "type", "is_read", "created_at")
    list_filter = ("type", "is_read", "created_at")
    search_fields = ("user__email", "title")
    readonly_fields = ("created_at",)
    actions = ["mark_as_read"]

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, "Selected notifications marked as read.")
    mark_as_read.short_description = "Mark selected as read"

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id_short", "recipient", "channel", "message_type", "status", "sent_at", "delivered_at")
    list_filter = ("channel", "message_type", "status", "created_at")
    search_fields = ("recipient__email", "content")
    readonly_fields = ("id", "sent_at", "delivered_at", "created_at")
    inlines = [DeliveryLogInline]

    def id_short(self, obj): return str(obj.id)[:8]

@admin.register(DeliveryLog)
class DeliveryLogAdmin(admin.ModelAdmin):
    list_display = ("id_short", "message", "provider", "attempt_number", "status", "attempted_at")
    list_filter = ("provider", "status", "attempted_at")
    readonly_fields = ("attempt_number", "raw_response", "attempted_at")

    def id_short(self, obj): return str(obj.id)[:8]
    def message_short(self, obj): return str(obj.message.id)[:8]

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("title", "creator", "channel", "status", "total_sent", "total_delivered", "scheduled_at")
    list_filter = ("channel", "status", "scheduled_at")
    search_fields = ("title",)
    readonly_fields = ("total_sent", "total_delivered", "metrics", "created_at", "updated_at")
    inlines = [CampaignAudienceInline]

@admin.register(MessageEvent)
class MessageEventAdmin(admin.ModelAdmin):
    list_display = ("id_short", "event_type", "target_user_id", "processed", "created_at")
    list_filter = ("event_type", "processed", "created_at")
    readonly_fields = ("id", "payload", "created_at")

    def id_short(self, obj): return str(obj.id)[:8]