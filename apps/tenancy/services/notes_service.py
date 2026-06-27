from django.core.exceptions import PermissionDenied
from ..models import TenancyNote

class NotesService:
    """
    Manages internal, append-only communication and audit logs for tenancies.
    Enforces strict confidentiality rules for sensitive notes.
    
    Note Types:
    - general: General manager notes
    - behavior: Tenant behavior observations
    - payment: Payment-related notes
    - maintenance: Maintenance issue notes
    - handover: Handover instructions
    - financial: Financial notes (waivers, adjustments)
    """

    VALID_NOTE_TYPES = ['general', 'behavior', 'payment', 'maintenance', 'handover', 'financial']

    @staticmethod
    def create_note(
        tenancy, 
        user, 
        content: str, 
        note_type: str = 'general', 
        is_confidential: bool = False
    ) -> TenancyNote:
        """
        Creates a new note attached to a tenancy.
        """
        if note_type not in NotesService.VALID_NOTE_TYPES:
            note_type = 'general'
            
        return TenancyNote.objects.create(
            tenancy=tenancy,
            note_type=note_type,
            content=content,
            is_confidential=is_confidential,
            created_by=user
        )

    @staticmethod
    def get_visible_notes(tenancy, user) -> list:
        """
        Retrieves notes for a tenancy, filtering out confidential notes 
        if the user does not have elevated permissions (Admin, Landlord, or Property Manager).
        """
        # Base queryset
        notes = TenancyNote.objects.filter(tenancy=tenancy).select_related('created_by').order_by('-created_at')
        
        # Check if user has elevated permissions for this specific property
        is_elevated = NotesService._is_elevated_user(user, tenancy)
        
        # If not elevated, filter out confidential notes
        if not is_elevated:
            notes = notes.filter(is_confidential=False)
            
        return list(notes)

    @staticmethod
    def get_notes_for_application_review(tenant, reviewing_user) -> list:
        """
        Fetches notes linked to the tenant's tenancies for use in application review.
        Only returns notes visible to the reviewing user.
        """
        # Get all tenancies (past and present) for this tenant
        from ..models import Tenancy
        tenant_tenancies = Tenancy.objects.filter(tenant=tenant)
        
        # Get notes from all those tenancies
        notes = TenancyNote.objects.filter(
            tenancy__in=tenant_tenancies
        ).select_related('created_by', 'tenancy', 'tenancy__unit', 'tenancy__property')
        
        # Filter based on user's access level
        # For application review, we show all non-confidential notes
        notes = notes.filter(is_confidential=False).order_by('-created_at')[:10]
        
        return [
            {
                "id": n.id,
                "note_type": n.note_type,
                "content": n.content,
                "author": n.created_by.email if n.created_by else "System",
                "date": n.created_at.strftime('%Y-%m-%d') if n.created_at else "",
                "tenancy_unit": n.tenancy.unit.unit_code if n.tenancy and n.tenancy.unit else "",
                "property_name": n.tenancy.property.title if n.tenancy and n.tenancy.property else ""
            }
            for n in notes
        ]

    @staticmethod
    def _is_elevated_user(user, tenancy) -> bool:
        """
        Helper to determine if user has elevated permissions for a tenancy.
        """
        if user.role == 'admin':
            return True
        
        property_obj = tenancy.property
        if property_obj.created_by == user:
            return True
        if getattr(property_obj, 'current_manager', None) == user:
            return True
            
        # Check agency delegation
        if user.role in ['agency', 'agent']:
            try:
                from apps.agencies.models import DelegatedProperty
                return DelegatedProperty.objects.filter(
                    property_ref=property_obj,
                    agency__staff_members__user=user,
                    status='active'
                ).exists()
            except Exception:
                return False
                
        return False