from django.utils import timezone
from django.db import transaction
from ..models import MaintenanceRequest, MaintenanceHistory
from ..utils.sla_calculator import SLACalculator
import logging

logger = logging.getLogger(__name__)

class EscalationService:
    @staticmethod
    def check_and_escalate_breaches():
        """
        Scans for overdue requests, escalates priority to 'emergency',
        and logs SLA breach events. Designed for Celery periodic execution.
        """
        now = timezone.now()
        breached_requests = MaintenanceRequest.objects.filter(
            sla_due_at__lte=now,
            status__in=["open", "assigned", "in_progress"]
        )

        escalated_count = 0
        for req in breached_requests:
            # Avoid duplicate escalation within 1 hour window
            recent_breach = MaintenanceHistory.objects.filter(
                request=req, event_type="sla_breach"
            ).order_by("-created_at").first()

            if recent_breach and (now - recent_breach.created_at).total_seconds() < 3600:
                continue

            breach_info = SLACalculator.check_status(req.sla_due_at, now)

            with transaction.atomic():
                old_priority = req.priority
                if req.priority != "emergency":
                    req.priority = "emergency"
                    req.save(update_fields=["priority", "updated_at"])

                MaintenanceHistory.objects.create(
                    request=req,
                    event_type="sla_breach",
                    previous_value={"priority": old_priority},
                    new_value={"priority": req.priority, "hours_overdue": breach_info.get("hours_overdue", 0)},
                    performed_by=None  # System-triggered
                )

                # TODO: Queue async notification task
                # from ..tasks.escalation_tasks import notify_manager_of_breach
                # notify_manager_of_breach.delay(str(req.id))

            escalated_count += 1

        logger.info(f"Escalated {escalated_count} breached maintenance requests")
        return {"escalated": escalated_count}