from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

# ... (keep your existing tasks like check_expiring_tenancies, etc.) ...

@shared_task(bind=True, max_retries=2)
def recall_unpaid_approved_applications(self):
    """
    Recalls approved applications if the tenant fails to pay the deposit/service charge 
    within 3 hours. Reverts application to 'under_review', cancels tenancy, and frees the unit.
    """
    try:
        from ..models import Tenancy
        from apps.applications.models import Application
        from apps.properties.models import Unit

        # Calculate the threshold time (3 hours ago)
        threshold_time = timezone.now() - timedelta(hours=3)
        
        # Find tenancies stuck in 'pending_payment' older than 3 hours
        unpaid_tenancies = Tenancy.objects.filter(
            status='pending_payment',
            created_at__lt=threshold_time
        ).select_related('unit', 'tenant')
        
        recalled_count = 0
        
        for tenancy in unpaid_tenancies:
            try:
                with transaction.atomic():
                    # 1. Cancel the tenancy
                    tenancy.status = 'cancelled'
                    tenancy.save(update_fields=['status'])
                    
                    # 2. Revert the application status to 'under_review'
                    application = Application.objects.filter(
                        unit=tenancy.unit,
                        applicant=tenancy.tenant,
                        status='approved'
                    ).first()
                    
                    if application:
                        # Safely get the enum value or fallback to string
                        under_review_status = getattr(Application.Status, 'UNDER_REVIEW', 'under_review')
                        application.status = under_review_status
                        application.save(update_fields=['status'])
                        
                    # 3. Free up the unit for the marketplace
                    unit = tenancy.unit
                    unit.status = 'available'
                    unit.save(update_fields=['status'])
                    
                    # 4. Notify tenant that their application was recalled (Optional)
                    try:
                        # Assuming you have a notification service in the communications app
                        from apps.communications.services.notification_service import NotificationService
                        NotificationService.send_application_recalled_notification(application, tenancy)
                    except Exception as notify_err:
                        logger.warning(f"Could not send recall notification for tenancy {tenancy.id}: {notify_err}")
                    
                    recalled_count += 1
                    
            except Exception as e:
                logger.warning(f"Failed to recall tenancy {tenancy.id}: {e}")
                
        if recalled_count > 0:
            logger.info(f"Successfully recalled {recalled_count} unpaid approved applications.")
            
        return {"recalled": recalled_count}
        
    except Exception as e:
        logger.error(f"Recall task failed: {e}")
        raise self.retry(exc=e, countdown=300)