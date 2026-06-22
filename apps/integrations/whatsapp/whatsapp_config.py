import requests
from django.conf import settings
from ..utils.encryption import decrypt_secret

class WhatsAppConfig:
    @staticmethod
    def get_env_credentials():
        return {
            "access_token": decrypt_secret(settings.WHATSAPP_ACCESS_TOKEN_ENCRYPTED),
            "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
            "business_account_id": settings.WHATSAPP_BUSINESS_ACCOUNT_ID,
            "webhook_verify_token": settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN,
            "app_secret": decrypt_secret(settings.WHATSAPP_APP_SECRET_ENCRYPTED),
            "base_url": "https://graph.facebook.com/v17.0",
            "callback_url": settings.WHATSAPP_CALLBACK_BASE_URL
        }

    @staticmethod
    def format_headers():
        creds = WhatsAppConfig.get_env_credentials()
        return {
            "Authorization": f"Bearer {creds['access_token']}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def get_verify_params():
        return {"hub.verify_token": WhatsAppConfig.get_env_credentials()["webhook_verify_token"]}