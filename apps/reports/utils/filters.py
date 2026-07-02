from django.db.models import Q
from django.contrib.auth import get_user_model
from django.apps import apps

User = get_user_model()

class ReportFilterUtils:
    """
    Universal data scoping utility for the Reports and Dashboards apps.
    Ensures strict role-based data isolation across all aggregators.
    """

    @staticmethod
    def scope_properties_by_user(user, base_queryset=None):
        """
        Filters a Property queryset to only include what the user is allowed to see.
        """
        if base_queryset is None:
            Property = apps.get_model('properties', 'Property')
            base_queryset = Property.objects.all()

        # 1. SYSTEM ADMINISTRATOR
        if user.role == 'admin':
            return base_queryset

        # 2. LANDLORD
        # Landlords see all properties they created, regardless of whether 
        # they have delegated operational control to an agency.
        elif user.role == 'landlord':
            return base_queryset.filter(created_by=user)

        # 3. AGENCY
        # Agencies see properties they own AND properties delegated to them.
        elif user.role == 'agency':
            Agency = apps.get_model('agencies', 'Agency')
            
            # Find all agencies this user is associated with (Owner, Director, or Staff)
            user_agencies = Agency.objects.filter(
                Q(created_by=user) | 
                Q(directors__user=user) | 
                Q(staff_members__user=user, staff_members__status='active')
            )
            
            return base_queryset.filter(
                Q(created_by=user) | 
                Q(agency_delegations__agency__in=user_agencies, agency_delegations__status='active')
            ).distinct()

        # 4. STAFF (Agent, Caretaker, Property Manager)
        # Staff only see properties they are explicitly assigned to via PropertyStaffAssignment.
        elif user.role in ['agent', 'caretaker', 'property_manager']:
            return base_queryset.filter(
                staff_assignments__user=user,
                staff_assignments__is_active=True
            ).distinct()

        # 5. TENANT
        # Tenants only see properties where they hold an active tenancy.
        elif user.role == 'tenant':
            return base_queryset.filter(
                units__tenancies__tenant=user,
                units__tenancies__status__in=['active', 'extended', 'pending_payment']
            ).distinct()

        # Fallback for unknown roles (returns empty queryset)
        return base_queryset.none()

    @staticmethod
    def apply_date_range(queryset, date_field: str, start_date=None, end_date=None):
        """
        Applies a date range filter to a queryset safely.
        """
        filters = Q()
        if start_date:
            filters &= Q(**{f"{date_field}__gte": start_date})
        if end_date:
            filters &= Q(**{f"{date_field}__lte": end_date})
            
        return queryset.filter(filters) if filters else queryset