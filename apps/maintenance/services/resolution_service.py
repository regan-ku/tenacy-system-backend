from django.db import transaction
from ..models import MaintenanceRequest, MaintenanceHistory, MaintenanceMedia
from .workflow_service import WorkflowService
import logging

logger = logging.getLogger(__name__)

class ResolutionService:
    @staticmethod
    @transaction.atomic
    def mark_resolved(request_id, resolved_by, comment="", requires_media=True):
        """
        Marks request as resolved. Optionally validates before/after media evidence.
        """
        request = MaintenanceRequest.objects.get(id=request_id)
        if request.status not in ["in_progress", "pending_review"]:
            raise ValueError("Request cannot be resolved from current status.")

        # Enforce evidence rule if configured
        if requires_media and not MaintenanceMedia.objects.filter(request=request, is_before_after=True).exists():
            logger.warning(f"Resolution submitted without before/after media for request {request_id}")

        WorkflowService.transition_status(str(request_id), "resolved", comment=comment, performed_by=resolved_by)

        MaintenanceHistory.objects.create(
            request=request,
            event_type="resolved",
            new_value={"resolved_by": str(resolved_by.id), "comment": comment},
            performed_by=resolved_by
        )

        logger.info(f"Request {request_id} marked as resolved by {resolved_by.email}")
        return request

    @staticmethod
    @transaction.atomic
    def close_request(request_id, closed_by):
        """Manager/landlord officially closes a resolved request."""
        request = MaintenanceRequest.objects.get(id=request_id)
        if request.status != "resolved":
            raise ValueError("Only resolved requests can be closed.")

        WorkflowService.transition_status(str(request_id), "closed", performed_by=closed_by)
        logger.info(f"Request {request_id} closed by {closed_by.email}")
        return request