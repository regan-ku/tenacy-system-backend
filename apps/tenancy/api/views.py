from decimal import Decimal
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse
from django.utils import timezone

from django.contrib.auth import get_user_model

from . import serializers
from ..models import Tenancy, Occupancy, TenancyNote, TenancyWaiver, TenancyTransfer, TenancyExtension, TenancyTermination
from ..services import NotesService, HistoryService
from ..permissions.tenancy_permissions import (
    IsTenantOfUnit, IsPropertyManagerOrOwner, CanApproveTenancyActions
)
from apps.applications.models import Application # ✅ Added for unified cancel actions

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
        
        return (
            Tenancy.objects.filter(property__created_by=user) | 
            Tenancy.objects.filter(property__current_manager=user)
        ).select_related('tenant', 'unit', 'property').distinct()

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'list_transfers', 'list_terminations', 'list_notes']:
            return [permissions.IsAuthenticated()]
        # ✅ UPDATED: Added settlement_preview and finalize_settlement to manager-only actions
        if self.action in ['create', 'activate', 'add_note', 'transfer', 'extend', 'terminate', 
                           'decide_transfer', 'decide_termination', 'decide_extension',
                           'cancel_transfer', 'cancel_extension', 'cancel_termination',
                           'settlement_preview', 'finalize_settlement']:
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

    @extend_schema(summary="List Notes for a Tenancy")
    @action(detail=True, methods=['GET'], url_path='notes', permission_classes=[permissions.IsAuthenticated])
    def list_notes(self, request, pk=None):
        tenancy = self.get_object()
        notes = TenancyNote.objects.filter(tenancy=tenancy).order_by('-created_at')
        serializer = serializers.TenancyNoteSerializer(notes, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

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
        return Response({"detail": "Tenancy termination request created successfully.", "termination_id": termination.id}, status=status.HTTP_200_OK)

    @extend_schema(summary="Decide on Transfer Request")
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def decide_transfer(self, request, pk=None):
        tenancy = self.get_object()
        decision = request.data.get('decision')
        reason = request.data.get('reason', '')
        
        transfer = TenancyTransfer.objects.filter(tenant=tenancy.tenant, from_unit=tenancy.unit, transfer_status='pending').first()
        if not transfer:
            return Response({"error": "No pending transfer found."}, status=status.HTTP_404_NOT_FOUND)
        
        if decision == 'approved':
            transfer.transfer_status = 'approved'
            transfer.approved_by = request.user
            transfer.processed_at = timezone.now()
            transfer.save()
            return Response({"detail": "Transfer approved.", "transfer_id": transfer.id}, status=status.HTTP_200_OK)
        elif decision == 'rejected':
            transfer.transfer_status = 'rejected'
            transfer.approved_by = request.user
            transfer.processed_at = timezone.now()
            transfer.save()
            return Response({"detail": "Transfer rejected."}, status=status.HTTP_200_OK)
        
        return Response({"error": "Invalid decision."}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Decide on Termination Request")
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def decide_termination(self, request, pk=None):
        tenancy = self.get_object()
        decision = request.data.get('decision')
        
        termination = TenancyTermination.objects.filter(tenancy=tenancy).first()
        if not termination:
            return Response({"error": "No termination record found."}, status=status.HTTP_404_NOT_FOUND)
        
        if decision == 'approved':
            termination.approved_by = request.user
            termination.save()
            tenancy.end_date = termination.effective_date
            if hasattr(Tenancy.Status, 'SCHEDULED_FOR_TERMINATION'):
                tenancy.status = Tenancy.Status.SCHEDULED_FOR_TERMINATION
            else:
                tenancy.status = 'scheduled_for_termination'
            tenancy.save(update_fields=['end_date', 'status'])
            return Response({"detail": "Termination approved.", "termination_id": termination.id}, status=status.HTTP_200_OK)
        elif decision == 'rejected':
            termination.delete()
            return Response({"detail": "Termination rejected."}, status=status.HTTP_200_OK)
        
        return Response({"error": "Invalid decision."}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Decide on Extension Request")
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def decide_extension(self, request, pk=None):
        from ..services import ExtensionService
        tenancy = self.get_object()
        decision = request.data.get('decision')
        reason = request.data.get('reason', '')
        extension_id = request.data.get('extension_id')
        
        if extension_id:
            try: extension = TenancyExtension.objects.get(id=extension_id, tenancy=tenancy)
            except TenancyExtension.DoesNotExist: return Response({"error": "Extension not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            extension = TenancyExtension.objects.filter(tenancy=tenancy, status='pending').order_by('-requested_at').first()
        
        if not extension:
            return Response({"error": "No pending extension found."}, status=status.HTTP_404_NOT_FOUND)
        
        if decision == 'approved':
            try:
                ExtensionService.approve_extension(extension, approved_by=request.user)
                return Response({"detail": "Extension approved."}, status=status.HTTP_200_OK)
            except Exception as e: return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        elif decision == 'rejected':
            try:
                ExtensionService.reject_extension(extension, approved_by=request.user, reason=reason)
                return Response({"detail": "Extension rejected."}, status=status.HTTP_200_OK)
            except Exception as e: return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({"error": "Invalid decision."}, status=status.HTTP_400_BAD_REQUEST)

    # ✅ UPDATED: CANCEL ACTIONS NOW TARGET THE UNIFIED APPLICATION MODEL
    @extend_schema(summary="Cancel Transfer Request")
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def cancel_transfer(self, request, pk=None):
        tenancy = self.get_object()
        
        application = Application.objects.filter(
            applicant=tenancy.tenant, unit=tenancy.unit, application_type='transfer',
            status__in=['pending', 'under_review', 'escalated']
        ).first()
        
        if not application:
            return Response({"error": "No pending transfer application found."}, status=status.HTTP_404_NOT_FOUND)
        
        application.status = 'cancelled'
        application.save(update_fields=['status'])
        return Response({"detail": "Transfer application cancelled."}, status=status.HTTP_200_OK)

    @extend_schema(summary="Cancel Extension Request")
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def cancel_extension(self, request, pk=None):
        tenancy = self.get_object()
        
        application = Application.objects.filter(
            applicant=tenancy.tenant, unit=tenancy.unit, application_type='extension',
            status__in=['pending', 'under_review', 'escalated']
        ).first()
        
        if application:
            application.status = 'cancelled'
            application.save(update_fields=['status'])
            return Response({"detail": "Extension application cancelled."}, status=status.HTTP_200_OK)
            
        extension = TenancyExtension.objects.filter(tenancy=tenancy, status='pending').first()
        if not extension:
            return Response({"error": "No pending extension found."}, status=status.HTTP_404_NOT_FOUND)
        
        extension.status = 'cancelled'
        extension.save(update_fields=['status'])
        return Response({"detail": "Extension request cancelled."}, status=status.HTTP_200_OK)

    @extend_schema(summary="Cancel Termination Request")
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveTenancyActions])
    def cancel_termination(self, request, pk=None):
        tenancy = self.get_object()
        
        application = Application.objects.filter(
            applicant=tenancy.tenant, unit=tenancy.unit, application_type='termination',
            status__in=['pending', 'under_review', 'escalated']
        ).first()
        
        if not application:
            return Response({"error": "No pending termination application found."}, status=status.HTTP_404_NOT_FOUND)
        
        application.status = 'cancelled'
        application.save(update_fields=['status'])
        return Response({"detail": "Termination application cancelled."}, status=status.HTTP_200_OK)

    # ==========================================
    # ✅ NEW: TERMINATION SETTLEMENT ENDPOINTS
    # ==========================================

    @extend_schema(summary="Preview Termination Settlement")
    @action(detail=True, methods=['GET'], url_path='settlement-preview', permission_classes=[CanApproveTenancyActions])
    def settlement_preview(self, request, pk=None):
        """
        Calculates the financial breakdown (Deposit vs Penalties vs Arrears) 
        for the frontend modal to display before finalizing.
        """
        tenancy = self.get_object()
        
        penalty = Decimal(request.query_params.get('penalty', '0.00'))
        manager_deductions = Decimal(request.query_params.get('manager_deductions', '0.00'))
        waive_arrears = request.query_params.get('waive_arrears', 'false').lower() == 'true'
        
        total_penalties = penalty + manager_deductions
        
        from apps.tenancy.services.termination_settelment_service  import TerminationSettlementService
        
        settlement = TerminationSettlementService.calculate_settlement(tenancy, total_penalties)
        
        # Recalculate net if manager chooses to waive arrears
        if waive_arrears:
            deposit_held = Decimal(settlement['deposit_held'])
            arrears = Decimal("0.00")
            net_refund = deposit_held - total_penalties - arrears
            settlement['outstanding_arrears'] = "0.00"
            settlement['net_refund'] = str(max(Decimal("0.00"), net_refund))
            settlement['amount_owed_by_tenant'] = str(abs(net_refund)) if net_refund < 0 else "0.00"
            settlement['requires_tenant_payment'] = net_refund < 0
            
        return Response(settlement, status=status.HTTP_200_OK)

    @extend_schema(summary="Finalize Termination Settlement and Vacate Unit")
    @action(detail=True, methods=['POST'], url_path='finalize-settlement', permission_classes=[CanApproveTenancyActions])
    def finalize_settlement(self, request, pk=None):
        """
        Executes the final settlement, triggers the refund/invoice, 
        and officially vacates the unit back to the marketplace.
        """
        tenancy = self.get_object()
        
        termination_id = request.data.get('termination_id')
        manager_deductions = Decimal(request.data.get('manager_deductions', '0.00'))
        waive_arrears = request.data.get('waive_arrears', False)
        
        # Fetch or create the termination record
        termination_record = TenancyTermination.objects.filter(tenancy=tenancy).first()
        if not termination_record:
            # Fallback for unified flow where only an Application was created
            termination_record = TenancyTermination.objects.create(
                tenancy=tenancy,
                termination_type='tenant_request',
                notes='Termination via unified application flow',
                penalty_applied=0,
                approved_by=request.user,
                effective_date=tenancy.end_date or timezone.now().date()
            )
            
        from apps.tenancy.services.termination_settelment_service import TerminationSettlementService
        
        try:
            result = TerminationSettlementService.finalize_settlement_and_vacate(
                tenancy=tenancy,
                termination_record=termination_record,
                approved_by_user=request.user,
                manager_deductions=manager_deductions,
                waive_arrears=waive_arrears
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ==========================================
    # LIST ACTIONS (Legacy support)
    # ==========================================

    @extend_schema(summary="List Transfer Requests")
    @action(detail=False, methods=['GET'], url_path='transfers')
    def list_transfers(self, request):
        user = request.user
        try:
            if user.role in ['admin', 'landlord', 'agency', 'manager']:
                transfers = (TenancyTransfer.objects.filter(to_property__current_manager=user) | TenancyTransfer.objects.filter(to_property__created_by=user)).distinct().order_by('-requested_at')
            else:
                transfers = TenancyTransfer.objects.filter(tenant=user).order_by('-requested_at')
        except Exception:
            transfers = TenancyTransfer.objects.all().order_by('-requested_at')
            
        data = []
        for t in transfers:
            try:
                tenant_name = "Unknown"
                if getattr(t, 'tenant', None):
                    profile = getattr(t.tenant, 'profile', None)
                    tenant_name = getattr(profile, 'full_name', None) or t.tenant.email or "Unknown"
                data.append({
                    "id": t.id, "tenant_name": tenant_name, "tenant_email": t.tenant.email if getattr(t, 'tenant', None) else "",
                    "from_property_title": getattr(t.from_property, 'title', '') if getattr(t, 'from_property', None) else "",
                    "from_unit_code": getattr(t.from_unit, 'unit_code', '') if getattr(t, 'from_unit', None) else "",
                    "to_property_title": getattr(t.to_property, 'title', '') if getattr(t, 'to_property', None) else "",
                    "to_unit_code": getattr(t.to_unit, 'unit_code', '') if getattr(t, 'to_unit', None) else "",
                    "reason": getattr(t, 'reason', ''), "status": getattr(t, 'transfer_status', 'pending'),
                })
            except Exception as e: continue
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(summary="List Termination Notices")
    @action(detail=False, methods=['GET'], url_path='terminations')
    def list_terminations(self, request):
        user = request.user
        try:
            if user.role in ['admin', 'landlord', 'agency', 'manager']:
                terminations = (TenancyTermination.objects.filter(tenancy__property__current_manager=user) | TenancyTermination.objects.filter(tenancy__property__created_by=user)).distinct().order_by('-created_at')
            else:
                terminations = TenancyTermination.objects.filter(tenancy__tenant=user).order_by('-created_at')
        except Exception:
            terminations = TenancyTermination.objects.all().order_by('-created_at')
            
        data = []
        for term in terminations:
            try:
                tenancy = getattr(term, 'tenancy', None)
                tenant_name = "Unknown"
                if tenancy and getattr(tenancy, 'tenant', None):
                    profile = getattr(tenancy.tenant, 'profile', None)
                    tenant_name = getattr(profile, 'full_name', None) or tenancy.tenant.email or "Unknown"
                data.append({
                    "id": term.id, "tenant_name": tenant_name,
                    "property_title": getattr(tenancy.property, 'title', '') if tenancy and getattr(tenancy, 'property', None) else "",
                    "unit_code": getattr(tenancy.unit, 'unit_code', '') if tenancy and getattr(tenancy, 'unit', None) else "",
                    "termination_type": getattr(term, 'termination_type', 'tenant_request'),
                    "effective_date": str(getattr(term, 'effective_date', '')) if getattr(term, 'effective_date', None) else "",
                })
            except Exception as e: continue
        return Response(data, status=status.HTTP_200_OK)


class OccupancyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.OccupancySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False): return Occupancy.objects.none()
        return Occupancy.objects.filter(unit__property__is_active=True).select_related('unit', 'current_tenant', 'active_tenancy')


class TenancyNoteViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.TenancyNoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False): return TenancyNote.objects.none()
        if not self.request.user.is_authenticated: return TenancyNote.objects.none()
        user = self.request.user
        if user.role == 'admin': return TenancyNote.objects.all().select_related('created_by')
        return (TenancyNote.objects.filter(tenancy__tenant=user) | TenancyNote.objects.filter(tenancy__property__created_by=user)).distinct().select_related('created_by')


class TenancyWaiverViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.TenancyWaiverSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False): return TenancyWaiver.objects.none()
        if not self.request.user.is_authenticated: return TenancyWaiver.objects.none()
        user = self.request.user
        if user.role == 'admin': return TenancyWaiver.objects.all()
        return (TenancyWaiver.objects.filter(tenancy__tenant=user) | TenancyWaiver.objects.filter(tenancy__property__created_by=user))


class TenantHistoryViewSet(viewsets.GenericViewSet):
    queryset = Tenancy.objects.none()
    serializer_class = serializers.TenancySerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(summary="Get Tenant History Summary")
    @action(detail=True, methods=['GET'], url_path='history')
    def history(self, request, pk=None):
        tenant_id = pk 
        if request.user.role not in ['admin', 'landlord', 'agency'] and request.user.id != int(tenant_id):
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
        summary = HistoryService.get_tenant_history_summary(tenant_id)
        return Response(summary, status=status.HTTP_200_OK)

    @extend_schema(summary="Get Tenant History Summary (Alias)")
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

    @extend_schema(summary="Get Tenant Profile for Application Review")
    def retrieve(self, request, application_id=None):
        profile_data = HistoryService.get_tenant_summary_for_application_review(application_id)
        return Response(profile_data, status=status.HTTP_200_OK)