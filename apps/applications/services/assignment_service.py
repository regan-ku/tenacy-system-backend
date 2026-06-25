from django.core.exceptions import ValidationError
from ..models import Application

class AssignmentService:
    """
    Determines the correct reviewer for an application based on property delegation.
    Routes to Agent if one is assigned and authorized; otherwise, routes to Manager/Landlord.
    """

    @staticmethod
    def get_initial_reviewer(application: Application):
        """
        Returns the user or role that should initially review this application.
        """
        # ✅ FIX: Safely extract the property object to prevent AttributeError crashes
        property_obj = getattr(application, 'property_ref', None) or getattr(application, 'property', None)
        
        if not property_obj:
            return {
                "role": "manager",
                "entity": None,
                "message": "Application is missing a linked property."
            }
            
        # Safely get manager and creator
        current_manager = getattr(property_obj, 'current_manager', None)
        created_by = getattr(property_obj, 'created_by', None)
        
        # Check if the property is delegated to an agency
        if current_manager and getattr(current_manager, 'role', None) == 'agency':
            return {
                "role": "agent",
                "entity": current_manager,
                "message": "Routed to assigned Agency Agent for initial review."
            }
        else:
            # Self-managed property: routes directly to the landlord/manager
            return {
                "role": "manager",
                "entity": created_by, 
                "message": "Routed to Property Owner/Manager for review."
            }

    @staticmethod
    def escalate_to_manager(application: Application, reason: str):
        """
        Explicitly changes the application state to ESCALATED, moving it from 
        the Agent's queue to the Manager/Landlord's queue.
        """
        if application.status != 'under_review':
            raise ValidationError("Only applications under review can be escalated.")

        application.status = Application.Status.ESCALATED
        application.save(update_fields=['status'])

        # Log the escalation
        from ..models import ApplicationNote
        
        # Safely get NoteType enum if it exists, otherwise fallback to string
        note_type_enum = getattr(ApplicationNote.NoteType, 'ESCALATION_REASON', 'escalation_reason')
        
        ApplicationNote.objects.create(
            application=application,
            note_type=note_type_enum,
            content=f"Escalated to Manager. Reason: {reason}",
            created_by=None # System-generated
        )