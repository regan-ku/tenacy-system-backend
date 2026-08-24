import requests
import logging
from decimal import Decimal
from django.core.exceptions import ValidationError

from ..utils.payload_formatter import format_mpesa_stk_payload
from ..services.integration_logger import IntegrationLogger
from .mpesa_config import MpesaConfig
from .transaction_validator import TransactionValidator

logger = logging.getLogger(__name__)

class StkPushService:
    @staticmethod
    def initiate(phone: str, amount: float, account_ref: str, transaction_desc: str = "Payment") -> dict:
        """
        Initiates the actual HTTP request to Safaricom Daraja API.
        PLATFORM MODEL: Uses the Platform's global Paybill configured in .env.
        """
        phone = TransactionValidator.validate_phone(phone)
        amount = TransactionValidator.validate_amount(amount)
        
        # 1. Get Platform's global credentials
        creds = MpesaConfig.get_env_credentials()
        platform_shortcode = creds["short_code"]
        platform_passkey = creds["passkey"]
        
        # 2. Generate Password using Platform's Shortcode & Passkey
        timestamp = MpesaConfig.generate_timestamp()
        password = MpesaConfig.generate_password(platform_shortcode, platform_passkey, timestamp)
        
        # 3. Format payload
        payload = format_mpesa_stk_payload(phone, amount, account_ref, creds["callback_url"], transaction_desc)
        payload.update({
            "BusinessShortCode": platform_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "PartyB": platform_shortcode # ✅ Money goes to the Platform's Paybill
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
            return {"success": True, "merchant_request_id": data.get("MerchantRequestID"), "log_id": log_id, "data": data}
        except Exception as e:
            IntegrationLogger.log_failure(log_id, str(e))
            logger.error(f"STK Push failed: {str(e)}")
            return {"success": False, "error": str(e), "log_id": log_id}


class PaymentStkOrchestrator:
    @staticmethod
    def request_payment(tenancy, phone: str, amount: Decimal, invoice_ref: str = None) -> dict:
        """
        PLATFORM COLLECTION MODEL:
        Orchestrates the STK push. All payments go to the Platform's global Paybill.
        The AccountReference is used to identify the tenant/invoice during callback reconciliation.
        """
        try:
            # 1. State validation
            tenancy_status = getattr(tenancy, "status", None)
            if tenancy_status not in ["active", "pending_payment", "overdue"]:
                raise ValidationError("Tenancy is not in a billable state.")

            # 2. Format reference for reconciliation
            # Safaricom strictly limits AccountReference to 12 characters.
            # We use the Invoice ID if available, otherwise a truncated Tenancy ID.
            if invoice_ref:
                account_ref = invoice_ref
            else:
                account_ref = f"TEN{str(tenancy.id)[:9].upper()}" # "TEN" + 9 chars = 12 chars
                
            if len(account_ref) > 12:
                account_ref = account_ref[:12]
                
            description = f"Rent - {getattr(tenancy, 'unit_code', 'Unit')}"

            # 3. Trigger gateway (No landlord account lookup needed!)
            return StkPushService.initiate(
                phone=phone,
                amount=float(amount),
                account_ref=account_ref,
                transaction_desc=description
            )
            
        except Exception as e:
            logger.error(f"STK Push orchestration failed: {str(e)}")
            return {"success": False, "error": f"Orchestration error: {str(e)}"}