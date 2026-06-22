from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from django.contrib.auth import get_user_model

from . import serializers
from ..models import Tenancy, Occupancy, TenancyNote, TenancyWaiver
from ..services import NotesService, HistoryService
from ..permissions.tenancy_permissions import (
    IsTenantOfUnit, IsPropertyManagerOrOwner, CanApproveTenancyActions
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(summary="List Tenancies"),
    retrieve=extend_schema(summary="Get Tenancy Details"),
    create=extend_schema(summary="Create Tenancy"),
)
class TenancyViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TenancySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Tenancy.objects.none()
            
        if not self.request.user.is_authenticated:
            return Tenancy.objects.none()
            
        user = self.request.user
        if user.role == 'admin':
            return Tenancy.objects.all().select_related('tenant', 'unit', 'property')
        if user.role == 'tenant':
            return Tenancy.objects.filter(tenant=user).select_related('unit', 'property')
        return Tenancy.objects.filter(
            property__created_by=user
        ) | Tenancy.objects.filter(
            property__current_manager=user
        ).select_related('tenant', 'unit', 'property').distinct()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated]
        if self.action in ['create', 'activate', 'add_note', 'transfer', 'extend', 'terminate']:
            return [CanApproveTenancyActions]
        return [IsPropertyManagerOrOwner]

    @extend_schema(request=serializers.TenancyActivationSerializer, responses={200: serializers.TenancySerializer})
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def activate(self, request, pk=None):
        tenancy = self.get_object()
        serializer = serializers.TenancyActivationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        updated_tenancy = serializer.update(tenancy, serializer.validated_data)
        return Response(self.get_serializer(updated_tenancy).data, status=status.HTTP_200_OK)

    @extend_schema(request=serializers.TenancyNoteSerializer, responses={201: serializers.TenancyNoteSerializer})
    @action(detail=True, methods=['POST'], permission_classes=[permissions.IsAuthenticated])
    def add_note(self, request, pk=None):
        tenancy = self.get_object()
        serializer = serializers.TenancyNoteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        note = NotesService.create_note(
            tenancy=tenancy, user=request.user, content=serializer.validated_data['content'],
            note_type=serializer.validated_data.get('note_type', 'general'),
            is_confidential=serializer.validated_data.get('is_confidential', False)
        )
        return Response(serializers.TenancyNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=serializers.TenancyTransferSerializer, responses={201: OpenApiResponse(description="Transfer initiated")})
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def transfer(self, request, pk=None):
        tenancy = self.get_object()
        serializer = serializers.TenancyTransferSerializer(data=request.data, context={'request': request, 'tenancy': tenancy})
        serializer.is_valid(raise_exception=True)
        transfer = serializer.save()
        return Response({"detail": "Transfer request created successfully.", "transfer_id": transfer.id}, status=status.HTTP_201_CREATED)

    @extend_schema(request=serializers.TenancyExtensionSerializer, responses={201: OpenApiResponse(description="Extension initiated")})
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def extend(self, request, pk=None):
        tenancy = self.get_object()
        serializer = serializers.TenancyExtensionSerializer(data=request.data, context={'request': request, 'tenancy': tenancy})
        serializer.is_valid(raise_exception=True)
        extension = serializer.save()
        return Response({"detail": "Extension request created successfully.", "extension_id": extension.id}, status=status.HTTP_201_CREATED)

    @extend_schema(request=serializers.TenancyTerminationSerializer, responses={200: OpenApiResponse(description="Tenancy terminated")})
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def terminate(self, request, pk=None):
        tenancy = self.get_object()
        serializer = serializers.TenancyTerminationSerializer(data=request.data, context={'request': request, 'tenancy': tenancy})
        serializer.is_valid(raise_exception=True)
        termination = serializer.save()
        return Response({"detail": "Tenancy terminated successfully.", "termination_id": termination.id}, status=status.HTTP_200_OK)


class OccupancyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.OccupancySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Occupancy.objects.none()
        return Occupancy.objects.filter(
            unit__property__is_active=True
        ).select_related('unit', 'current_tenant', 'active_tenancy')


class TenancyNoteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.TenancyNoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TenancyNote.objects.none()
        if not self.request.user.is_authenticated:
            return TenancyNote.objects.none()
            
        user = self.request.user
        if user.role == 'admin':
            return TenancyNote.objects.all().select_related('created_by')
        return TenancyNote.objects.filter(
            tenancy__tenant=user
        ) | TenancyNote.objects.filter(
            tenancy__property__created_by=user
        ).distinct().select_related('created_by')


class TenancyWaiverViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.TenancyWaiverSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return TenancyWaiver.objects.none()
        if not self.request.user.is_authenticated:
            return TenancyWaiver.objects.none()
            
        user = self.request.user
        if user.role == 'admin':
            return TenancyWaiver.objects.all()
        return TenancyWaiver.objects.filter(tenancy__tenant=user) | TenancyWaiver.objects.filter(tenancy__property__created_by=user)


class TenantHistoryViewSet(viewsets.GenericViewSet):
    # ✅ FIX: Added dummy queryset to satisfy DRF Spectacular's requirement for GenericViewSet
    queryset = Tenancy.objects.none()
    serializer_class = serializers.TenancySerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Full Tenant History", responses={200: OpenApiResponse(description="Tenant history data")})
    @action(detail=False, methods=['GET'], url_path='history')
    def list(self, request, tenant_id=None):
        if request.user.role not in ['admin', 'landlord', 'agency'] and request.user.id != int(tenant_id):
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
            
        history = HistoryService.get_tenant_history(tenant_id)
        return Response(history, status=status.HTTP_200_OK)

    @extend_schema(summary="Get Tenant History Summary", responses={200: OpenApiResponse(description="Tenant history summary")})
    @action(detail=False, methods=['GET'], url_path='history/summary')
    def summary(self, request, tenant_id=None):
        if request.user.role not in ['admin', 'landlord', 'agency'] and request.user.id != int(tenant_id):
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
            
        summary = HistoryService.get_tenant_summary(tenant_id)
        return Response(summary, status=status.HTTP_200_OK)


class ApplicationTenantProfileView(viewsets.GenericViewSet):
    queryset = Tenancy.objects.none() # ✅ FIX: Added dummy queryset
    serializer_class = serializers.TenancySerializer # ✅ FIX: Added dummy serializer class
    permission_classes = [permissions.IsAuthenticated, CanApproveTenancyActions]

    @extend_schema(
        summary="Get Tenant Profile for Application Review",
        responses={200: OpenApiResponse(description="Tenant profile and history data")}
    )
    def retrieve(self, request, application_id=None):
        profile_data = HistoryService.get_tenant_summary_for_application_review(application_id)
        return Response(profile_data, status=status.HTTP_200_OK)