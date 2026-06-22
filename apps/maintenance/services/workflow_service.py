from django.db import transaction
from django.utils import timezone
from ..models import MaintenanceRequest, MaintenanceUpdate, MaintenanceHistory
import logging

logger = logging.getLogger(__name__)

# Strict transition map per documentation §5.1
VALID_TRANSITIONS = {
    "open": ["assigned"],
    "assigned": ["in_progress", "reassigned"],
    "in_progress": ["pending_review"],
    "pending_review": ["resolved", "in_progress"],
    "resolved": ["closed"],
    "closed": []
}

class WorkflowService:
    @staticmethod
    @transaction.atomic
    def transition_status(request_id, new_status, comment="", performed_by=None):
        """
        Safely transitions request status.
        Validates against allowed transitions, logs update & history.
        """
        request = MaintenanceRequest.objects.select_for_update().get(id=request_id)
        old_status = request.status

        if new_status not in VALID_TRANSITIONS.get(old_status, []):
            raise ValueError(f"Invalid transition: {old_status} → {new_status}")

        # 1. Update core status & timestamps
        request.status = new_status
        if new_status == "resolved":
            request.resolved_at = timezone.now()
        if new_status == "closed":
            request.closed_at = timezone.now()
        request.save(update_fields=["status", "resolved_at", "closed_at", "updated_at"])

        # 2. Create human-readable progress update
        if comment or performed_by:
            MaintenanceUpdate.objects.create(
                request=request,
                updated_by=performed_by,
                comment=comment,
                previous_status=old_status,
                new_status=new_status
            )

        # 3. Audit log
        MaintenanceHistory.objects.create(
            request=request,
            event_type="status_changed",
            previous_value={"status": old_status},
            new_value={"status": new_status},
            performed_by=performed_by
        )

        logger.info(f"Request {request_id} transitioned: {old_status} → {new_status}")
        return request