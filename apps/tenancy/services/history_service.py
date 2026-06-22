from django.db.models import Count
from ..models import TenancyHistory

class HistoryService:
    """
    Manages querying and reporting of historical tenancy data.
    Critical for tenant background checks, landlord references, and system analytics.
    """

    @staticmethod
    def get_tenant_rental_history(tenant, limit: int = 10):
        """
        Retrieves a chronological history of all past tenancies for a specific tenant.
        Used for generating rental references or background checks.
        """
        return TenancyHistory.objects.filter(
            tenant=tenant
        ).select_related(
            'unit', 'property'
        ).order_by('-start_date')[:limit]

    @staticmethod
    def get_property_occupancy_history(property_obj, years: int = 2):
        """
        Retrieves occupancy history for a specific property to calculate 
        vacancy rates and tenant turnover for landlord analytics.
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff = timezone.now() - timedelta(days=years * 365)
        
        return TenancyHistory.objects.filter(
            property=property_obj,
            end_date__gte=cutoff
        ).select_related('tenant', 'unit').order_by('-end_date')

    @staticmethod
    def generate_tenant_summary(tenant):
        """
        Generates a quick summary of a tenant's historical performance 
        (e.g., total properties rented, average stay duration, termination reasons).
        """
        history = TenancyHistory.objects.filter(tenant=tenant)
        
        total_tenancies = history.count()
        if total_tenancies == 0:
            return {"status": "New Tenant", "total_tenancies": 0}
            
        # Count termination types
        terminations = history.values('final_status').annotate(count=Count('final_status'))
        
        return {
            "total_tenancies": total_tenancies,
            "termination_breakdown": list(terminations),
            "has_history": True
        }