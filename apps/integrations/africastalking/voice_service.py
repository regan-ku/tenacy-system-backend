import requests
import logging
from ..services.integration_logger import IntegrationLogger
from .africastalking_config import AfricasTalkingConfig

logger = logging.getLogger(__name__)

class VoiceService:
    @staticmethod
    def initiate_call(phone: str, message: str, caller_id: str = "Tennacy") -> dict:
        payload = {
            "from": caller_id,
            "to": phone,
            "voiceUrl": f"{AfricasTalkingConfig.get_env_credentials()['callback_url']}/voice/ivr"
        }
        log_id = IntegrationLogger.log_request("africastalking_voice", "/voice/call", payload)

        try:
            creds = AfricasTalkingConfig.get_env_credentials()
            headers = AfricasTalkingConfig.format_headers()
            headers["Content-Type"] = "application/json"
            url = f"{creds['base_url']}/voice/call"
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            
            IntegrationLogger.log_response(log_id, response.status_code, response.json(), "success")
            return {"success": True, "call_id": response.json().get("VoiceCallData", {}).get("PhoneEntries", [{}])[0].get("id"), "log_id": log_id}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            return {"success": False, "error": str(e), "log_id": log_id}