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
        property_obj = application.property
        
        # Check if the property is delegated to an agency
        if property_obj.current_manager and property_obj.current_manager.role == 'agency':
            # In a full implementation, we would query the AgencyStaff model to find 
            # an active 'agent' assigned to this specific property.
            # For now, we return the agency entity or a designated primary agent.
            # The ApprovalService will then enforce that this Agent can ONLY approve 
            # if all tenancy conditions are met, else it escalates to the Agency Manager.
            return {
                "role": "agent",
                "entity": property_obj.current_manager,
                "message": "Routed to assigned Agency Agent for initial review."
            }
        else:
            # Self-managed property: routes directly to the landlord/manager
            return {
                "role": "manager",
                "entity": property_obj.created_by, # Or current_manager if different
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
        ApplicationNote.objects.create(
            application=application,
            note_type=ApplicationNote.NoteType.ESCALATION_REASON,
            content=f"Escalated to Manager. Reason: {reason}",
            created_by=None # System-generated
        )