import requests
import logging
from django.core.exceptions import ValidationError
from ..utils.payload_formatter import format_whatsapp_template_payload
from ..services.integration_logger import IntegrationLogger
from ..models import MessageLog
from .whatsapp_config import WhatsAppConfig
from .template_manager import TemplateManager

logger = logging.getLogger(__name__)

class WhatsAppService:
    @staticmethod
    def send_text(phone: str, message: str) -> dict:
        payload = WhatsAppService._build_text_payload(phone, message)
        return WhatsAppService._dispatch_message(payload, "text", message)

    @staticmethod
    def send_template(phone: str, template_name: str, language_code: str = "en", components: list = None) -> dict:
        if not TemplateManager.validate_template_request(template_name, language_code, components):
            return {"success": False, "error": "Invalid template configuration"}
            
        payload = WhatsAppService._build_template_payload(phone, template_name, language_code, components)
        return WhatsAppService._dispatch_message(payload, "template", template_name)

    @staticmethod
    def _build_text_payload(phone: str, message: str) -> dict:
        creds = WhatsAppConfig.get_env_credentials()
        return {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": message}
        }

    @staticmethod
    def _build_template_payload(phone: str, name: str, lang: str, components: list = None) -> dict:
        creds = WhatsAppConfig.get_env_credentials()
        return format_whatsapp_template_payload(phone, name, lang, components)

    @staticmethod
    def _dispatch_message(payload: dict, msg_type: str, ref_id: str) -> dict:
        log_id = IntegrationLogger.log_request("whatsapp", "/messages", payload)

        try:
            creds = WhatsAppConfig.get_env_credentials()
            headers = WhatsAppConfig.format_headers()
            url = f"{creds['base_url']}/{creds['phone_number_id']}/messages"
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            message_id = data.get("messages", [{}])[0].get("id")
            MessageLog.objects.create(
                recipient_id=payload.get("to"),
                channel="whatsapp",
                message_content=ref_id,
                status="sent",
                external_ref=message_id,
                message_type=msg_type
            )
            
            IntegrationLogger.log_response(log_id, response.status_code, data, "success")
            return {"success": True, "message_id": message_id, "log_id": log_id}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            logger.error(f"WhatsApp dispatch failed: {str(e)}")
            return {"success": False, "error": str(e), "log_id": log_id}