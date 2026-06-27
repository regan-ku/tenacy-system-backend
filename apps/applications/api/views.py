from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view

from django.contrib.auth import get_user_model

from . import serializers
from ..models import Application, ApplicationNote
from ..services import NotesService, ApplicationService
from ..permissions.application_permissions import IsApplicant, IsAgentOrManager, CanApproveApplication

User = get_user_model()

@extend_schema_view(
    list=extend_schema(summary="List Applications"),
    retrieve=extend_schema(summary="Get Application Details"),
    create=extend_schema(summary="Submit Application"),
    make_decision=extend_schema(summary="Make Decision on Application"),
)
class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.ApplicationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Application.objects.none()
        if not self.request.user.is_authenticated:
            return Application.objects.none()

        user = self.request.user
        if user.role in ['admin', 'landlord', 'agency', 'manager']:
            qs1 = Application.objects.filter(property__current_manager=user)
            qs2 = Application.objects.filter(property__created_by=user)
            qs = (qs1 | qs2).select_related('applicant', 'property', 'unit').distinct().order_by('-created_at')
        else:
            qs = Application.objects.filter(applicant=user).select_related('property', 'unit').order_by('-created_at')

        app_type = self.request.query_params.get('application_type')
        if app_type:
            qs = qs.filter(application_type=app_type)

        return qs

    def get_serializer_class(self):
        if getattr(self, 'swagger_fake_view', False):
            return serializers.ApplicationDetailSerializer

        if self.action == 'create':
            app_type = self.request.data.get('application_type')
            if app_type == 'rental': 
                return serializers.RentalApplicationCreateSerializer
            elif app_type == 'transfer': 
                return serializers.TransferApplicationCreateSerializer
            elif app_type in ['termination', 'eviction']: 
                return serializers.EvictionApplicationCreateSerializer
            elif app_type == 'extension':
                return serializers.ExtensionApplicationCreateSerializer
            else:
                return serializers.RentalApplicationCreateSerializer
                
        elif self.action == 'make_decision': 
            return serializers.ApplicationDecisionSerializer
        elif self.action == 'add_note': 
            return serializers.ApplicationNoteSerializer
        elif self.action in ['update', 'partial_update', 'update_transfer']:
            return serializers.ApplicationUpdateSerializer
            
        return serializers.ApplicationDetailSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        if self.action in ['make_decision', 'add_note', 'manager_cancel', 'apply_waiver', 'revoke_waiver']:
            return [IsAgentOrManager()]
        if self.action in ['cancel', 'update_transfer']:
            return [IsApplicant()]
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated()]  # Will check role in the method
        return [permissions.IsAuthenticated()]

    def _get_target_unit_for_application(self, application):
        """For transfers, the pending tenancy is on the TARGET unit, not the base unit."""
        if application.application_type == 'transfer':
            import json
            note = application.notes.filter(content__startswith='TRANSFER_REQUEST:').first()
            if note:
                try:
                    json_str = note.content.replace('TRANSFER_REQUEST:', '')
                    data = json.loads(json_str)
                    from apps.properties.models import Unit
                    return Unit.objects.filter(id=data.get('to_unit')).first() or application.unit
                except Exception:
                    pass
        return application.unit

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        output_serializer = serializers.ApplicationDetailSerializer(application, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    # ✅ NEW: Role-based update method
    @extend_schema(summary="Edit Application (Role-Based)")
    def update(self, request, *args, **kwargs):
        """
        Handles editing of applications with strict role-based rules:
        - Tenants can ONLY edit if status is 'pending' or 'under_review'.
        - Managers can edit if status is 'pending', 'under_review', or 'approved'.
        """
        application = self.get_object()
        is_manager = request.user.role in ['admin', 'landlord', 'agency', 'manager']
        is_applicant = request.user == application.applicant
        
        # TENANT RULE: Can only edit before approval
        if is_applicant and not is_manager and application.status not in ['pending', 'under_review']:
            return Response(
                {"error": "You can only edit applications before they are approved."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        # MANAGER RULE: Can edit pending or approved applications
        if is_manager and application.status not in ['pending', 'under_review', 'approved']:
            return Response(
                {"error": "Can only edit pending or approved applications."}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        if not is_applicant and not is_manager:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        # Use the update serializer
        serializer = serializers.ApplicationUpdateSerializer(
            application, 
            data=request.data, 
            partial=True, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        updated_app = serializer.save()
        
        output_serializer = serializers.ApplicationDetailSerializer(updated_app, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        """Allow PATCH requests to use the same logic as update."""
        return self.update(request, *args, **kwargs)

    # Legacy endpoint for transfer-specific updates
    @extend_schema(summary="Update Pending Transfer Application")
    @action(detail=True, methods=['PUT', 'PATCH'], permission_classes=[IsApplicant], url_path='update-transfer')
    def update_transfer(self, request, pk=None):
        """
        Allows applicants to edit their pending transfer applications.
        Only works if application is in 'pending' or 'under_review' status.
        """
        application = self.get_object()
        
        if application.application_type != 'transfer':
            return Response(
                {"error": "This endpoint is only for transfer applications."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if application.status not in ['pending', 'under_review']:
            return Response(
                {"error": f"Cannot edit application with status '{application.status}'. Only pending or under_review applications can be edited."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if application.applicant != request.user:
            return Response(
                {"error": "You can only edit your own applications."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            from apps.properties.models import Unit
            to_unit = Unit.objects.get(id=serializer.validated_data['to_unit_id'])
            
            updated_application = ApplicationService.update_transfer_application(
                application=application,
                to_unit=to_unit,
                reason=serializer.validated_data.get('reason', ''),
                desired_move_in_date=serializer.validated_data.get('desired_move_in_date'),
                notes=serializer.validated_data.get('notes', '')
            )
            
            output_serializer = serializers.ApplicationDetailSerializer(updated_application, context={'request': request})
            return Response(output_serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['POST'], permission_classes=[CanApproveApplication])
    def make_decision(self, request, pk=None):
        application = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        updated_application = serializer.update(application, serializer.validated_data)
        return Response(self.get_serializer(updated_application).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['POST'], permission_classes=[IsAgentOrManager])
    def add_note(self, request, pk=None):
        application = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        note = NotesService.create_note(
            application=application, user=request.user, content=serializer.validated_data['content'],
            note_type=serializer.validated_data.get('note_type', 'agent_review'),
            is_confidential=serializer.validated_data.get('is_confidential', False)
        )
        return Response(serializers.ApplicationNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['POST'], permission_classes=[IsApplicant])
    def cancel(self, request, pk=None):
        application = self.get_object()
        if application.status not in ['pending', 'under_review']:
            return Response({"error": f"Cannot cancel application with status '{application.status}'."}, status=400)
        application.status = 'cancelled'
        application.save(update_fields=['status'])
        return Response({"detail": "Application cancelled."}, status=200)

    @action(detail=True, methods=['POST'], permission_classes=[IsAgentOrManager])
    def manager_cancel(self, request, pk=None):
        application = self.get_object()
        reason = request.data.get('reason', 'Cancelled by manager')
        if application.status != 'approved':
            return Response({"error": "Only approved applications can be cancelled by managers."}, status=400)
        application.status = 'cancelled'
        application.save(update_fields=['status'])
        
        from apps.tenancy.models import Tenancy
        target_unit = self._get_target_unit_for_application(application)
        
        linked_tenancy = Tenancy.objects.filter(tenant=application.applicant, unit=target_unit, status='pending_payment').first()
        if linked_tenancy:
            linked_tenancy.status = 'cancelled'
            linked_tenancy.save(update_fields=['status'])
            
        target_unit.status = 'available'
        target_unit.save(update_fields=['status'])
        
        ApplicationNote.objects.create(
            application=application, note_type='manager_remark', 
            content=f"Application cancelled by manager. Reason: {reason}", created_by=request.user
        )
        return Response({"detail": "Application and linked tenancy cancelled successfully."}, status=200)

    @action(detail=True, methods=['POST'], permission_classes=[IsAgentOrManager])
    def apply_waiver(self, request, pk=None):
        application = self.get_object()
        waiver_types = request.data.get('waiver_types', []) 
        reason = request.data.get('reason', 'Waived by manager')
        if application.status != 'approved': 
            return Response({"error": "Waivers can only be applied to approved applications."}, status=400)
        if not waiver_types: 
            return Response({"error": "Please select at least one waiver type."}, status=400)
        
        from apps.tenancy.models import Tenancy, TenancyWaiver
        target_unit = self._get_target_unit_for_application(application)
        linked_tenancy = Tenancy.objects.filter(tenant=application.applicant, unit=target_unit, status='pending_payment').first()
        if not linked_tenancy: 
            return Response({"error": "No pending payment tenancy found."}, status=404)
        
        for w_type in waiver_types:
            if w_type not in ['rent', 'deposit', 'service_charge']: continue
            TenancyWaiver.objects.create(
                tenancy=linked_tenancy, waiver_type=w_type, reason=reason, 
                requested_by=request.user, approved_by=request.user, status='approved'
            )
            if w_type == 'deposit': 
                linked_tenancy.deposit_paid = True; linked_tenancy.deposit_waived = True
            elif w_type == 'service_charge': 
                linked_tenancy.service_charge_paid = True; linked_tenancy.service_charge_waived = True
            elif w_type == 'rent': 
                if hasattr(linked_tenancy, 'rent_paid'): linked_tenancy.rent_paid = True
                if hasattr(linked_tenancy, 'rent_waived'): linked_tenancy.rent_waived = True
        linked_tenancy.save()
        
        if linked_tenancy.is_ready_for_activation():
            from apps.tenancy.services.tenancy_service import TenancyService
            TenancyService.activate_tenancy(linked_tenancy, activated_by=request.user)
            return Response({"detail": f"Successfully waived: {', '.join(waiver_types)}. Tenancy is now ACTIVE!", "status": "activated"}, status=200)
        return Response({"detail": f"Successfully waived: {', '.join(waiver_types)}. Awaiting remaining payments.", "status": "pending_remaining"}, status=200)

    @action(detail=True, methods=['POST'], permission_classes=[IsAgentOrManager])
    def revoke_waiver(self, request, pk=None):
        application = self.get_object()
        waiver_types = request.data.get('waiver_types', [])
        reason = request.data.get('reason', 'Waiver revoked by manager')
        if application.status != 'approved': 
            return Response({"error": "Waivers can only be revoked for approved applications."}, status=400)
        if not waiver_types: 
            return Response({"error": "Please select at least one waiver type to revoke."}, status=400)
        
        from apps.tenancy.models import Tenancy, TenancyWaiver
        target_unit = self._get_target_unit_for_application(application)
        linked_tenancy = Tenancy.objects.filter(tenant=application.applicant, unit=target_unit, status='pending_payment').first()
        if not linked_tenancy: 
            return Response({"error": "Cannot revoke: Tenancy is already active or cancelled."}, status=400)
        
        revoked_count = 0
        for w_type in waiver_types:
            if w_type not in ['rent', 'deposit', 'service_charge']: continue
            waivers = TenancyWaiver.objects.filter(tenancy=linked_tenancy, waiver_type=w_type, status='approved')
            for w in waivers: 
                w.status = 'revoked'; w.save(update_fields=['status']); revoked_count += 1
            if w_type == 'deposit': 
                linked_tenancy.deposit_paid = False; linked_tenancy.deposit_waived = False
            elif w_type == 'service_charge': 
                linked_tenancy.service_charge_paid = False; linked_tenancy.service_charge_waived = False
            elif w_type == 'rent': 
                if hasattr(linked_tenancy, 'rent_paid'): linked_tenancy.rent_paid = False
                if hasattr(linked_tenancy, 'rent_waived'): linked_tenancy.rent_waived = False
        linked_tenancy.save()
        
        ApplicationNote.objects.create(
            application=application, note_type='manager_remark', 
            content=f"Waivers revoked for: {', '.join(waiver_types)}. Reason: {reason}", created_by=request.user
        )
        return Response({"detail": f"Successfully revoked {revoked_count} waiver(s).", "status": "revoked"}, status=200)