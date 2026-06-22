from django.utils import timezone
from ..models import AgencyActivityLog

class ActivityService:
    """
    Centralized service for logging all agency-related actions.
    Ensures a complete, immutable audit trail for compliance and security.
    """

    @staticmethod
    def log_action(
        agency,
        action_type: str,
        performed_by,
        target_user=None,
        details: dict = None,
        ip_address: str = None
    ) -> AgencyActivityLog:
        """
        Creates an immutable audit log entry.
        
        Args:
            agency: The Agency instance this action relates to.
            action_type: String matching AgencyActivityLog.ActionType choices.
            performed_by: The User instance who performed the action.
            target_user: (Optional) The User instance the action was performed on.
            details: (Optional) Dictionary of structured data about the action.
            ip_address: (Optional) IP address of the requester.
        """
        return AgencyActivityLog.objects.create(
            agency=agency,
            action_type=action_type,
            performed_by=performed_by,
            target_user=target_user,
            details=details or {},
            ip_address=ip_address,
            timestamp=timezone.now()
        )

    @staticmethod
    def get_recent_activity(agency, limit: int = 50):
        """
        Retrieves the most recent activity logs for an agency dashboard.
        """
        return AgencyActivityLog.objects.filter(agency=agency).select_related(
            'performed_by', 'target_user'
        ).order_by('-timestamp')[:limit]