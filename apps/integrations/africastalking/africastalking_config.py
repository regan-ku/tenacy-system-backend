import requests
from django.conf import settings
from ..utils.encryption import decrypt_secret

class AfricasTalkingConfig:
    @staticmethod
    def get_env_credentials():
        return {
            "username": settings.AT_USERNAME,
            "api_key": decrypt_secret(settings.AT_API_KEY_ENCRYPTED),
            "base_url": settings.AT_BASE_URL or "https://api.africastalking.com/version1",
            "callback_url": settings.AT_CALLBACK_BASE_URL
        }

    @staticmethod
    def format_headers():
        creds = AfricasTalkingConfig.get_env_credentials()
        return {
            "Api-Key": creds["api_key"],
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }

    @staticmethod
    def validate_api_status(response: requests.Response) -> bool:
        return response.status_code == 201 or (response.status_code == 200 and response.json().get("SMSMessageData", {}).get("Status") == "Success")