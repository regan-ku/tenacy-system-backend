from celery import shared_task
import logging
from django.utils import timezone
from ..models import MaintenanceInspection, InspectionStatus

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def update_overdue_inspections(self):
    """
    Scans for inspections where the date has passed but status is still SCHEDULED.
    Updates status to OVERDUE so they appear in caretaker dashboards as urgent.
    """
    try:
        now = timezone.now().date()
        
        count, _ = MaintenanceInspection.objects.filter(
            inspection_date__lt=now,
            status=InspectionStatus.SCHEDULED
        ).update(status=InspectionStatus.OVERDUE)
        
        if count > 0:
            logger.info(f"Marked {count} inspections as overdue.")
        
        return {"updated_count": count}
    except Exception as e:
        logger.error(f"Inspection update task failed: {str(e)}")
        self.retry(exc=e)