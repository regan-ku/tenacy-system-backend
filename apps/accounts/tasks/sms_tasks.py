from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_otp_sms(self, phone_number: str, otp_code: str):
    """
    Sends an OTP code to the user's phone number for verification.
    """
    message = f"Your Tennacy verification code is: {otp_code}. Do not share this with anyone."
    
    try:
        # TODO: Integrate with Africa's Talking or Twilio here
        # Example: africastalking.SMS.send(message, [phone_number])
        logger.info(f"SMS sent to {phone_number}: {message}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send SMS to {phone_number}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=2)
def send_account_alert_sms(self, phone_number: str, alert_message: str):
    """
    Sends critical account alerts (e.g., password change, suspicious login).
    """
    try:
        # TODO: Integrate with SMS provider
        logger.info(f"Alert SMS sent to {phone_number}: {alert_message}")
        return True
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)