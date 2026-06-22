from django.db.models import Count, Q
from apps.tenancy.models import TenancyHistory, TenancyNote

class ScreeningService:
    """
    Aggregates tenant historical data and notes for application reviewers.
    Enforces strict visibility rules for confidential notes.
    """

    @staticmethod
    def get_tenant_screening_profile(tenant, reviewer):
        """
        Retrieves a comprehensive screening profile for a tenant, 
        including historical tenancies and behavioral notes.
        """
        # 1. Fetch Tenancy History
        history_records = TenancyHistory.objects.filter(
            tenant=tenant
        ).select_related('property', 'unit').order_by('-start_date')
        
        total_tenancies = history_records.count()
        termination_breakdown = list(
            history_records.values('final_status').annotate(count=Count('final_status'))
        )

        # 2. Fetch Tenancy Notes with Visibility Rules
        # Base query: notes linked to any tenancy belonging to this tenant
        notes_query = Q(tenancy__tenant=tenant)
        
        # Visibility Rule: Only Landlords, Agencies (Managers), and Admins can see confidential notes.
        # Agents and Caretakers will only see public/internal notes.
        is_elevated_reviewer = reviewer.role in ['admin', 'landlord', 'agency', 'manager']
        
        if not is_elevated_reviewer:
            notes_query &= Q(is_confidential=False)
            
        tenant_notes = TenancyNote.objects.filter(notes_query).select_related(
            'created_by', 'tenancy__unit'
        ).order_by('-created_at')

        # 3. Format the response for the frontend reviewer dashboard
        return {
            "tenant_id": tenant.id,
            "tenant_email": tenant.email,
            "total_historical_tenancies": total_tenancies,
            "termination_breakdown": termination_breakdown,
            "history_records": [
                {
                    "property_title": h.property.title,
                    "unit_code": h.unit.unit_code,
                    "start_date": h.start_date,
                    "end_date": h.end_date,
                    "final_status": h.final_status,
                    "termination_reason": h.termination_reason,
                    "manager_notes": h.manager_notes,
                    "performance_score": h.performance_score
                } for h in history_records
            ],
            "notes": [
                {
                    "note_type": n.note_type,
                    "content": n.content,
                    "is_confidential": n.is_confidential,
                    "created_by": n.created_by.email if n.created_by else "System",
                    "created_at": n.created_at,
                    "unit_context": n.tenancy.unit.unit_code if n.tenancy else "General"
                } for n in tenant_notes
            ]
        }