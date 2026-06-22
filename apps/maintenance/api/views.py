from rest_framework import viewsets, mixins, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .serializers import (
    CategorySerializer, RequestDetailSerializer, RequestCreateSerializer,
    AssignmentSerializer, InspectionSerializer, InspectionCreateSerializer
)
from ..models import (
    MaintenanceCategory, MaintenanceRequest, MaintenanceAssignment,
    MaintenanceInspection
)
from ..permissions.maintenance_permissions import (
    IsTenantOrOwnerOfRequest, IsMaintenanceStaffOrAdmin, IsAssignedTechnicianOrAdmin
)
from ..services.request_service import RequestService
from ..services.workflow_service import WorkflowService
from ..services.assignment_service import AssignmentService
from ..services.resolution_service import ResolutionService
from ..services.inspection_service import InspectionService
from ..services.unit_history_service import UnitHistoryService

# ================= CATEGORIES =================
class CategoryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MaintenanceCategory.objects.none()
        return MaintenanceCategory.objects.filter(is_active=True)

# ================= REQUESTS =================
class RequestViewSet(viewsets.ModelViewSet):
    serializer_class = RequestDetailSerializer
    permission_classes = [permissions.IsAuthenticated, IsTenantOrOwnerOfRequest]
    lookup_field = "id"

    def get_serializer_class(self):
        return RequestCreateSerializer if self.request.method == "POST" else RequestDetailSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MaintenanceRequest.objects.none()
        user = self.request.user
        if user.is_staff:
            return MaintenanceRequest.objects.all().select_related("unit", "category", "assigned_to").order_by("-created_at")
        return MaintenanceRequest.objects.filter(created_by=user).order_by("-created_at")

    def perform_create(self, serializer):
        RequestService.create_request(
            created_by=self.request.user,
            unit_id=serializer.validated_data["unit_id"],
            title=serializer.validated_data["title"],
            description=serializer.validated_data["description"],
            category_id=serializer.validated_data["category_id"],
            priority=serializer.validated_data.get("priority")
        )

    @extend_schema(responses={200: OpenApiResponse(description="Request assigned successfully")})
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsMaintenanceStaffOrAdmin])
    def assign(self, request, id=None):
        obj = self.get_object()
        assignee_id = request.data.get("assignee_id")
        role = request.data.get("role", "caretaker")
        assignment = AssignmentService.assign_request(str(obj.id), assignee_id, request.user, role)
        return Response({"status": "assigned", "assignment": AssignmentSerializer(assignment).data})

    @extend_schema(responses={200: OpenApiResponse(description="Status updated successfully")})
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsAssignedTechnicianOrAdmin])
    def update_status(self, request, id=None):
        obj = self.get_object()
        new_status = request.data.get("status")
        comment = request.data.get("comment", "")
        WorkflowService.transition_status(str(obj.id), new_status, comment, request.user)
        return Response({"status": "updated", "new_status": new_status})

    @extend_schema(responses={200: OpenApiResponse(description="Request marked as resolved")})
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsAssignedTechnicianOrAdmin])
    def resolve(self, request, id=None):
        obj = self.get_object()
        comment = request.data.get("comment", "")
        ResolutionService.mark_resolved(str(obj.id), request.user, comment)
        return Response({"status": "resolved"})

# ================= INSPECTIONS =================
class InspectionViewSet(viewsets.ModelViewSet):
    serializer_class = InspectionSerializer
    permission_classes = [permissions.IsAuthenticated, IsMaintenanceStaffOrAdmin]
    lookup_field = "id"

    def get_serializer_class(self):
        return InspectionCreateSerializer if self.request.method == "POST" else InspectionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MaintenanceInspection.objects.none()
        return MaintenanceInspection.objects.select_related("property", "unit").order_by("-inspection_date")

    @extend_schema(responses={200: OpenApiResponse(description="Inspection completed successfully")})
    @action(detail=True, methods=["post"])
    def complete(self, request, id=None):
        obj = self.get_object()
        findings = request.data.get("findings", "")
        create_request = request.data.get("create_request", False)
        category_id = request.data.get("category_id")
        InspectionService.complete_inspection(str(obj.id), request.user, findings, create_request, category_id)
        return Response({"status": "completed"})

# ================= UNIT HISTORY =================
@extend_schema(responses={200: OpenApiResponse(description="Public maintenance history & health score")})
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def unit_maintenance_history(request, unit_id):
    """Read-only maintenance history for a unit. Used during applications & manager reviews."""
    history = UnitHistoryService.get_public_unit_history(unit_id)
    health = UnitHistoryService.get_unit_health_score(unit_id)
    return Response({
        "unit_id": unit_id,
        "health_score": health,
        "maintenance_history": history
    })