from celery import shared_task
import logging
from django.utils import timezone
from datetime import timedelta
from ..models import Invoice
from communications.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def send_payment_reminders(self, days_before_due=3, days_overdue=1):
    """
    Triggers notifications for:
    1. Invoices due soon (e.g., 3 days before due date)
    2. Overdue invoices (e.g., 1+ days past due)
    """
    try:
        now = timezone.now().date()
        due_soon_cutoff = now + timedelta(days=days_before_due)
        overdue_cutoff = now - timedelta(days=days_overdue)

        upcoming = Invoice.objects.filter(due_date=due_soon_cutoff, status__in=["pending", "partial"])
        overdue = Invoice.objects.filter(due_date__lte=overdue_cutoff, status__in=["pending", "partial", "overdue"])

        triggered = 0

        for inv in upcoming:
            NotificationService.create_in_app(
                user_id=str(inv.tenancy.tenant.id),
                title="Rent Due Soon",
                body=f"Your rent of {inv.total_amount} is due on {inv.due_date}",
                notif_type="reminder"
            )
            triggered += 1

        for inv in overdue:
            NotificationService.create_in_app(
                user_id=str(inv.tenancy.tenant.id),
                title="Overdue Rent Alert",
                body=f"Invoice {inv.invoice_number} is overdue by {inv.total_amount}",
                notif_type="alert"
            )
            triggered += 1

        logger.info(f"Payment reminders triggered for {triggered} invoices")
        return {"status": "completed", "triggered": triggered}
    except Exception as e:
        logger.error(f"Reminder task failed: {str(e)}")
        self.retry(exc=e)