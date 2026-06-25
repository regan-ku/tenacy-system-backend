from django.db.models import Count
from django.utils import timezone
from ..models import TenancyHistory, TenancyNote

class HistoryService:
    """
    Manages querying and reporting of historical tenancy data.
    Critical for tenant background checks, landlord references, and system analytics.
    """

    @staticmethod
    def get_tenant_rental_history(tenant_id, limit: int = 10):
        """
        Retrieves a chronological history of all past tenancies for a specific tenant.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            tenant = User.objects.get(id=tenant_id)
        except User.DoesNotExist:
            return []
            
        return TenancyHistory.objects.filter(
            tenant=tenant
        ).select_related(
            'unit', 'property'
        ).order_by('-start_date')[:limit]

    @staticmethod
    def get_tenant_history_summary(tenant_id):
        """
        ✅ NEW: Generates a summary matching the frontend's TenantHistorySummary interface.
        Safely handles new tenants with no history by returning the expected empty shape.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            tenant = User.objects.get(id=tenant_id)
        except User.DoesNotExist:
            return {
                "total_past_tenancies": 0,
                "average_stay_duration_months": 0,
                "payment_reliability_score": "New Applicant",
                "notes": []
            }

        history = TenancyHistory.objects.filter(tenant=tenant)
        total_past_tenancies = history.count()

        # ✅ CRITICAL: If no history, return the exact shape the frontend expects
        if total_past_tenancies == 0:
            return {
                "total_past_tenancies": 0,
                "average_stay_duration_months": 0,
                "payment_reliability_score": "New Applicant",
                "notes": []
            }

        # Calculate average stay duration in months
        total_months = 0
        valid_tenancies = 0
        for h in history:
            if h.start_date:
                end = h.end_date or timezone.now().date()
                delta = end - h.start_date
                months = delta.days / 30.44
                total_months += months
                valid_tenancies += 1
        
        avg_months = round(total_months / valid_tenancies, 1) if valid_tenancies > 0 else 0

        # Simple reliability score based on terminations
        bad_terminations = history.filter(final_status__in=['breach', 'evicted', 'terminated_by_landlord']).count()
        if bad_terminations == 0:
            score = "Excellent"
        elif bad_terminations <= 1:
            score = "Good"
        else:
            score = "Fair"

        # Fetch notes linked to the tenant's tenancies
        notes_qs = TenancyNote.objects.filter(tenancy__tenant=tenant).order_by('-created_at')[:5]
        notes = [{"note_type": n.note_type, "content": n.content} for n in notes_qs]

        return {
            "total_past_tenancies": total_past_tenancies,
            "average_stay_duration_months": avg_months,
            "payment_reliability_score": score,
            "notes": notes
        }

    @staticmethod
    def get_property_occupancy_history(property_obj, years: int = 2):
        """
        Retrieves occupancy history for a specific property.
        """
        cutoff = timezone.now() - timezone.timedelta(days=years * 365)
        
        return TenancyHistory.objects.filter(
            property=property_obj,
            end_date__gte=cutoff
        ).select_related('tenant', 'unit').order_by('-end_date')