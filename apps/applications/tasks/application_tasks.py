from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def expire_stale_applications(self, days_threshold: int = 14):
    """
    Automatically expires rental and transfer applications that have been 
    in 'pending' or 'under_review' status for longer than the threshold.
    Recommended to run daily via Celery Beat.
    """
    try:
        from ..models import Application
        
        cutoff_date = timezone.now() - timedelta(days=days_threshold)
        
        # Find stale applications
        stale_apps = Application.objects.filter(
            status__in=['pending', 'under_review'],
            created_at__lt=cutoff_date
        )
        
        count = stale_apps.update(status='expired')
        logger.info(f"Automatically expired {count} stale applications older than {days_threshold} days.")
        
        return {"expired_count": count}
    except Exception as e:
        logger.error(f"Failed to expire stale applications: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=2)
def flag_escalated_applications_for_review(self, hours_threshold: int = 48):
    """
    Identifies applications that have been 'escalated' to a manager for longer 
    than the threshold and flags them for urgent review (or triggers a notification).
    Recommended to run every 12 hours.
    """
    try:
        from ..models import Application, ApplicationNote
        
        cutoff_date = timezone.now() - timedelta(hours=hours_threshold)
        
        escalated_apps = Application.objects.filter(
            status='escalated',
            updated_at__lt=cutoff_date
        ).select_related('property', 'applicant')
        
        flagged_count = 0
        for app in escalated_apps:
            # Check if we already flagged it recently to avoid spamming notes
            recent_flag = ApplicationNote.objects.filter(
                application=app,
                note_type='system_validation',
                content__icontains='Urgent: Escalated application pending manager review'
            ).exists()
            
            if not recent_flag:
                ApplicationNote.objects.create(
                    application=app,
                    note_type='system_validation',
                    content=f"Urgent: Escalated application pending manager review for >{hours_threshold} hours.",
                    created_by=None # System-generated
                )
                flagged_count += 1
                
        logger.info(f"Flagged {flagged_count} escalated applications for urgent manager review.")
        return {"flagged_count": flagged_count}
    except Exception as e:
        logger.error(f"Failed to flag escalated applications: {e}")
        raise self.retry(exc=e, countdown=600)


@shared_task(bind=True, max_retries=2)
def cleanup_cancelled_applications(self, days_old: int = 90):
    """
    Soft-deletes or archives cancelled/rejected applications older than 
    a specified period to maintain database performance and GDPR compliance.
    """
    try:
        from ..models import Application
        
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        # In a production system, you might want to move these to an Archive table 
        # instead of hard deleting. For now, we hard delete cancelled/rejected ones.
        deleted_count, _ = Application.objects.filter(
            status__in=['cancelled', 'rejected', 'expired'],
            updated_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old cancelled/rejected applications.")
        return {"deleted_count": deleted_count}
    except Exception as e:
        logger.error(f"Failed to cleanup old applications: {e}")
        raise self.retry(exc=e, countdown=600)