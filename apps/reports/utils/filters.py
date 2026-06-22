from django.db.models import Q
from django.contrib.auth import get_user_model

User = get_user_model()

class ReportFilterUtils:
    """
    Reusable queryset filtering logic to ensure reports are strictly scoped 
    to the requesting user's role and property assignments.
    """

    @staticmethod
    def scope_properties_by_user(user, queryset):
        """
        Filters a Property or Unit queryset to only include what the user is allowed to see.
        """
        if user.role == 'admin':
            return queryset # Admin sees everything
            
        if user.role == 'landlord':
            return queryset.filter(created_by=user)
            
        if user.role in ['agency', 'manager']:
            # Agency/Manager sees properties they own OR properties delegated to them
            return queryset.filter(
                Q(created_by=user) | Q(current_manager=user)
            ).distinct()
            
        if user.role == 'agent':
            # Agents only see properties assigned to their parent agency
            if hasattr(user, 'agency') and user.agency:
                return queryset.filter(current_manager=user.agency)
            return queryset.none()
            
        if user.role == 'caretaker':
            # Caretakers only see properties they are directly assigned to
            return queryset.filter(caretaker=user)
            
        if user.role == 'tenant':
            # Tenants only see the specific units/properties they occupy
            from tenancy.models import Tenancy
            occupied_units = Tenancy.objects.filter(tenant=user, status__in=['active', 'extended']).values_list('unit__property', flat=True)
            return queryset.filter(id__in=occupied_units).distinct()
            
        return queryset.none()

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