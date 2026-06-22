from celery import shared_task
import logging
from django.utils import timezone
from datetime import timedelta
from ..models import MaintenanceAssignment, MaintenanceRequest, RequestStatus
from communications.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=1, default_retry_delay=300)
def send_assignment_reminders(self):
    """
    Scans for assignments that have not been acknowledged within 2 hours
    and sends a reminder to the assigned caretaker/agent.
    """
    try:
        now = timezone.now()
        cutoff = now - timedelta(hours=2)
        
        pending_assignments = MaintenanceAssignment.objects.filter(
            status="pending",
            assigned_at__lte=cutoff
        )

        reminded_count = 0
        for assignment in pending_assignments:
            try:
                # Send in-app notification + potentially SMS/WhatsApp via router
                NotificationService.create_in_app(
                    user_id=str(assignment.assigned_to.id),
                    title="Maintenance Action Required",
                    body=f"You have a pending maintenance request '{assignment.request.title}' that requires immediate acknowledgment.",
                    notif_type="reminder"
                )
                reminded_count += 1
            except Exception as e:
                logger.error(f"Failed to send reminder for assignment {assignment.id}: {str(e)}")
        
        return f"Reminders sent: {reminded_count}"
    except Exception as e:
        logger.error(f"Reminder task failed: {str(e)}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=1, default_retry_delay=300)
def send_pending_review_alerts(self):
    """
    Alerts landlords/managers when a request is marked 'Pending Review' (resolved) 
    but not yet 'Closed' within 48 hours.
    """
    try:
        now = timezone.now()
        cutoff = now - timedelta(hours=48)
        
        stalled_reviews = MaintenanceRequest.objects.filter(
            status=RequestStatus.PENDING_REVIEW,
            resolved_at__lte=cutoff
        )
        
        alerted_count = 0
        for req in stalled_reviews:
            # Logic to determine manager/landlord to alert
            manager_id = req.property.current_manager_id or req.property.owner_id
            if manager_id:
                NotificationService.create_in_app(
                    user_id=str(manager_id),
                    title="Maintenance Review Pending",
                    body=f"Request '{req.title}' has been resolved but awaits your final review/closure.",
                    notif_type="alert"
                )
                alerted_count += 1

        return f"Review alerts sent: {alerted_count}"
    except Exception as e:
        logger.error(f"Pending review alert task failed: {str(e)}")
        self.retry(exc=e)