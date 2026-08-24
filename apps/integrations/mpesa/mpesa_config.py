import base64
import requests
from datetime import datetime
from django.conf import settings
from ..utils.encryption import decrypt_secret

class MpesaConfig:
    """
    PLATFORM COLLECTION MODEL CONFIGURATION
    ---------------------------------------
    In this model, the platform uses a SINGLE, centralized M-Pesa Paybill 
    to collect all rent on behalf of landlords. 
    The credentials below represent the PLATFORM'S global Paybill and Passkey.
    """
    @staticmethod
    def get_env_credentials():
        # ✅ Safely handle blank Initiator Password to prevent server crash
        raw_initiator_pwd = getattr(settings, 'MPESA_INITIATOR_PASSWORD_ENCRYPTED', '')
        initiator_pwd = decrypt_secret(raw_initiator_pwd) if raw_initiator_pwd else ""

        return {
            "consumer_key": settings.MPESA_CONSUMER_KEY,
            "consumer_secret": decrypt_secret(settings.MPESA_CONSUMER_SECRET_ENCRYPTED),
            
            # ✅ PLATFORM GLOBAL PAYBILL: All tenant STK pushes will route to this shortcode
            "short_code": settings.MPESA_SHORT_CODE, 
            
            # ✅ PLATFORM GLOBAL PASSKEY: Must match the Paybill above
            "passkey": decrypt_secret(settings.MPESA_PASSKEY_ENCRYPTED),
            
            "initiator_name": settings.MPESA_INITIATOR_NAME,
            "initiator_password": initiator_pwd, 
            "base_url": settings.MPESA_BASE_URL,
            "callback_url": settings.MPESA_CALLBACK_BASE_URL 
        }

    @staticmethod
    def generate_timestamp():
        return datetime.now().strftime("%Y%m%d%H%M%S")

    @staticmethod
    def generate_password(short_code: str, passkey: str, timestamp: str) -> str:
        raw = f"{short_code}{passkey}{timestamp}"
        return base64.b64encode(raw.encode()).decode("utf-8")

    @staticmethod
    def get_access_token() -> str:
        creds = MpesaConfig.get_env_credentials()
        auth_url = f"{creds['base_url']}/oauth/v1/generate?grant_type=client_credentials"
        response = requests.get(
            auth_url,
            auth=(creds["consumer_key"], creds["consumer_secret"]),
            timeout=10
        )
        response.raise_for_status()
        return response.json().get("access_token")

    @staticmethod
    def format_headers(token: str):
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }