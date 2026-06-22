from django.contrib import admin
from django.utils import timezone
from .models import (
    MaintenanceCategory, MaintenanceRequest, MaintenanceAssignment,
    MaintenanceUpdate, MaintenanceMedia, MaintenanceInspection, MaintenanceHistory
)

class MaintenanceUpdateInline(admin.StackedInline):
    model = MaintenanceUpdate
    extra = 0
    readonly_fields = ("created_at",)

class MaintenanceMediaInline(admin.TabularInline):
    model = MaintenanceMedia
    extra = 0
    readonly_fields = ("created_at",)

@admin.register(MaintenanceCategory)
class MaintenanceCategoryAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "default_sla_hours", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")

@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "unit", "property", "category", "priority", "status", "assigned_to", "created_at")
    list_filter = ("status", "priority", "category", "created_at")
    search_fields = ("title", "unit__unit_code", "property__title")
    readonly_fields = ("id", "created_at", "updated_at", "resolved_at", "closed_at")
    inlines = [MaintenanceUpdateInline, MaintenanceMediaInline]
    actions = ["mark_resolved", "mark_closed"]

    def mark_resolved(self, request, queryset):
        queryset.update(status="resolved", resolved_at=timezone.now())
    mark_resolved.short_description = "Mark selected as resolved"

    def mark_closed(self, request, queryset):
        queryset.update(status="closed", closed_at=timezone.now())
    mark_closed.short_description = "Mark selected as closed"

@admin.register(MaintenanceAssignment)
class MaintenanceAssignmentAdmin(admin.ModelAdmin):
    list_display = ("request", "assigned_to", "role_type", "status", "assigned_at")
    list_filter = ("status", "role_type")
    search_fields = ("request__title", "assigned_to__email")
    readonly_fields = ("assigned_at", "acknowledged_at")

@admin.register(MaintenanceMedia)
class MaintenanceMediaAdmin(admin.ModelAdmin):
    list_display = ("request", "media_type", "is_before_after", "uploaded_by", "created_at")
    list_filter = ("media_type", "is_before_after")
    readonly_fields = ("created_at",)

@admin.register(MaintenanceInspection)
class MaintenanceInspectionAdmin(admin.ModelAdmin):
    list_display = ("property", "unit", "inspector", "inspection_date", "status", "created_at")
    list_filter = ("status", "inspection_date")
    search_fields = ("property__title", "unit__unit_code")
    readonly_fields = ("id", "findings", "created_at")
    actions = ["mark_completed", "mark_overdue"]

    def mark_completed(self, request, queryset):
        queryset.update(status="completed")
    mark_completed.short_description = "Mark selected as completed"

    def mark_overdue(self, request, queryset):
        queryset.update(status="overdue")
    mark_overdue.short_description = "Mark selected as overdue"

@admin.register(MaintenanceHistory)
class MaintenanceHistoryAdmin(admin.ModelAdmin):
    list_display = ("request", "event_type", "performed_by", "created_at")
    list_filter = ("event_type", "created_at")
    readonly_fields = ("id", "previous_value", "new_value", "ip_address", "created_at")
    search_fields = ("request__title", "event_type")