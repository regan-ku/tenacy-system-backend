import math
from typing import Optional
from ..models import IntegrationLog
from django.utils import timezone
from datetime import timedelta

class RetryService:
    MAX_RETRIES = 3
    BASE_DELAY_SECONDS = 60

    @classmethod
    def should_retry(cls, log_id: str) -> bool:
        """Checks if retry is allowed based on current retry count"""
        try:
            log = IntegrationLog.objects.get(id=log_id)
            return log.retry_count < cls.MAX_RETRIES
        except IntegrationLog.DoesNotExist:
            return False

    @classmethod
    def get_retry_delay(cls, log_id: str) -> Optional[timedelta]:
        """Calculates exponential backoff delay"""
        try:
            log = IntegrationLog.objects.get(id=log_id)
            if log.retry_count >= cls.MAX_RETRIES:
                return None
            
            delay = cls.BASE_DELAY_SECONDS * (2 ** log.retry_count)
            return timedelta(seconds=delay)
        except IntegrationLog.DoesNotExist:
            return None

    @classmethod
    def schedule_retry_task(cls, task_func, *args, log_id: str, **kwargs):
        """Enqueues Celery task with calculated delay"""
        delay = cls.get_retry_delay(log_id)
        if delay:
            task_func.apply_async(args=args, kwargs=kwargs, countdown=delay.total_seconds())
            return True
        return False