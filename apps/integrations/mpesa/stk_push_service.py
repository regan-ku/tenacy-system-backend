import requests
import logging
from django.core.exceptions import ValidationError
from ..utils.payload_formatter import format_mpesa_stk_payload
from ..services.integration_logger import IntegrationLogger
from .mpesa_config import MpesaConfig
from .transaction_validator import TransactionValidator

logger = logging.getLogger(__name__)

class StkPushService:
    @staticmethod
    def initiate(phone: str, amount: float, account_ref: str, transaction_desc: str = "Payment") -> dict:
        phone = TransactionValidator.validate_phone(phone)
        amount = TransactionValidator.validate_amount(amount)
        creds = MpesaConfig.get_env_credentials()
        timestamp = MpesaConfig.generate_timestamp()
        password = MpesaConfig.generate_password(creds["short_code"], creds["passkey"], timestamp)
        
        payload = format_mpesa_stk_payload(phone, amount, account_ref, creds["callback_url"], transaction_desc)
        payload.update({
            "BusinessShortCode": creds["short_code"],
            "Password": password,
            "Timestamp": timestamp
        })

        log_id = IntegrationLogger.log_request("mpesa", "/mpesa/stkpush/v1/processrequest", payload)
        
        try:
            token = MpesaConfig.get_access_token()
            headers = MpesaConfig.format_headers(token)
            url = f"{creds['base_url']}/mpesa/stkpush/v1/processrequest"
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            IntegrationLogger.log_response(log_id, response.status_code, data, "success")
            return {"success": True, "merchant_request_id": data.get("MerchantRequestID"), "log_id": log_id}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            logger.error(f"STK Push failed: {str(e)}")
            return {"success": False, "error": str(e), "log_id": log_id}