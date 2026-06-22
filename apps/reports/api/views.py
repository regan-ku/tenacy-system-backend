from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from ..models import Report, ReportSchedule, Dashboard
from ..permissions.reports_permissions import (
    CanViewDashboard,
    CanGenerateReport,
    CanManageReportSchedules,
    CanExportData
)
from . import serializers
from ..dashboards.builders import (
    AdminDashboardBuilder,
    LandlordDashboardBuilder,
    AgencyDashboardBuilder,
    AgentDashboardBuilder,
    CaretakerDashboardBuilder,
    TenantDashboardBuilder
)

DASHBOARD_BUILDERS = {
    'admin': AdminDashboardBuilder,
    'landlord': LandlordDashboardBuilder,
    'agency': AgencyDashboardBuilder,
    'agent': AgentDashboardBuilder,
    'caretaker': CaretakerDashboardBuilder,
    'tenant': TenantDashboardBuilder,
}


@extend_schema_view(
    retrieve=extend_schema(
        summary="Get Role-Based Dashboard",
        description="Fetches the dynamically assembled dashboard payload for the requesting user's role.",
        responses={200: serializers.DashboardRequestSerializer}
    )
)
class DashboardViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.DashboardRequestSerializer
    permission_classes = [permissions.IsAuthenticated, CanViewDashboard]
    
    # ✅ FIX: Provide a dummy queryset so Spectacular can derive the model type without crashing
    queryset = Dashboard.objects.none()

    @extend_schema(responses={200: serializers.DashboardRequestSerializer})
    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        dashboard_data = serializer.save()
        return Response(dashboard_data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(summary="List Report Requests", description="View status of all report generation requests."),
    retrieve=extend_schema(summary="Get Report Details", description="View detailed status, parameters, and download URL of a specific report."),
    create=extend_schema(
        summary="Generate New Report",
        description="Triggers an asynchronous report generation job. Returns the report ID to poll for status.",
        request=serializers.ReportGenerationRequestSerializer,
        responses={201: serializers.ReportStatusSerializer}
    )
)
class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ReportStatusSerializer
    permission_classes = [permissions.IsAuthenticated, CanGenerateReport]

    def get_queryset(self):
        # ✅ FIX: Prevent drf-spectacular from crashing during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Report.objects.none()
            
        if not self.request.user.is_authenticated:
            return Report.objects.none()
            
        user = self.request.user
        if user.role == 'admin':
            return Report.objects.all().order_by('-created_at')
        return Report.objects.filter(generated_by=user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(generated_by=self.request.user)

    @extend_schema(
        summary="Download Report Export",
        description="Redirects to or serves the generated PDF/Excel file for a completed report.",
        responses={
            200: OpenApiResponse(description="File download initiated"), 
            404: OpenApiResponse(description="Report not found or not completed") # ✅ FIX: Explicit OpenApiResponse
        }
    )
    @action(detail=True, methods=['GET'], permission_classes=[CanExportData])
    def download(self, request, pk=None):
        report = self.get_object()
        if report.status != Report.Status.COMPLETED or not report.file_url:
            return Response(
                {"error": "Report is not ready for download or generation failed."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"download_url": report.file_url}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(summary="List Scheduled Reports", description="View all recurring report schedules created by the user."),
    retrieve=extend_schema(summary="Get Schedule Details", description="View details of a specific report schedule."),
    create=extend_schema(summary="Create Schedule", description="Set up a new recurring report generation schedule.", request=serializers.ReportScheduleSerializer),
    update=extend_schema(summary="Update Schedule", description="Modify an existing report schedule.", request=serializers.ReportScheduleSerializer),
    destroy=extend_schema(summary="Delete Schedule", description="Cancel and delete a recurring report schedule.")
)
class ReportScheduleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing recurring report schedules.
    STRICTLY ENFORCED: Uses CanManageReportSchedules to ensure users can only 
    manage schedules they created (or admins can manage all).
    """
    serializer_class = serializers.ReportScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, CanManageReportSchedules]

    def get_queryset(self):
        # ✅ FIX: Prevent drf-spectacular from crashing during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return ReportSchedule.objects.none()
            
        if not self.request.user.is_authenticated:
            return ReportSchedule.objects.none()
            
        user = self.request.user
        if user.role == 'admin':
            return ReportSchedule.objects.all().order_by('-next_run_at')
        return ReportSchedule.objects.filter(created_by=user).order_by('-next_run_at')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)