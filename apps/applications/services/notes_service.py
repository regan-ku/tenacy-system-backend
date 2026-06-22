from django.core.exceptions import PermissionDenied
from ..models import ApplicationNote

class NotesService:
    """
    Manages internal notes added during the application review process.
    Enforces strict confidentiality rules based on the viewer's role.
    """

    @staticmethod
    def create_note(application, user, content: str, note_type: str = 'agent_review', is_confidential: bool = False) -> ApplicationNote:
        """
        Creates a new note attached to an application.
        """
        # Only Managers, Landlords, and Admins can create confidential notes
        if is_confidential and user.role not in ['manager', 'landlord', 'admin', 'agency']:
            raise PermissionDenied("Only Managers, Landlords, or Admins can create confidential notes.")

        return ApplicationNote.objects.create(
            application=application,
            note_type=note_type,
            content=content,
            is_confidential=is_confidential,
            created_by=user
        )

    @staticmethod
    def get_visible_notes(application, user) -> list:
        """
        Retrieves notes for an application, filtering out confidential notes 
        if the user is a standard Agent or Caretaker.
        """
        notes = ApplicationNote.objects.filter(application=application).select_related('created_by').order_by('-created_at')
        
        # Check if user has elevated permissions
        is_elevated = user.role in ['admin', 'landlord', 'agency', 'manager']
        
        # If not elevated, filter out confidential notes
        if not is_elevated:
            notes = notes.filter(is_confidential=False)
            
        return notes