import logging
from ..services.integration_logger import IntegrationLogger
from .transaction_validator import TransactionValidator

logger = logging.getLogger(__name__)

class C2BService:
    @staticmethod
    def handle_validation_callback(payload: dict) -> dict:
        # M-Pesa expects ResultCode=0 to accept transaction
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    @staticmethod
    def handle_confirmation_callback(payload: dict) -> dict:
        if not TransactionValidator.validate_callback_payload(payload):
            return {"ResultCode": 1, "ResultDesc": "Invalid callback payload"}
            
        log_id = IntegrationLogger.log_request("mpesa_c2b", "/c2b/confirmation", payload)
        IntegrationLogger.log_response(log_id, 200, {"status": "queued"}, "success")
        return {"ResultCode": 0, "ResultDesc": "Success"}