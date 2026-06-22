from celery import shared_task
import logging
from django.utils import timezone
from ..models import MaintenanceRequest, MaintenanceHistory
from ..services.escalation_service import EscalationService
from communications.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=600)
def run_sla_breach_scan(self):
    """
    Periodic task: Scans for overdue requests and escalates priority.
    Runs every 30 minutes.
    """
    try:
        logger.info("Starting SLA breach scan...")
        result = EscalationService.check_and_escalate_breaches()
        
        # Trigger high-priority alerts if breaches occurred
        if result["escalated"] > 0:
            NotificationService.create_in_app(
                user_id="ADMIN_USER_ID_PLACEHOLDER", # Resolve actual admin IDs in production
                title="SLA Breaches Detected",
                body=f"{result['escalated']} maintenance requests have breached their SLA deadlines.",
                notif_type="alert"
            )
            logger.info(f"Escalation alerts sent for {result['escalated']} breaches.")
            
        return result
    except Exception as e:
        logger.error(f"SLA breach scan failed: {str(e)}")
        self.retry(exc=e)