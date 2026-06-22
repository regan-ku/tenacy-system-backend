from rest_framework import serializers
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema_field

from ..models import Report, ReportSchedule, Dashboard
from ..services import (
    DashboardService,
    FinancialReportService,
    OccupancyReportService,
    TenancyReportService,
    MaintenanceReportService,
    ApplicationReportService,
    PropertyReportService,
    MarketplaceReportService,
    CommunicationReportService
)

User = get_user_model()


class DashboardRequestSerializer(serializers.Serializer):
    """
    Validates requests for dashboard data. 
    Allows admins to preview other roles, but defaults to the requesting user's role.
    """
    role = serializers.ChoiceField(
        choices=Dashboard.RoleType.choices, 
        required=False, 
        help_text="Role to preview (Admin only). Defaults to requesting user's role."
    )

    def validate_role(self, value):
        user = self.context['request'].user
        if value and user.role != 'admin':
            raise serializers.ValidationError("Only administrators can preview other roles' dashboards.")
        return value or user.role

    def create(self, validated_data):
        user = self.context['request'].user
        target_role = validated_data.get('role', user.role)
        return DashboardService.get_dashboard_data(user, role=target_role)


class ReportGenerationRequestSerializer(serializers.Serializer):
    """
    Validates requests to generate a new report.
    """
    title = serializers.CharField(max_length=255)
    report_type = serializers.ChoiceField(choices=Report.ReportType.choices)
    parameters = serializers.JSONField(
        required=False, 
        default=dict,
        help_text="Filters like start_date, end_date, property_ids, etc."
    )

    def create(self, validated_data):
        user = self.context['request'].user
        report_type = validated_data['report_type']
        title = validated_data['title']
        parameters = validated_data['parameters']

        service_map = {
            'financial': FinancialReportService.initiate_financial_report,
            'occupancy': OccupancyReportService.initiate_occupancy_report,
            'tenancy': TenancyReportService.initiate_tenancy_report,
            'maintenance': MaintenanceReportService.initiate_maintenance_report,
            'applications': ApplicationReportService.initiate_application_report,
            'property': PropertyReportService.initiate_property_report,
            'marketplace': MarketplaceReportService.initiate_marketplace_report,
            'communications': CommunicationReportService.initiate_communication_report,
        }

        service_func = service_map.get(report_type)
        if not service_func:
            raise serializers.ValidationError(f"Unsupported report type: {report_type}")

        return service_func(user, title, parameters)


class ReportStatusSerializer(serializers.ModelSerializer):
    """
    Read-only serializer to display the status, progress, and download URL of a report.
    """
    generated_by_email = serializers.EmailField(source='generated_by.email', read_only=True, allow_null=True)
    snapshot_data = serializers.SerializerMethodField(help_text="The computed data payload (if completed).")

    class Meta:
        model = Report
        fields = [
            'id', 'title', 'report_type', 'status', 'parameters', 
            'file_url', 'error_message', 'generated_by_email', 
            'created_at', 'completed_at', 'snapshot_data'
        ]
        read_only_fields = fields

    @extend_schema_field(field={"type": "object", "nullable": True})
    def get_snapshot_data(self, obj):
        if obj.status == Report.Status.COMPLETED and hasattr(obj, 'snapshot'):
            return obj.snapshot.snapshot_data
        return None


class ReportScheduleSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and managing recurring report schedules.
    """
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, allow_null=True)

    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'title', 'report_type', 'frequency', 'parameters', 
            'is_active', 'next_run_at', 'last_run_at', 'created_by_email', 'created_at'
        ]
        read_only_fields = ['created_by', 'next_run_at', 'last_run_at', 'created_at']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        freq = validated_data.get('frequency', 'monthly')
        if freq == 'daily':
            validated_data['next_run_at'] = now + timedelta(days=1)
        elif freq == 'weekly':
            validated_data['next_run_at'] = now + timedelta(weeks=1)
        else:
            validated_data['next_run_at'] = now + timedelta(days=30) # monthly fallback
            
        return super().create(validated_data)