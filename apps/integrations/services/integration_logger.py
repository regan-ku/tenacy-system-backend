from typing import Dict, Any, Optional
from ..models import IntegrationLog
import logging

logger = logging.getLogger(__name__)

class IntegrationLogger:
    @staticmethod
    def log_request(
        provider: str, 
        endpoint: str, 
        request_payload: Dict, 
        triggered_by_id: Optional[str] = None
    ) -> str:
        """Creates initial log entry before external call"""
        log_entry = IntegrationLog.objects.create(
            provider=provider,
            endpoint=endpoint,
            request_payload=request_payload,
            status="pending",
            triggered_by_id=triggered_by_id
        )
        return str(log_entry.id)

    @staticmethod
    def log_response(log_id: str, status_code: int, response_payload: Dict, status: str = "success"):
        """Updates log after provider response"""
        try:
            log_entry = IntegrationLog.objects.get(id=log_id)
            log_entry.status_code = status_code
            log_entry.response_payload = response_payload
            log_entry.status = status
            log_entry.save(update_fields=["status_code", "response_payload", "status"])
        except IntegrationLog.DoesNotExist:
            logger.warning(f"Integration log {log_id} not found for response update")

    @staticmethod
    def log_failure(log_id: str, error_msg: str, increment_retry: bool = True):
        """Marks request as failed & increments retry counter"""
        try:
            log_entry = IntegrationLog.objects.get(id=log_id)
            log_entry.status = "failed"
            log_entry.response_payload = {"error": error_msg}
            if increment_retry:
                log_entry.retry_count += 1
            log_entry.save(update_fields=["status", "response_payload", "retry_count"])
        except IntegrationLog.DoesNotExist:
            logger.warning(f"Integration log {log_id} not found for failure update")