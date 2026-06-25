from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from django.contrib.auth import get_user_model

from . import serializers
from ..models import Application
from ..services import NotesService
from ..permissions.application_permissions import IsApplicant, IsAgentOrManager, CanApproveApplication

User = get_user_model()


@extend_schema_view(
    list=extend_schema(summary="List Applications", description="Returns applications based on user role."),
    retrieve=extend_schema(summary="Get Application Details", description="Returns full application state, including reviewer context."),
    create=extend_schema(summary="Submit Application", description="Submits a Rental, Transfer, or Eviction application."),
    make_decision=extend_schema(
        summary="Make Decision on Application",
        description="Approves, rejects, or escalates an application.",
        request=serializers.ApplicationDecisionSerializer,
        responses={200: serializers.ApplicationDetailSerializer}
    ),
    add_note=extend_schema(
        summary="Add Application Note",
        description="Adds an internal review note.",
        request=serializers.ApplicationNoteSerializer,
        responses={201: serializers.ApplicationNoteSerializer}
    ),
    # ✅ NEW: Swagger documentation for the cancel action
    cancel=extend_schema(
        summary="Cancel Application",
        description="Allows the applicant to cancel their application if it is still pending or under review.",
        responses={200: serializers.ApplicationDetailSerializer}
    )
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
            return (qs1 | qs2).select_related('applicant', 'property', 'unit').distinct().order_by('-created_at')
            
        return Application.objects.filter(applicant=user).select_related('property', 'unit').order_by('-created_at')

    def get_serializer_class(self):
        if getattr(self, 'swagger_fake_view', False):
            return serializers.ApplicationDetailSerializer

        if self.action == 'create':
            app_type = self.request.data.get('application_type')
            if app_type == 'rental':
                return serializers.RentalApplicationCreateSerializer
            elif app_type == 'transfer':
                return serializers.TransferApplicationCreateSerializer
            elif app_type == 'eviction':
                return serializers.EvictionApplicationCreateSerializer
        elif self.action == 'make_decision':
            return serializers.ApplicationDecisionSerializer
        elif self.action == 'add_note':
            return serializers.ApplicationNoteSerializer
            
        return serializers.ApplicationDetailSerializer

    def get_permissions(self):
        # ✅ CRITICAL FIX: DRF requires INSTANCES of permission classes when overriding get_permissions().
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        
        if self.action in ['make_decision', 'add_note']:
            return [IsAgentOrManager()]
            
        # ✅ NEW: Only the applicant who created the application can cancel it
        if self.action == 'cancel':
            return [IsApplicant()]
            
        return [permissions.IsAuthenticated()]

    # ✅ Override create to return the fully populated ApplicationDetailSerializer
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        
        output_serializer = serializers.ApplicationDetailSerializer(application, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: serializers.ApplicationDetailSerializer})
    @action(detail=True, methods=['POST'], permission_classes=[CanApproveApplication])
    def make_decision(self, request, pk=None):
        application = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        updated_application = serializer.update(application, serializer.validated_data)
        return Response(self.get_serializer(updated_application).data, status=status.HTTP_200_OK)

    @extend_schema(responses={201: serializers.ApplicationNoteSerializer})
    @action(detail=True, methods=['POST'], permission_classes=[IsAgentOrManager])
    def add_note(self, request, pk=None):
        application = self.get_object()
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        note = NotesService.create_note(
            application=application,
            user=request.user,
            content=serializer.validated_data['content'],
            note_type=serializer.validated_data.get('note_type', 'agent_review'),
            is_confidential=serializer.validated_data.get('is_confidential', False)
        )
        return Response(serializers.ApplicationNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    # ✅ NEW: CANCEL ACTION
    @extend_schema(responses={200: serializers.ApplicationDetailSerializer})
    @action(detail=True, methods=['POST'], permission_classes=[IsApplicant])
    def cancel(self, request, pk=None):
        """
        Allows the applicant to cancel their application.
        Only allowed if the status is 'pending' or 'under_review'.
        """
        application = self.get_object()
        
        # Enforce business rule: cannot cancel if already approved/rejected
        if application.status not in ['pending', 'under_review']:
            return Response(
                {"error": f"This application cannot be cancelled because its status is '{application.status}'."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        application.status = 'cancelled'
        application.save(update_fields=['status'])
        
        output_serializer = serializers.ApplicationDetailSerializer(application, context={'request': request})
        return Response(
            {"detail": "Application cancelled successfully.", "application": output_serializer.data}, 
            status=status.HTTP_200_OK
        )