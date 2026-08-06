from rest_framework import viewsets, status, permissions, parsers, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from django.core.exceptions import ValidationError
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiResponse,
    OpenApiParameter,
    OpenApiTypes,
)

from django.db.models import Q, Prefetch, Count
from django.contrib.auth import get_user_model

from . import serializers as prop_serializers
from ..models import Property, UnitGroup, Unit, PropertyMedia
from ..models.staff_assignment import PropertyStaffAssignment
from ..models.enums import UnitStatus
from ..services import UnitGroupService, UnitService, PropertyService
from ..permissions.property_permissions import (
    IsPropertyOwnerOrManager,
    IsDelegatedAgencyStaff,
    IsMarketplaceReadOnly,
)
from apps.tenancy.models.tenancy import Tenancy
from apps.accounts.models.next_of_kin import NextOfKin

from apps.agencies.models.agency import Agency
from apps.agencies.models.delegated_property import DelegatedProperty

User = get_user_model()


# ==========================================
# CONSTANTS
# ==========================================

ACTIVE_TENANCY_STATUSES = [
    "active",
    "extended",
    "pending_payment",
]


# ==========================================
# HELPER: TENANT MANAGEMENT SCOPE
# ==========================================

def get_tenant_managed_property_q_filters(user):
    """
    Returns Q filters for properties that a tenant should be allowed to see.

    Business Rule:
    - A tenant should only see properties under the same management scope
      as their current active tenancy.
    - Same management means:
      1. Same property owner / creator
      2. Same current manager
      3. Same delegated agency, if the current property is agency-managed
    """
    if not user or not user.is_authenticated:
        return None, None

    if getattr(user, "role", None) != "tenant":
        return None, None

    active_tenancy = (
        Tenancy.objects.filter(
            tenant=user,
            status__in=ACTIVE_TENANCY_STATUSES,
        )
        .select_related(
            "property",
            "property__created_by",
            "property__current_manager",
            "unit",
        )
        .order_by("-id")
        .first()
    )

    if not active_tenancy or not active_tenancy.property:
        return None, None

    current_property = active_tenancy.property

    q_filters = Q(id=current_property.id)

    # Same landlord / owner
    if getattr(current_property, "created_by_id", None):
        q_filters |= Q(created_by=current_property.created_by)

    # Same direct manager
    if getattr(current_property, "current_manager_id", None):
        q_filters |= Q(current_manager=current_property.current_manager)

    # Same delegated agency, if applicable
    try:
        active_delegation = (
            current_property.agency_delegations.filter(status="active")
            .select_related("agency")
            .first()
        )

        if active_delegation and active_delegation.agency:
            q_filters |= Q(
                agency_delegations__agency=active_delegation.agency,
                agency_delegations__status="active",
            )
    except Exception:
        # If delegation relation is unavailable, fail safely to owner/manager scope only
        pass

    return q_filters, active_tenancy


# ==========================================
# PERMISSIONS
# ==========================================

class IsOwnerOrDelegated(BasePermission):
    """
    Allows access if the user is the property owner/manager OR a delegated agency staff.

    Updated:
    - Tenants can safely read property lists scoped by get_queryset().
    - Tenants are blocked from creating/updating/deleting property records.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Allow read-style access for authenticated users.
        # The queryset still enforces role-based visibility.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Tenants should never create/update/delete properties or units.
        return getattr(request.user, "role", None) != "tenant"

    def has_object_permission(self, request, view, obj):
        property_obj = getattr(obj, "property_ref", None) or getattr(obj, "property", None)

        if obj.__class__.__name__ == "Property":
            property_obj = obj

        if not property_obj:
            return False

        if property_obj.created_by == request.user:
            return True

        if getattr(property_obj, "current_manager", None) == request.user:
            return True

        try:
            return IsDelegatedAgencyStaff().has_object_permission(request, view, property_obj)
        except Exception:
            return False


class UnitStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=UnitStatus.choices)


# ==========================================
# PROPERTY VIEWSET
# ==========================================

@extend_schema_view(
    list=extend_schema(summary="List Properties"),
    retrieve=extend_schema(summary="Get Property Details"),
    create=extend_schema(summary="Create Property"),
    update=extend_schema(summary="Update Property"),
)
class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.PropertySerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDelegated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Property.objects.none()

        if not self.request.user.is_authenticated:
            return Property.objects.none()

        user = self.request.user

        # ==========================================
        # ADMIN SCOPE
        # ==========================================
        if user.role == "admin":
            qs = Property.objects.all()

        # ==========================================
        # ✅ TENANT SCOPE
        # ==========================================
        elif getattr(user, "role", None) == "tenant":
            q_filters, active_tenancy = get_tenant_managed_property_q_filters(user)

            if not q_filters:
                return Property.objects.none()

            qs = Property.objects.filter(q_filters)

        # ==========================================
        # LANDLORD / AGENCY / STAFF SCOPE
        # ==========================================
        else:
            q_filters = Q(created_by=user) | Q(current_manager=user)

            if user.role == "agency":
                agency = Agency.objects.filter(
                    Q(created_by=user)
                    | Q(directors__user=user)
                    | Q(staff_members__user=user, staff_members__status="active")
                ).first()

                if agency:
                    q_filters |= Q(
                        agency_delegations__agency=agency,
                        agency_delegations__status="active",
                    )

            if user.role in ["agent", "caretaker", "property_manager"]:
                q_filters |= Q(
                    staff_assignments__user=user,
                    staff_assignments__is_active=True,
                )

            qs = Property.objects.filter(q_filters)

        qs = qs.select_related(
            "location",
            "created_by",
            "created_by__profile",
        )

        # Avoid duplicates caused by delegation/staff joins
        qs = qs.distinct()

        # ==========================================
        # 🚀 PERFORMANCE FIX: ANNOTATE COUNTS TO PREVENT N+1 QUERIES
        # ==========================================
        qs = qs.annotate(
            total_units_count=Count("units", distinct=True),
            occupied_units_count=Count(
                "units",
                filter=Q(
                    units__tenancies__status__in=[
                        "active",
                        "extended",
                        "pending_payment",
                    ]
                ),
                distinct=True,
            ),
            available_units_count=Count(
                "units",
                filter=Q(units__status="available"),
                distinct=True,
            ),
        )

        # ==========================================
        # ✅ TENANT TRANSFER MODE: ONLY PROPERTIES WITH AVAILABLE UNITS
        # ==========================================
        # For tenant property lists, hide properties that have zero available units.
        # If you ever need to show all properties to a tenant, pass:
        # ?include_unavailable=true
        if (
            getattr(user, "role", None) == "tenant"
            and self.action == "list"
            and self.request.query_params.get("include_unavailable") != "true"
        ):
            qs = qs.filter(available_units_count__gt=0)

        # ==========================================
        # OPTIONAL ROLE FILTER FOR STAFF ASSIGNMENTS
        # ==========================================
        available_for_role = self.request.query_params.get("available_for_role")

        if available_for_role:
            excluded_ids = list(
                PropertyStaffAssignment.objects.filter(
                    operational_role=available_for_role,
                    is_active=True,
                ).values_list("property_id", flat=True)
            )

            if excluded_ids:
                qs = qs.exclude(id__in=excluded_ids)

        # Prefetch delegation info for serializer if agency
        if user.role == "agency":
            agency = Agency.objects.filter(
                Q(created_by=user)
                | Q(directors__user=user)
                | Q(staff_members__user=user, staff_members__status="active")
            ).first()

            if agency:
                qs = qs.prefetch_related(
                    Prefetch(
                        "agency_delegations",
                        queryset=DelegatedProperty.objects.filter(
                            agency=agency,
                            status="active",
                        ),
                        to_attr="active_agency_delegation",
                    )
                )

        return qs

    def perform_create(self, serializer):
        serializer.save()

    # ==========================================
    # ✅ STAFF ASSIGNMENT ENDPOINTS
    # ==========================================

    @extend_schema(
        summary="Get Property Staff",
        responses={200: prop_serializers.PropertyStaffAssignmentSerializer(many=True)},
    )
    @action(
        detail=True,
        methods=["GET"],
        url_path="staff",
        permission_classes=[IsOwnerOrDelegated],
    )
    def get_staff(self, request, pk=None):
        property_obj = self.get_object()
        staff = PropertyService.get_property_staff(property_obj)
        serializer = prop_serializers.PropertyStaffAssignmentSerializer(staff, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Assign Staff to Property",
        request=prop_serializers.AssignStaffRequestSerializer,
        responses={201: prop_serializers.PropertyStaffAssignmentSerializer},
    )
    @action(
        detail=True,
        methods=["POST"],
        url_path="staff/assign",
        permission_classes=[IsPropertyOwnerOrManager],
    )
    def assign_staff(self, request, pk=None):
        property_obj = self.get_object()
        serializer = prop_serializers.AssignStaffRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        operational_role = serializer.validated_data["operational_role"]
        notes = serializer.validated_data.get("notes")

        try:
            user_to_assign = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            assignment = PropertyService.assign_staff_to_property(
                property_obj=property_obj,
                user_to_assign=user_to_assign,
                assigning_user=request.user,
                operational_role=operational_role,
                notes=notes,
            )
            out_serializer = prop_serializers.PropertyStaffAssignmentSerializer(assignment)
            return Response(out_serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        summary="Terminate Staff Assignment",
        responses={200: OpenApiResponse(description="Assignment terminated")},
    )
    @action(
        detail=True,
        methods=["POST"],
        url_path=r"staff/(?P<user_id>[^/.]+)/terminate",
        permission_classes=[IsPropertyOwnerOrManager],
    )
    def terminate_staff(self, request, pk=None, user_id=None):
        property_obj = self.get_object()

        try:
            user_to_remove = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            PropertyService.terminate_staff_assignment(
                property_obj=property_obj,
                user_to_remove=user_to_remove,
                assigning_user=request.user,
            )
            return Response(
                {"message": "Staff assignment terminated successfully."},
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ==========================================
    # UNIT GROUP / UNIT GENERATION
    # ==========================================

    @extend_schema(summary="Generate Units from Group")
    @action(
        detail=True,
        methods=["POST"],
        url_path=r"unit-groups/(?P<group_pk>[^/.]+)/generate",
        permission_classes=[IsPropertyOwnerOrManager],
    )
    def generate_units(self, request, pk=None, group_pk=None):
        property_obj = self.get_object()

        try:
            unit_group = UnitGroup.objects.get(id=group_pk, property=property_obj)
        except UnitGroup.DoesNotExist:
            return Response(
                {"error": "Unit group not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        units = UnitGroupService.generate_units_from_group(unit_group, request.user)
        serializer = prop_serializers.UnitSerializer(units, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="Finalize Unit Groups & Generate Units")
    @action(
        detail=True,
        methods=["POST"],
        url_path="finalize-unit-groups",
        permission_classes=[IsPropertyOwnerOrManager],
    )
    def finalize_unit_groups(self, request, pk=None):
        property_obj = self.get_object()
        groups_data = request.data.get("unit_groups", [])

        if not groups_data:
            return Response(
                {"error": "No unit groups provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            created_groups = UnitGroupService.finalize_property_unit_groups(
                property=property_obj,
                user=request.user,
                groups_data=groups_data,
            )
            serializer = prop_serializers.UnitGroupSerializer(created_groups, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ==========================================
    # ✅ FINALIZE PROPERTY WIZARD
    # ==========================================

    @extend_schema(summary="Finalize Property Wizard (Activate)")
    @action(
        detail=True,
        methods=["POST"],
        url_path="finalize",
        permission_classes=[IsPropertyOwnerOrManager],
    )
    def finalize_wizard(self, request, pk=None):
        """
        Endpoint for the frontend to call when the Property Wizard is 100% complete.
        Flips is_active to True safely after backend validation.
        """
        property_obj = self.get_object()

        try:
            updated_property = PropertyService.finalize_property_wizard(
                property_obj,
                request.user,
            )
            return Response(
                {
                    "message": "Property wizard completed. Property is now active.",
                    "is_active": updated_property.is_active,
                    "is_marketplace_ready": updated_property.is_marketplace_ready,
                },
                status=status.HTTP_200_OK,
            )
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ==========================================
    # ✅ TENANT FINANCIALS
    # ==========================================

    @extend_schema(summary="Get Tenant Financials")
    @action(
        detail=True,
        methods=["GET"],
        url_path="tenant-financials",
        permission_classes=[IsOwnerOrDelegated],
    )
    def tenant_financials(self, request, pk=None):
        """
        Manager-only endpoint.

        Updated:
        - Previously this allowed any authenticated user.
        - Now it is locked behind IsOwnerOrDelegated so tenants cannot access
          financial summaries for properties they do not manage.
        """
        property_obj = self.get_object()

        tenancies = (
            Tenancy.objects.filter(
                property=property_obj,
                status="active",
            )
            .select_related(
                "tenant",
                "tenant__profile",
                "unit",
            )
        )

        data = []

        for tenancy in tenancies:
            tenant_user = tenancy.tenant
            profile = getattr(tenant_user, "profile", None)
            tenant_name = getattr(profile, "full_name", None) or "Unnamed Tenant"

            nok = NextOfKin.objects.filter(user=tenant_user).first()

            nok_data = None
            if nok:
                nok_data = {
                    "full_name": nok.full_name,
                    "relationship": nok.relationship,
                    "phone_number": nok.phone_number,
                    "city": nok.city,
                }

            data.append(
                {
                    "tenancy_id": tenancy.id,
                    "tenant_id": tenant_user.id,
                    "tenant_name": tenant_name,
                    "tenant_email": tenant_user.email,
                    "tenant_phone": getattr(tenant_user, "phone_number", "")
                    or (getattr(profile, "phone_number", "") if profile else ""),
                    "property_name": property_obj.title,
                    "unit_code": tenancy.unit.unit_code if tenancy.unit else "Unassigned",
                    "rent_amount": float(tenancy.rent_amount),
                    "deposit_amount": float(tenancy.deposit_amount),
                    "service_charge": float(tenancy.service_charge_amount),
                    "balance_due": 0,
                    "arrears": 0,
                    "last_payment_date": "",
                    "last_payment_amount": 0,
                    "next_billing_date": "",
                    "tenancy_status": tenancy.status,
                    "tenancy_start_date": str(tenancy.start_date)
                    if hasattr(tenancy, "start_date")
                    else "",
                    "tenancy_end_date": str(tenancy.end_date)
                    if hasattr(tenancy, "end_date")
                    else "",
                    "next_of_kin": nok_data,
                }
            )

        return Response(data, status=status.HTTP_200_OK)


# ==========================================
# UNIT GROUP VIEWSET
# ==========================================

class UnitGroupViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.UnitGroupSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDelegated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return UnitGroup.objects.none()

        property_pk = self.kwargs.get("property_pk")

        return UnitGroup.objects.filter(property_id=property_pk).annotate(
            actual_units_count=Count("units", distinct=True),
            occupied_units_count=Count(
                "units",
                filter=Q(
                    units__tenancies__status__in=[
                        "active",
                        "extended",
                        "pending_payment",
                    ]
                ),
                distinct=True,
            ),
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["property"] = Property.objects.get(id=self.kwargs.get("property_pk"))
        return context

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        try:
            UnitGroupService.delete_unit_group(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# UNIT VIEWSET
# ==========================================

class UnitViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.UnitSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]
    pagination_class = None

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Unit.objects.none()

        property_pk = self.kwargs.get("property_pk")

        qs = Unit.objects.filter(property_ref_id=property_pk).select_related(
            "property_ref",
            "unit_group",
        )

        user = self.request.user

        # ==========================================
        # ✅ TENANT UNIT SCOPE
        # ==========================================
        # Tenants should only see:
        # 1. Units inside properties under their current management scope
        # 2. Units that are available / unoccupied
        #
        # Their own current unit is excluded because it is occupied and
        # should not be selectable as a transfer destination.
        if user and user.is_authenticated and getattr(user, "role", None) == "tenant":
            q_filters, active_tenancy = get_tenant_managed_property_q_filters(user)

            if not q_filters:
                return Unit.objects.none()

            allowed_property_ids = (
                Property.objects.filter(q_filters)
                .distinct()
                .values("id")
            )

            qs = qs.filter(property_ref_id__in=allowed_property_ids)

            # Default tenant behavior: only available units.
            qs = qs.filter(status="available")

            # Extra safety: exclude tenant's current unit if it somehow has available status.
            if active_tenancy and active_tenancy.unit_id:
                qs = qs.exclude(id=active_tenancy.unit_id)

        # ==========================================
        # PUBLIC / MARKETPLACE SCOPE
        # ==========================================
        elif not user or not user.is_authenticated:
            qs = qs.filter(status="available")

        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()

        if self.kwargs.get("property_pk"):
            context["property"] = Property.objects.get(id=self.kwargs.get("property_pk"))

        return context

    def get_permissions(self):
        if not self.request.user.is_authenticated:
            if self.action in ["list", "retrieve"]:
                return [IsMarketplaceReadOnly()]
            return [permissions.IsAuthenticated()]

        if self.action in ["list", "retrieve"]:
            return [permissions.IsAuthenticated()]

        if self.action == "destroy":
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
    @action(
        detail=True,
        methods=["PATCH"],
        permission_classes=[IsOwnerOrDelegated],
    )
    def update_status(self, request, property_pk=None, pk=None):
        unit = self.get_object()
        new_status = request.data.get("status")

        if not new_status:
            return Response(
                {"error": "Status is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_unit = UnitService.update_unit_status(unit, new_status)

        return Response(
            prop_serializers.UnitSerializer(updated_unit).data,
            status=status.HTTP_200_OK,
        )


# ==========================================
# PROPERTY MEDIA VIEWSET
# ==========================================

class PropertyMediaViewSet(viewsets.ModelViewSet):
    serializer_class = prop_serializers.PropertyMediaSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrDelegated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return PropertyMedia.objects.none()

        property_pk = self.kwargs.get("property_pk")

        qs = PropertyMedia.objects.filter(property_ref_id=property_pk)

        user = self.request.user

        # If tenant accesses media, restrict to properties in their management scope.
        if user and user.is_authenticated and getattr(user, "role", None) == "tenant":
            q_filters, active_tenancy = get_tenant_managed_property_q_filters(user)

            if not q_filters:
                return PropertyMedia.objects.none()

            allowed_property_ids = (
                Property.objects.filter(q_filters)
                .distinct()
                .values("id")
            )

            qs = qs.filter(property_ref_id__in=allowed_property_ids)

        return qs

    def perform_create(self, serializer):
        property_pk = self.kwargs.get("property_pk")
        property_obj = Property.objects.get(id=property_pk)
        serializer.save(property_ref=property_obj)