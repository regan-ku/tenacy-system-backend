from django.db import transaction
from django.utils import timezone
from ..models import MaintenanceRequest, MaintenanceAssignment, MaintenanceHistory
from .workflow_service import WorkflowService
import logging

logger = logging.getLogger(__name__)

class AssignmentService:
    @staticmethod
    @transaction.atomic
    def assign_request(request_id, assigned_to_user, assigned_by_user, role_type="caretaker"):
        """
        Assigns an open request to a caretaker/agent.
        Creates assignment record & transitions status to 'assigned'.
        """
        request = MaintenanceRequest.objects.select_for_update().get(id=request_id)
        if request.status != "open":
            raise ValueError("Can only assign requests in 'open' status.")

        # 1. Update request ownership
        request.assigned_to = assigned_to_user
        request.save(update_fields=["assigned_to", "updated_at"])

        # 2. Transition status
        WorkflowService.transition_status(str(request.id), "assigned", performed_by=assigned_by_user)

        # 3. Create assignment record
        assignment = MaintenanceAssignment.objects.create(
            request=request,
            assigned_to=assigned_to_user,
            assigned_by=assigned_by_user,
            role_type=role_type,
            status="pending"
        )

        # 4. Audit log
        MaintenanceHistory.objects.create(
            request=request,
            event_type="assigned",
            previous_value={"assigned_to": None, "status": "open"},
            new_value={"assigned_to": str(assigned_to_user.id), "status": "assigned"},
            performed_by=assigned_by_user
        )

        logger.info(f"Request {request_id} assigned to {assigned_to_user.email}")
        return assignment

    @staticmethod
    def acknowledge_assignment(assignment_id, user):
        """Caretaker/agent acknowledges receipt of assignment."""
        assignment = MaintenanceAssignment.objects.get(id=assignment_id, assigned_to=user)
        if assignment.status != "pending":
            raise ValueError("Assignment already processed.")
        assignment.status = "accepted"
        assignment.acknowledged_at = timezone.now()
        assignment.save(update_fields=["status", "acknowledged_at"])
        return assignment