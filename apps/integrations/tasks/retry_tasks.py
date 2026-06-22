from celery import shared_task
import logging
from ..models import IntegrationLog
from ..services.retry_service import RetryService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=1)
def retry_failed_integration(self, log_id: str):
    """
    Checks if a failed log is eligible for retry and re-dispatches the original request.
    Used for tasks that failed outside of the Celery retry mechanism.
    """
    try:
        if not RetryService.should_retry(log_id):
            logger.warning(f"Max retries reached for log {log_id}. Marking as permanently failed.")
            # In a full system, we might send an alert here.
            return "Max retries reached"

        # Fetch log to determine provider and payload
        log = IntegrationLog.objects.get(id=log_id)
        
        # Placeholder: Logic to re-dispatch based on provider type.
        # In production, this would parse log.request_payload and call the specific service again.
        # Example: if log.provider == 'sms': dispatch_sms_task.delay(log_id, ...)
        
        logger.info(f"Scheduling manual retry for log {log_id} ({log.provider})")
        RetryService.schedule_retry_task(
            task_func=retry_failed_integration, 
            log_id=log_id
        )
        
        return f"Retry scheduled for {log_id}"

    except IntegrationLog.DoesNotExist:
        logger.error(f"Integration Log {log_id} not found for retry")
        return "Log not found"
    except Exception as e:
        logger.error(f"Retry Task Failed: {str(e)}")
        self.retry(exc=e)