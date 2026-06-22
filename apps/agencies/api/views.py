from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from django.contrib.auth import get_user_model
from django.apps import apps

from . import serializers
from ..models import Agency, AgencyDirector, AgencyVerification, AgencyProfile, AgencyStaff, DelegatedProperty
from ..services import AgencyService, AgencyVerificationService, StaffService, DelegationService, AgencyProfileService
from ..permissions.agency_permissions import IsAgencyAdmin

User = get_user_model()
Property = apps.get_model('properties', 'Property')


@extend_schema_view(
    list=extend_schema(summary="List Agencies", responses={200: serializers.AgencySerializer(many=True)}),
    retrieve=extend_schema(summary="Get Agency Details", responses={200: serializers.AgencyDetailSerializer}),
    create=extend_schema(summary="Create Agency", request=serializers.AgencySerializer)
)
class AgencyViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AgencySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # ✅ FIX: Prevent drf-spectacular from crashing during schema generation
        if getattr(self, 'swagger_fake_view', False):
            return Agency.objects.none()
            
        user = self.request.user
        if not user.is_authenticated:
            return Agency.objects.none()
            
        if user.role == 'admin':
            return Agency.objects.all().select_related('business_profile')
        
        return Agency.objects.filter(
            created_by=user
        ) | Agency.objects.filter(
            directors__user=user
        ) | Agency.objects.filter(
            staff_members__user=user, staff_members__status='active'
        ).distinct().select_related('business_profile')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.AgencyDetailSerializer
        return serializers.AgencySerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class AgencyProfileViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.AgencyProfileSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgencyAdmin]

    def get_queryset(self):
        agency_id = self.kwargs.get('agency_pk')
        return AgencyProfile.objects.filter(agency_id=agency_id)

    @extend_schema(summary="Get Agency Business Profile", responses={200: serializers.AgencyProfileSerializer})
    @action(detail=False, methods=['GET'])
    def retrieve_profile(self, request, agency_pk=None):
        agency = Agency.objects.get(id=agency_pk)
        profile = AgencyProfileService.get_profile(agency)
        return Response(self.get_serializer(profile).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Update Agency Business Profile", request=serializers.AgencyProfileSerializer)
    @action(detail=False, methods=['PUT', 'PATCH'])
    def update_profile(self, request, agency_pk=None):
        agency = Agency.objects.get(id=agency_pk)
        profile = AgencyProfileService.get_profile(agency)
        
        serializer = self.get_serializer(
            profile, data=request.data, partial=True, 
            context={'agency': agency, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer(serializer.save()).data, status=status.HTTP_200_OK)


class AgencyDirectorViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AgencyDirectorSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgencyAdmin]

    def get_queryset(self):
        agency_pk = self.kwargs.get('agency_pk')
        return AgencyDirector.objects.filter(agency_id=agency_pk)

    def perform_create(self, serializer):
        agency_pk = self.kwargs.get('agency_pk')
        agency = Agency.objects.get(id=agency_pk)
        serializer.save(agency=agency)

    @extend_schema(summary="Verify Director")
    @action(detail=True, methods=['PATCH'], url_path='verify')
    def verify_director(self, request, pk=None, agency_pk=None):
        director = self.get_object()
        director.verification_status = 'verified'
        director.save(update_fields=['verification_status'])
        return Response({"status": "verified", "message": "Director verified successfully."})


class AgencyVerificationViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.AgencyVerificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgencyAdmin]

    def get_queryset(self):
        agency_pk = self.kwargs.get('agency_pk')
        return AgencyVerification.objects.filter(agency_id=agency_pk)

    @extend_schema(summary="Submit Agency Verification")
    @action(detail=False, methods=['PUT', 'PATCH'], url_path='submit')
    def submit(self, request, agency_pk=None):
        agency = Agency.objects.get(id=agency_pk)
        verification = AgencyVerificationService.submit_verification(agency, request.data, request.FILES)
        return Response(serializers.AgencyVerificationSerializer(verification).data, status=status.HTTP_200_OK)

    @extend_schema(summary="Get Verification Status")
    @action(detail=False, methods=['GET'], url_path='status')
    def status(self, request, agency_pk=None):
        agency = Agency.objects.get(id=agency_pk)
        verification = AgencyVerification.objects.filter(agency=agency).first()
        if not verification:
            return Response({"status": "not_submitted"}, status=status.HTTP_200_OK)
        return Response(serializers.AgencyVerificationSerializer(verification).data, status=status.HTTP_200_OK)


class AgencyStaffViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.AgencyStaffSerializer
    permission_classes = [permissions.IsAuthenticated, IsAgencyAdmin]

    def get_queryset(self):
        agency_pk = self.kwargs.get('agency_pk')
        return AgencyStaff.objects.filter(agency_id=agency_pk)

    def perform_create(self, serializer):
        agency_pk = self.kwargs.get('agency_pk')
        agency = Agency.objects.get(id=agency_pk)
        StaffService.create_staff(agency, serializer.validated_data)

    @action(detail=True, methods=['POST'], url_path='deactivate')
    def deactivate(self, request, pk=None, agency_pk=None):
        staff = self.get_object()
        StaffService.deactivate_staff(staff)
        return Response({"status": "deactivated", "message": "Staff member deactivated successfully."})


class DelegationViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.DelegatedPropertySerializer
    permission_classes = [permissions.IsAuthenticated, IsAgencyAdmin]

    def get_queryset(self):
        agency_pk = self.kwargs.get('agency_pk')
        return DelegatedProperty.objects.filter(agency_id=agency_pk)

    def perform_create(self, serializer):
        agency_pk = self.kwargs.get('agency_pk')
        agency = Agency.objects.get(id=agency_pk)
        DelegationService.delegate_property(agency, serializer.validated_data)

    @action(detail=True, methods=['POST'], url_path='revoke')
    def revoke(self, request, pk=None, agency_pk=None):
        delegation = self.get_object()
        DelegationService.revoke_delegation(delegation)
        return Response({"status": "revoked", "message": "Delegation revoked successfully."})