from django.core.exceptions import PermissionDenied
from ..models import TenancyNote

class NotesService:
    """
    Manages internal, append-only communication and audit logs for tenancies.
    Enforces strict confidentiality rules for sensitive notes.
    """

    @staticmethod
    def create_note(tenancy, user, content: str, note_type: str = 'general', is_confidential: bool = False) -> TenancyNote:
        """
        Creates a new note attached to a tenancy.
        """
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
        is_elevated = (
            user.role == 'admin' or 
            tenancy.property.created_by == user or 
            tenancy.property.current_manager == user
        )
        
        # If not elevated, filter out confidential notes
        if not is_elevated:
            notes = notes.filter(is_confidential=False)
            
        return notes