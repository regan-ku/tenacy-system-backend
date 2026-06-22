from django.contrib import admin
from .models import (
    Report, 
    ReportSnapshot, 
    ReportSchedule, 
    Dashboard, 
    DashboardWidget, 
    DashboardSnapshot,
    AnalyticsEvent
)

@admin.register(Dashboard)
class DashboardAdmin(admin.ModelAdmin):
    list_display = ('role', 'name', 'is_active', 'updated_at')
    list_filter = ('role', 'is_active')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(DashboardWidget)
class DashboardWidgetAdmin(admin.ModelAdmin):
    list_display = ('name', 'widget_type', 'data_source', 'is_active')
    list_filter = ('widget_type', 'is_active')
    search_fields = ('name', 'data_source')

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'report_type', 'status', 'generated_by', 'created_at', 'completed_at')
    list_filter = ('report_type', 'status', 'created_at')
    search_fields = ('title', 'generated_by__email')
    readonly_fields = ('file_url', 'error_message', 'created_at', 'completed_at')
    raw_id_fields = ('generated_by',)

@admin.register(ReportSnapshot)
class ReportSnapshotAdmin(admin.ModelAdmin):
    list_display = ('report', 'taken_at')
    list_filter = ('taken_at',)
    search_fields = ('report__title',)
    readonly_fields = ('snapshot_data', 'taken_at')
    raw_id_fields = ('report',)

@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('title', 'report_type', 'frequency', 'created_by', 'is_active', 'next_run_at', 'last_run_at')
    list_filter = ('report_type', 'frequency', 'is_active')
    search_fields = ('title', 'created_by__email')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('created_by',)

@admin.register(DashboardSnapshot)
class DashboardSnapshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'role_at_time', 'captured_at')
    list_filter = ('role_at_time', 'captured_at')
    search_fields = ('user__email',)
    readonly_fields = ('snapshot_data', 'captured_at')
    raw_id_fields = ('user',)

@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'timestamp')
    list_filter = ('event_type', 'timestamp')
    search_fields = ('user__email', 'metadata')
    readonly_fields = ('timestamp', 'metadata')
    raw_id_fields = ('user', 'content_type')