from django.db.models import Count, Q
from apps.tenancy.models import TenancyHistory, TenancyNote

class ScreeningService:
    """
    Aggregates tenant historical data and notes for application reviewers.
    """

    @staticmethod
    def get_tenant_screening_profile(tenant, reviewer):
        # 1. Fetch Tenancy History
        history_records = TenancyHistory.objects.filter(
            tenant=tenant
        ).select_related('property', 'unit').order_by('-start_date')
        
        total_tenancies = history_records.count()
        
        # ✅ FIX: Safely aggregate termination breakdown in case 'final_status' field is missing
        try:
            termination_breakdown = list(
                history_records.values('final_status').annotate(count=Count('final_status'))
            )
        except Exception:
            termination_breakdown = []

        # 2. Fetch Tenancy Notes with Visibility Rules
        notes_query = Q(tenancy__tenant=tenant)
        is_elevated_reviewer = reviewer.role in ['admin', 'landlord', 'agency', 'manager']
        
        if not is_elevated_reviewer:
            notes_query &= Q(is_confidential=False)
            
        tenant_notes = TenancyNote.objects.filter(notes_query).select_related(
            'created_by', 'tenancy__unit'
        ).order_by('-created_at')

        # 3. Format the response for the frontend reviewer dashboard
        # ✅ FIX: Used getattr() for all history fields to prevent AttributeError crashes 
        # if the TenancyHistory model is missing columns like 'performance_score' or 'manager_notes'
        return {
            "tenant_id": tenant.id,
            "tenant_email": tenant.email,
            "total_historical_tenancies": total_tenancies,
            "termination_breakdown": termination_breakdown,
            "history_records": [
                {
                    "property_title": getattr(h.property, 'title', 'Unknown Property') if h.property else 'Unknown',
                    "unit_code": getattr(h.unit, 'unit_code', 'Unknown Unit') if h.unit else 'Unknown',
                    "start_date": h.start_date,
                    "end_date": h.end_date,
                    "final_status": getattr(h, 'final_status', 'N/A'),
                    "termination_reason": getattr(h, 'termination_reason', ''),
                    "manager_notes": getattr(h, 'manager_notes', ''),
                    "performance_score": getattr(h, 'performance_score', None)
                } for h in history_records
            ],
            "notes": [
                {
                    "note_type": n.note_type,
                    "content": n.content,
                    "is_confidential": getattr(n, 'is_confidential', False),
                    "created_by": n.created_by.email if n.created_by else "System",
                    "created_at": n.created_at,
                    "unit_context": n.tenancy.unit.unit_code if n.tenancy and n.tenancy.unit else "General"
                } for n in tenant_notes
            ]
        }