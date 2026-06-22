from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from ..models import Report, ReportSchedule, ReportSnapshot
from .report_generation_tasks import generate_report_task

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2)
def process_scheduled_reports(self):
    """
    Checks for active ReportSchedules that are due to run and triggers 
    asynchronous report generation for them. Recommended to run every 15 minutes via Celery Beat.
    """
    try:
        now = timezone.now()
        due_schedules = ReportSchedule.objects.filter(
            is_active=True,
            next_run_at__lte=now
        )

        processed_count = 0
        for schedule in due_schedules:
            # Create a new Report record for this scheduled run
            report = Report.objects.create(
                title=f"Scheduled: {schedule.title}",
                report_type=schedule.report_type,
                generated_by=schedule.created_by,
                parameters=schedule.parameters,
                status=Report.Status.PENDING
            )
            
            # Trigger async generation
            generate_report_task.delay(report.id)
            
            # Update schedule's next run time (simplified logic; production would use dateutil.relativedelta)
            if schedule.frequency == 'daily':
                schedule.next_run_at = now + timedelta(days=1)
            elif schedule.frequency == 'weekly':
                schedule.next_run_at = now + timedelta(weeks=1)
            elif schedule.frequency == 'monthly':
                # Approximate monthly addition
                schedule.next_run_at = now + timedelta(days=30)
            else:
                schedule.next_run_at = now + timedelta(days=365) # yearly fallback
                
            schedule.last_run_at = now
            schedule.save(update_fields=['next_run_at', 'last_run_at'])
            processed_count += 1

        logger.info(f"Processed {processed_count} scheduled reports.")
        return {"processed": processed_count}
    except Exception as e:
        logger.error(f"Failed to process scheduled reports: {str(e)}")
        raise self.retry(exc=e, countdown=600)


@shared_task(bind=True, max_retries=2)
def cleanup_old_reports(self, days_old: int = 90):
    """
    Archives or deletes old completed reports and their snapshots to maintain 
    database performance and comply with data retention policies.
    """
    try:
        cutoff = timezone.now() - timedelta(days=days_old)
        
        # Find old completed reports
        old_reports = Report.objects.filter(
            status=Report.Status.COMPLETED,
            completed_at__lt=cutoff
        )
        
        deleted_count, _ = old_reports.delete() # Cascades to ReportSnapshot due to on_delete=CASCADE
        
        logger.info(f"Cleaned up {deleted_count} old reports and their snapshots.")
        return {"deleted": deleted_count}
    except Exception as e:
        logger.error(f"Failed to cleanup old reports: {str(e)}")
        raise self.retry(exc=e, countdown=600)