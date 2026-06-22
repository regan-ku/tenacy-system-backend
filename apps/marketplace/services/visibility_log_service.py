from django.db import transaction
from ..models import MarketplaceVisibilityLog, PropertyPublication

class VisibilityLogService:
    """
    Provides an immutable audit trail for all property publication and visibility changes.
    Critical for compliance, dispute resolution, and tracking marketplace exposure.
    """

    @staticmethod
    @transaction.atomic
    def log_action(property, publication: PropertyPublication, action: str, performed_by, reason: str = ""):
        """
        Creates an immutable log entry for a visibility change.
        """
        return MarketplaceVisibilityLog.objects.create(
            property=property,
            publication=publication,
            action=action,
            performed_by=performed_by,
            reason=reason
        )

    @staticmethod
    def get_property_visibility_history(property, limit: int = 20):
        """
        Retrieves the audit trail of visibility changes for a specific property.
        """
        return MarketplaceVisibilityLog.objects.filter(
            property=property
        ).select_related('performed_by').order_by('-timestamp')[:limit]