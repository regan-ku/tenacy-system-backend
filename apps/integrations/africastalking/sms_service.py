import requests
import logging
from ..utils.payload_formatter import format_sms_payload
from ..services.integration_logger import IntegrationLogger
from ..models import MessageLog
from .africastalking_config import AfricasTalkingConfig

logger = logging.getLogger(__name__)

class SmsService:
    @staticmethod
    def send_single(phone: str, message: str, sender_id: str = "Tennacy") -> dict:
        payload = format_sms_payload(phone, message, sender_id)
        log_id = IntegrationLogger.log_request("africastalking", "/messaging", payload)

        try:
            creds = AfricasTalkingConfig.get_env_credentials()
            headers = AfricasTalkingConfig.format_headers()
            url = f"{creds['base_url']}/messaging"
            
            response = requests.post(url, data=payload, headers=headers, timeout=15)
            
            if AfricasTalkingConfig.validate_api_status(response):
                data = response.json()
                message_id = data.get("SMSMessageData", {}).get("Message", [{}])[0].get("id")
                
                # Create local tracking record
                MessageLog.objects.create(
                    recipient_id=payload.get("to"),
                    channel="sms",
                    message_content=message,
                    status="queued",
                    external_ref=message_id
                )
                IntegrationLogger.log_response(log_id, response.status_code, data, "success")
                return {"success": True, "message_id": message_id, "log_id": log_id}
            else:
                IntegrationLogger.log_response(log_id, response.status_code, response.json(), "failed")
                return {"success": False, "error": "AT API returned failure status", "log_id": log_id}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            logger.error(f"AT SMS failed: {str(e)}")
            return {"success": False, "error": str(e), "log_id": log_id}