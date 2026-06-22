import requests
import logging
from django.core.exceptions import ValidationError
from ..services.integration_logger import IntegrationLogger
from ..utils.payload_formatter import format_mpesa_stk_payload
from .mpesa_config import MpesaConfig
from .transaction_validator import TransactionValidator

logger = logging.getLogger(__name__)

class B2CService:
    @staticmethod
    def initiate_payout(phone: str, amount: float, command_id: str = "BusinessPayment", remarks: str = "Payout") -> dict:
        phone = TransactionValidator.validate_phone(phone)
        amount = TransactionValidator.validate_amount(amount)
        creds = MpesaConfig.get_env_credentials()
        
        payload = {
            "InitiatorName": creds["initiator_name"],
            "SecurityCredential": creds["initiator_password"], # In prod, use RSA encryption
            "CommandID": command_id,
            "Amount": amount,
            "PartyA": creds["short_code"],
            "PartyB": phone,
            "Remarks": remarks,
            "QueueTimeOutURL": f"{creds['callback_url']}/mpesa/b2c/timeout",
            "ResultURL": f"{creds['callback_url']}/mpesa/b2c/callback",
            "Occasion": "Payment"
        }

        log_id = IntegrationLogger.log_request("mpesa", "/mpesa/b2c/v1/paymentrequest", payload)
        
        try:
            token = MpesaConfig.get_access_token()
            headers = MpesaConfig.format_headers(token)
            url = f"{creds['base_url']}/mpesa/b2c/v1/paymentrequest"
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            
            IntegrationLogger.log_response(log_id, response.status_code, response.json(), "success")
            return {"success": True, "conversation_id": response.json().get("ConversationID"), "log_id": log_id}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            return {"success": False, "error": str(e), "log_id": log_id}