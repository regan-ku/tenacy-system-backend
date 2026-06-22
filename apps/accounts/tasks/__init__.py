# This file ensures that Celery autodiscover_tasks can find the tasks in this directory.
from .email_tasks import send_welcome_email, send_verification_status_email
from .sms_tasks import send_otp_sms, send_account_alert_sms

__all__ = [
    'send_welcome_email',
    'send_verification_status_email',
    'send_otp_sms',
    'send_account_alert_sms',
]