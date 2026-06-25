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
        # ✅ CRITICAL FIX 1: Instantiate permission classes with () to prevent TypeError
        # ✅ CRITICAL FIX 2: Added 'list_transfers' and 'list_terminations' to allowed read actions
        if self.action in ['list', 'retrieve', 'list_transfers', 'list_terminations']:
            return [permissions.IsAuthenticated()]
        if self.action in ['create', 'activate', 'add_note', 'transfer', 'extend', 'terminate']:
            return [CanApproveTenancyActions()]
        return [IsPropertyManagerOrOwner()]

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

    # ✅ FIX: Added missing @ to @extend_schema
    @extend_schema(summary="List Transfer Requests")
    @action(detail=False, methods=['GET'], url_path='transfers')
    def list_transfers(self, request):
        from ..models import TenancyTransfer
        user = request.user
        
        # ✅ CRITICAL FIX: The TenancyTransfer model uses 'requested_at', not 'created_at'.
        # Using 'created_at' in order_by() causes a fatal FieldError at the database level.
        try:
            if user.role in ['admin', 'landlord', 'agency', 'manager']:
                qs1 = TenancyTransfer.objects.filter(to_property__current_manager=user)
                qs2 = TenancyTransfer.objects.filter(to_property__created_by=user)
                transfers = (qs1 | qs2).distinct().order_by('-requested_at') # <--- FIXED
            else:
                transfers = TenancyTransfer.objects.filter(tenant=user).order_by('-requested_at') # <--- FIXED
        except Exception:
            transfers = TenancyTransfer.objects.all().order_by('-requested_at') # <--- FIXED
            
        data = []
        for t in transfers:
            try:
                tenant_name = "Unknown"
                if getattr(t, 'tenant', None):
                    profile = getattr(t.tenant, 'profile', None)
                    tenant_name = getattr(profile, 'full_name', None) or t.tenant.email or "Unknown"
                
                from_prop = getattr(t, 'from_property', None)
                to_prop = getattr(t, 'to_property', None)
                from_u = getattr(t, 'from_unit', None)
                to_u = getattr(t, 'to_unit', None)

                data.append({
                    "id": t.id,
                    "tenant_name": tenant_name,
                    "tenant_email": t.tenant.email if getattr(t, 'tenant', None) else "",
                    "from_property_title": from_prop.title if from_prop else "",
                    "from_unit_code": from_u.unit_code if from_u else "",
                    "to_property_title": to_prop.title if to_prop else "",
                    "to_unit_code": to_u.unit_code if to_u else "",
                    "reason": getattr(t, 'reason', ''),
                    # ✅ FIX: Model uses 'transfer_status'
                    "status": getattr(t, 'transfer_status', 'pending'), 
                    # ✅ FIX: Map model's 'requested_at' to frontend's expected 'submitted_at'
                    "submitted_at": getattr(t, 'requested_at', ''), 
                })
            except Exception as e:
                print(f"⚠️ Error formatting transfer {t.id}: {e}")
                continue
                
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(summary="List Termination Notices")
    @action(detail=False, methods=['GET'], url_path='terminations')
    def list_terminations(self, request):
        from ..models import TenancyTermination
        user = request.user
        
        try:
            if user.role in ['admin', 'landlord', 'agency', 'manager']:
                qs1 = TenancyTermination.objects.filter(tenancy__property__current_manager=user)
                qs2 = TenancyTermination.objects.filter(tenancy__property__created_by=user)
                terminations = (qs1 | qs2).distinct().order_by('-created_at')
            else:
                terminations = TenancyTermination.objects.filter(tenancy__tenant=user).order_by('-created_at')
        except Exception:
            terminations = TenancyTermination.objects.all().order_by('-created_at')
            
        data = []
        for term in terminations:
            try:
                tenancy = getattr(term, 'tenancy', None)
                tenant_name = "Unknown"
                tenant_email = ""
                property_title = ""
                unit_code = ""
                
                if tenancy:
                    tenant = getattr(tenancy, 'tenant', None)
                    if tenant:
                        profile = getattr(tenant, 'profile', None)
                        tenant_name = getattr(profile, 'full_name', None) or tenant.email or "Unknown"
                        tenant_email = tenant.email or ""
                    
                    prop = getattr(tenancy, 'property', None)
                    property_title = prop.title if prop else ""
                    
                    u = getattr(tenancy, 'unit', None)
                    unit_code = u.unit_code if u else ""

                data.append({
                    "id": term.id,
                    "tenant_name": tenant_name,
                    "tenant_email": tenant_email,
                    "property_title": property_title,
                    "unit_code": unit_code,
                    "termination_type": getattr(term, 'termination_type', 'tenant_request'),
                    "intended_vacate_date": str(getattr(term, 'intended_vacate_date', '')) if getattr(term, 'intended_vacate_date', None) else "",
                    "status": getattr(term, 'status', 'pending_review'),
                    "notes": getattr(term, 'notes', ''),
                    "created_at": getattr(term, 'created_at', ''),
                })
            except Exception as e:
                print(f"⚠️ Error formatting termination {term.id}: {e}")
                continue
                
        return Response(data, status=status.HTTP_200_OK)


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
    queryset = Tenancy.objects.none()
    serializer_class = serializers.TenancySerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Tenant History Summary", responses={200: OpenApiResponse(description="Tenant history summary")})
    @action(detail=True, methods=['GET'], url_path='history')
    def history(self, request, pk=None):
        tenant_id = pk 
        if request.user.role not in ['admin', 'landlord', 'agency'] and request.user.id != int(tenant_id):
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        summary = HistoryService.get_tenant_history_summary(tenant_id)
        return Response(summary, status=status.HTTP_200_OK)

    @extend_schema(summary="Get Tenant History Summary (Alias)", responses={200: OpenApiResponse(description="Tenant history summary")})
    @action(detail=True, methods=['GET'], url_path='history/summary')
    def summary(self, request, pk=None):
        tenant_id = pk
        if request.user.role not in ['admin', 'landlord', 'agency'] and request.user.id != int(tenant_id):
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        summary = HistoryService.get_tenant_history_summary(tenant_id)
        return Response(summary, status=status.HTTP_200_OK)


class ApplicationTenantProfileView(viewsets.GenericViewSet):
    queryset = Tenancy.objects.none()
    serializer_class = serializers.TenancySerializer
    permission_classes = [permissions.IsAuthenticated, CanApproveTenancyActions]

    @extend_schema(
        summary="Get Tenant Profile for Application Review",
        responses={200: OpenApiResponse(description="Tenant profile and history data")}
    )
    def retrieve(self, request, application_id=None):
        profile_data = HistoryService.get_tenant_summary_for_application_review(application_id)
        return Response(profile_data, status=status.HTTP_200_OK)