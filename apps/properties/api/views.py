# from rest_framework import viewsets, status, permissions, serializers, parsers
# from rest_framework.response import Response
# from rest_framework.decorators import action
# from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter, OpenApiTypes

# from django.db.models import Q, Prefetch 
# from django.contrib.auth import get_user_model

# from . import serializers as prop_serializers
# from ..models import Property, Location, UnitGroup, Unit, PropertyMedia
# from ..models.enums import UnitStatus
# from ..services import PropertyService, UnitGroupService, UnitService, MediaService
# from ..permissions.property_permissions import IsPropertyOwnerOrManager, IsDelegatedAgencyStaff, IsMarketplaceReadOnly
# from apps.tenancy.models.tenancy import Tenancy
# from apps.accounts.models.next_of_kin import NextOfKin

        

# # ✅ Top-level imports for Agency delegation logic
# from apps.agencies.models.agency import Agency
# from apps.agencies.models.delegated_property import DelegatedProperty

# User = get_user_model()


# # ✅ FIX: Dedicated serializer to resolve Spectacular request body warning
# class UnitStatusUpdateSerializer(serializers.Serializer):
#     status = serializers.ChoiceField(
#         choices=UnitStatus.choices, 
#         help_text="New status for the unit (e.g., available, occupied, maintenance, reserved)."
#     )


# @extend_schema_view(
#     list=extend_schema(summary="List Properties", description="Returns a list of properties based on user role and permissions."),
#     retrieve=extend_schema(summary="Get Property Details", description="Retrieves full details of a specific property, including nested location."),
#     create=extend_schema(summary="Create Property", description="Initiates a new property with nested location data."),
#     update=extend_schema(summary="Update Property", description="Updates property details. Restricted to owners/managers.")
# )
# class PropertyViewSet(viewsets.ModelViewSet):
#     serializer_class = prop_serializers.PropertySerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return Property.objects.none()
            
#         if not self.request.user.is_authenticated:
#             return Property.objects.none()
            
#         user = self.request.user
        
#         # ✅ Base QuerySet with select_related to prevent N+1 for Location and User/Profile
#         if user.role == 'admin':
#             qs = Property.objects.all().select_related('location', 'created_by', 'created_by__profile')
#         else:
#             qs = Property.objects.filter(
#                 Q(created_by=user) | Q(current_manager=user)
#             ).select_related('location', 'created_by', 'created_by__profile').distinct()

#         # ✅ CRITICAL PERFORMANCE FIX: Prefetch delegation data for Agency users
#         if user.role == 'agency':
#             # Find the specific agency this user belongs to
#             agency = Agency.objects.filter(
#                 Q(created_by=user) | 
#                 Q(directors__user=user) | 
#                 Q(staff_members__user=user, staff_members__status='active')
#             ).first()
            
#             if agency:
#                 # This attaches the active delegation to the property object as 'active_agency_delegation'
#                 qs = qs.prefetch_related(
#                     Prefetch(
#                         'agency_delegations', # Matches related_name in DelegatedProperty model
#                         queryset=DelegatedProperty.objects.filter(agency=agency, status='active'),
#                         to_attr='active_agency_delegation'
#                     )
#                 )
                
#         return qs

#     def perform_create(self, serializer):
#         serializer.save()

#     @extend_schema(
#         summary="Generate Units from Group",
#         description="Triggers bulk unit generation based on a Unit Group template. Enforces capacity and floor validation.",
#         parameters=[
#             OpenApiParameter(name='group_pk', type=int, location=OpenApiParameter.PATH, description="ID of the unit group to generate units from")
#         ],
#         request=None,
#         responses={201: prop_serializers.UnitSerializer(many=True)}
#     )
#     @action(detail=True, methods=['POST'], url_path='unit-groups/(?P<group_pk>[^/.]+)/generate', permission_classes=[IsPropertyOwnerOrManager])
#     def generate_units(self, request, pk=None, group_pk=None):
#         property_obj = self.get_object()
#         try:
#             unit_group = UnitGroup.objects.get(id=group_pk, property=property_obj)
#         except UnitGroup.DoesNotExist:
#             return Response({"error": "Unit group not found for this property."}, status=status.HTTP_404_NOT_FOUND)
            
#         units = UnitGroupService.generate_units_from_group(unit_group, request.user)
#         serializer = prop_serializers.UnitSerializer(units, many=True)
#         return Response(serializer.data, status=status.HTTP_201_CREATED)

#     @extend_schema(
#         summary="Finalize Unit Groups & Generate Units",
#         description="Accepts a list of Unit Group drafts, saves them to the DB, and immediately generates the individual Unit records. Called at the end of the Property Wizard Step 4.",
#         request={
#             'application/json': {
#                 'type': 'object',
#                 'properties': {
#                     'unit_groups': {
#                         'type': 'array',
#                         'items': {
#                             'type': 'object',
#                             'properties': {
#                                 'name': {'type': 'string'},
#                                 'unit_type': {'type': 'string'},
#                                 'floor_range': {'type': 'string'},
#                                 'billing_cycle': {'type': 'string'},
#                                 'billing_date': {'type': 'integer'},
#                                 'base_rent_amount': {'type': 'string'},
#                                 'service_charge_amount': {'type': 'string'},
#                                 'deposit_amount': {'type': 'string'},
#                                 'capacity': {'type': 'integer'},
#                             }
#                         }
#                     }
#                 }
#             }
#         },
#         responses={201: prop_serializers.UnitGroupSerializer(many=True)}
#     )
#     @action(detail=True, methods=['post'], url_path='finalize-unit-groups', permission_classes=[IsPropertyOwnerOrManager])
#     def finalize_unit_groups(self, request, pk=None):
#         """
#         Accepts a list of Unit Group drafts, saves them to the DB, 
#         and immediately generates the individual Unit records.
#         """
#         property_obj = self.get_object()
#         groups_data = request.data.get('unit_groups', [])
        
#         if not groups_data:
#             return Response({"error": "No unit groups provided."}, status=status.HTTP_400_BAD_REQUEST)
            
#         try:
#             created_groups = UnitGroupService.finalize_property_unit_groups(
#                 property=property_obj, 
#                 user=request.user, 
#                 groups_data=groups_data
#             )
            
#             serializer = prop_serializers.UnitGroupSerializer(created_groups, many=True)
#             return Response(serializer.data, status=status.HTTP_201_CREATED)
            
#         except Exception as e:
#             return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




#         # ... (inside your existing PropertyViewSet class) ...

#     @extend_schema(summary="Get Tenant Financials & Details for a Property")
#     @action(detail=True, methods=['get'], url_path='tenant-financials', permission_classes=[permissions.IsAuthenticated])
#     def tenant_financials(self, request, pk=None):
#         """
#         Aggregates Tenancy, Accounts (Next of Kin), and Payments data 
#         for all active tenants in a specific property.
#         """
#         property_obj = self.get_object()
        
#         #
#         # 2. Get active tenancies for this property
#         tenancies = Tenancy.objects.filter(
#             property=property_obj, 
#             status='active'
#         ).select_related('tenant', 'tenant__profile', 'unit')
        
#         data = []
#         for tenancy in tenancies:
#             tenant_user = tenancy.tenant
            
#             # 3. Fetch Next of Kin from Accounts app
#             nok = NextOfKin.objects.filter(user=tenant_user).first()
#             nok_data = {
#                 "full_name": nok.full_name,
#                 "relationship": nok.relationship,
#                 "phone_number": nok.phone_number,
#                 "city": nok.city
#             } if nok else None
            
#             # 4. TODO: Fetch actual arrears and balance from your Payments app models here
#             # For now, we pull the base financial snapshot from the Tenancy model
#             balance_due = 0 
#             arrears = 0 
            
#             # 5. Format the response to match the frontend TenantFinancialInfo interface
#             data.append({
#                 "tenant_id": tenant_user.id,
#                 "tenant_name": tenant_user.get_full_name() or tenant_user.email,
#                 "tenant_email": tenant_user.email,
#                 "tenant_phone": getattr(tenant_user, 'phone_number', ''),
#                 "property_name": property_obj.title,
#                 "unit_code": tenancy.unit.unit_code if tenancy.unit else "Unassigned",
#                 "rent_amount": float(tenancy.rent_amount),
#                 "deposit_amount": float(tenancy.deposit_amount),
#                 "service_charge": float(tenancy.service_charge_amount),
#                 "balance_due": balance_due,
#                 "arrears": arrears,
#                 "last_payment_date": "", # TODO: Fetch latest payment date from Payments app
#                 "last_payment_amount": 0, # TODO: Fetch latest payment amount from Payments app
#                 "next_billing_date": "", # TODO: Fetch from billing cycle logic
#                 "tenancy_status": tenancy.status,
#                 "tenancy_start_date": str(tenancy.start_date) if hasattr(tenancy, 'start_date') else "",
#                 "tenancy_end_date": str(tenancy.end_date) if hasattr(tenancy, 'end_date') else "",
#                 "next_of_kin": nok_data
#             })
            
#         return Response(data, status=status.HTTP_200_OK)

# class UnitGroupViewSet(viewsets.ModelViewSet):
#     serializer_class = prop_serializers.UnitGroupSerializer
#     permission_classes = [permissions.IsAuthenticated, IsPropertyOwnerOrManager]

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return UnitGroup.objects.none()
#         property_pk = self.kwargs.get('property_pk')
#         return UnitGroup.objects.filter(property_id=property_pk)

#     def get_serializer_context(self):
#         context = super().get_serializer_context()
#         context['property'] = Property.objects.get(id=self.kwargs.get('property_pk'))
#         return context


# class UnitViewSet(viewsets.ModelViewSet):
#     serializer_class = prop_serializers.UnitSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return Unit.objects.none()
            
#         property_pk = self.kwargs.get('property_pk')
        
#         # ✅ CRITICAL FIX: The Unit model uses 'property_ref' as the FK field name, not 'property'.
#         return Unit.objects.filter(property_ref_id=property_pk).select_related('property_ref', 'unit_group')

#     def get_permissions(self):
#         if self.action in ['list', 'retrieve'] and not self.request.user.is_authenticated:
#             return [IsMarketplaceReadOnly()]
#         return [IsPropertyOwnerOrManager(), IsDelegatedAgencyStaff()]

#     @extend_schema(
#         summary="Update Unit Status",
#         description="Updates unit status (e.g., available -> occupied). Restricted to managers.",
#         request=UnitStatusUpdateSerializer,
#         responses={200: prop_serializers.UnitSerializer}
#     )
#     @action(detail=True, methods=['PATCH'], permission_classes=[IsPropertyOwnerOrManager])
#     def update_status(self, request, property_pk=None, pk=None):
#         unit = self.get_object()
#         new_status = request.data.get('status')
#         if not new_status:
#             return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)
            
#         updated_unit = UnitService.update_unit_status(unit, new_status)
#         return Response(prop_serializers.UnitSerializer(updated_unit).data, status=status.HTTP_200_OK)


# class PropertyMediaViewSet(viewsets.ModelViewSet):
#     serializer_class = prop_serializers.PropertyMediaSerializer
#     permission_classes = [permissions.IsAuthenticated, IsPropertyOwnerOrManager]
    
#     # ✅ Explicitly tell DRF to accept multipart file uploads
#     parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

#     def get_queryset(self):
#         if getattr(self, 'swagger_fake_view', False):
#             return PropertyMedia.objects.none()
            
#         property_pk = self.kwargs.get('property_pk')
#         return PropertyMedia.objects.filter(property_ref_id=property_pk)

#     def perform_create(self, serializer):
#         property_pk = self.kwargs.get('property_pk')
#         property_obj = Property.objects.get(id=property_pk)
#         serializer.save(property_ref=property_obj)






from rest_framework import viewsets, status, permissions, serializers, parsers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from django.core.exceptions import ValidationError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter, OpenApiTypes

from django.db.models import Q, Prefetch 
from django.contrib.auth import get_user_model

from . import serializers as prop_serializers
from ..models import Property, UnitGroup, Unit, PropertyMedia
from ..models.enums import UnitStatus
from ..services import UnitGroupService, UnitService
from ..permissions.property_permissions import IsPropertyOwnerOrManager, IsDelegatedAgencyStaff, IsMarketplaceReadOnly
from apps.tenancy.models.tenancy import Tenancy
from apps.accounts.models.next_of_kin import NextOfKin

from apps.agencies.models.agency import Agency
from apps.agencies.models.delegated_property import DelegatedProperty

User = get_user_model()

# ✅ Combined Permission Class (OR Logic)
class IsOwnerOrDelegated(BasePermission):
    """
    Allows access if the user is the property owner/manager OR a delegated agency staff.
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Handle both Unit (property_ref) and UnitGroup/Property (property)
        property_obj = getattr(obj, 'property_ref', None) or getattr(obj, 'property', None)
        
        # If the object itself is the Property (from PropertyViewSet)
        if obj.__class__.__name__ == 'Property':
            property_obj = obj
            
        if not property_obj:
            return False
        
        # 1. Check if user is the owner or current manager
        if property_obj.created_by == request.user:
            return True
        if getattr(property_obj, 'current_manager', None) == request.user:
            return True
            
        # 2. Check if user is a delegated agency staff
        try:
            return IsDelegatedAgencyStaff().has_object_permission(request, view, property_obj)
        except Exception:
            return False


class UnitStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=UnitStatus.choices)

@extend_schema_view(
    list=extend_schema(summary="List Properties"),
    retrieve=extend_schema(summary="Get Property Details"),
    create=extend_schema(summary="Create Property"),
    update=extend_schema(summary="Update Property")
)
class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.PropertySerializer
    
    # ✅ SECURITY FIX: Added IsOwnerOrDelegated to prevent unauthorized edits via direct API calls
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDelegated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Property.objects.none()
        if not self.request.user.is_authenticated:
            return Property.objects.none()
            
        user = self.request.user
        if user.role == 'admin':
            qs = Property.objects.all().select_related('location', 'created_by', 'created_by__profile')
        else:
            qs = Property.objects.filter(
                Q(created_by=user) | Q(current_manager=user)
            ).select_related('location', 'created_by', 'created_by__profile').distinct()

        if user.role == 'agency':
            agency = Agency.objects.filter(
                Q(created_by=user) | 
                Q(directors__user=user) | 
                Q(staff_members__user=user, staff_members__status='active')
            ).first()
            
            if agency:
                qs = qs.prefetch_related(
                    Prefetch(
                        'agency_delegations', 
                        queryset=DelegatedProperty.objects.filter(agency=agency, status='active'),
                        to_attr='active_agency_delegation'
                    )
                )
        return qs

    def perform_create(self, serializer):
        serializer.save()

    @extend_schema(summary="Generate Units from Group")
    @action(detail=True, methods=['POST'], url_path='unit-groups/(?P<group_pk>[^/.]+)/generate', permission_classes=[IsPropertyOwnerOrManager])
    def generate_units(self, request, pk=None, group_pk=None):
        property_obj = self.get_object()
        try:
            unit_group = UnitGroup.objects.get(id=group_pk, property=property_obj)
        except UnitGroup.DoesNotExist:
            return Response({"error": "Unit group not found."}, status=status.HTTP_404_NOT_FOUND)
            
        units = UnitGroupService.generate_units_from_group(unit_group, request.user)
        serializer = prop_serializers.UnitSerializer(units, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Finalize Unit Groups & Generate Units")
    @action(detail=True, methods=['post'], url_path='finalize-unit-groups', permission_classes=[IsPropertyOwnerOrManager])
    def finalize_unit_groups(self, request, pk=None):
        property_obj = self.get_object()
        groups_data = request.data.get('unit_groups', [])
        if not groups_data:
            return Response({"error": "No unit groups provided."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            created_groups = UnitGroupService.finalize_property_unit_groups(property=property_obj, user=request.user, groups_data=groups_data)
            serializer = prop_serializers.UnitGroupSerializer(created_groups, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Get Tenant Financials")
    @action(detail=True, methods=['get'], url_path='tenant-financials', permission_classes=[permissions.IsAuthenticated])
    def tenant_financials(self, request, pk=None):
        property_obj = self.get_object()
        tenancies = Tenancy.objects.filter(property=property_obj, status='active').select_related('tenant', 'tenant__profile', 'unit')
        data = []
        for tenancy in tenancies:
            tenant_user = tenancy.tenant
            nok = NextOfKin.objects.filter(user=tenant_user).first()
            nok_data = {"full_name": nok.full_name, "relationship": nok.relationship, "phone_number": nok.phone_number, "city": nok.city} if nok else None
            data.append({
                "tenant_id": tenant_user.id, "tenant_name": tenant_user.get_full_name() or tenant_user.email,
                "tenant_email": tenant_user.email, "tenant_phone": getattr(tenant_user, 'phone_number', ''),
                "property_name": property_obj.title, "unit_code": tenancy.unit.unit_code if tenancy.unit else "Unassigned",
                "rent_amount": float(tenancy.rent_amount), "deposit_amount": float(tenancy.deposit_amount),
                "service_charge": float(tenancy.service_charge_amount), "balance_due": 0, "arrears": 0,
                "last_payment_date": "", "last_payment_amount": 0, "next_billing_date": "",
                "tenancy_status": tenancy.status, "tenancy_start_date": str(tenancy.start_date) if hasattr(tenancy, 'start_date') else "",
                "tenancy_end_date": str(tenancy.end_date) if hasattr(tenancy, 'end_date') else "", "next_of_kin": nok_data
            })
        return Response(data, status=status.HTTP_200_OK)


class UnitGroupViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.UnitGroupSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDelegated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False): return UnitGroup.objects.none()
        property_pk = self.kwargs.get('property_pk')
        return UnitGroup.objects.filter(property_id=property_pk)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['property'] = Property.objects.get(id=self.kwargs.get('property_pk'))
        return context

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            UnitGroupService.delete_unit_group(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UnitViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.UnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False): return Unit.objects.none()
        property_pk = self.kwargs.get('property_pk')
        return Unit.objects.filter(property_ref_id=property_pk).select_related('property_ref', 'unit_group')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.kwargs.get('property_pk'):
            context['property'] = Property.objects.get(id=self.kwargs.get('property_pk'))
        return context

    def get_permissions(self):
        if self.action in ['list', 'retrieve'] and not self.request.user.is_authenticated:
            return [IsMarketplaceReadOnly()]
        
        if self.action == 'destroy':
            return [IsPropertyOwnerOrManager()]
            
        return [IsOwnerOrDelegated()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            UnitService.delete_unit(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(summary="Update Unit Status")
    @action(detail=True, methods=['PATCH'], permission_classes=[IsOwnerOrDelegated])
    def update_status(self, request, property_pk=None, pk=None):
        unit = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return Response({"error": "Status is required."}, status=status.HTTP_400_BAD_REQUEST)
        updated_unit = UnitService.update_unit_status(unit, new_status)
        return Response(prop_serializers.UnitSerializer(updated_unit).data, status=status.HTTP_200_OK)


class PropertyMediaViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.PropertyMediaSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDelegated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False): return PropertyMedia.objects.none()
        property_pk = self.kwargs.get('property_pk')
        return PropertyMedia.objects.filter(property_ref_id=property_pk)

    def perform_create(self, serializer):
        property_pk = self.kwargs.get('property_pk')
        property_obj = Property.objects.get(id=property_pk)
        serializer.save(property_ref=property_obj)