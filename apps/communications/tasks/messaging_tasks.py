from celery import shared_task
import logging
from django.utils import timezone
from django.core.mail import send_mail as django_send_mail
from django.conf import settings
from ..models import Message, MessageStatus, DeliveryLog

# Import provider services from the centralized Integrations App
from integrations.africastalking.sms_service import SmsService
from integrations.whatsapp.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_message_task(self, message_id: str, channel: str, payload: dict) -> dict:
    """
    Main router: Dispatches a single message to the appropriate channel worker.
    """
    try:
        message = Message.objects.get(id=message_id)
        message.status = MessageStatus.SENDING
        message.save(update_fields=["status"])

        if channel == "sms":
            return dispatch_sms_task.delay(message_id, payload)
        elif channel == "whatsapp":
            return dispatch_whatsapp_task.delay(message_id, payload)
        elif channel == "email":
            return dispatch_email_task.delay(message_id, payload)
        else:
            logger.warning(f"Unsupported channel: {channel}")
            return {"status": "failed", "error": "Unsupported channel"}
    except Exception as e:
        logger.error(f"Failed to route message {message_id}: {str(e)}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_sms_task(self, message_id: str, payload: dict) -> dict:
    """Worker for SMS dispatch via Africa's Talking"""
    try:
        message = Message.objects.get(id=message_id)
        phone = payload.get("phone") or message.recipient.profile.phone
        content = payload.get("content", message.content)
        
        result = SmsService.send_single(phone=phone, message=content)
        
        # Update logs via DeliveryLog (omitted for brevity, handled in service usually)
        message.status = MessageStatus.SENT if result.get("success") else MessageStatus.FAILED
        message.sent_at = timezone.now()
        message.save(update_fields=["status", "sent_at"])
        
        return result
    except Exception as e:
        logger.error(f"SMS dispatch failed for {message_id}: {str(e)}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_whatsapp_task(self, message_id: str, payload: dict) -> dict:
    """Worker for WhatsApp dispatch via WhatsApp Business API"""
    try:
        message = Message.objects.get(id=message_id)
        phone = payload.get("phone") or message.recipient.profile.phone
        template_name = payload.get("template_name")
        
        # Fallback to text if no template specified
        if template_name:
            result = WhatsAppService.send_template(phone=phone, template_name=template_name)
        else:
            result = WhatsAppService.send_text(phone=phone, message=message.content)
            
        message.status = MessageStatus.SENT if result.get("success") else MessageStatus.FAILED
        message.sent_at = timezone.now()
        message.save(update_fields=["status", "sent_at"])
        
        return result
    except Exception as e:
        logger.error(f"WhatsApp dispatch failed for {message_id}: {str(e)}")
        self.retry(exc=e)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def dispatch_email_task(self, message_id: str, payload: dict) -> dict:
    """Worker for Email dispatch via Django's SMTP backend"""
    try:
        message = Message.objects.get(id=message_id)
        recipient_email = payload.get("email") or message.recipient.email
        subject = payload.get("subject", "System Notification")
        body = payload.get("content", message.content)
        
        django_send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        
        message.status = MessageStatus.SENT
        message.sent_at = timezone.now()
        message.save(update_fields=["status", "sent_at"])
        return {"status": "queued"}
    except Exception as e:
        logger.error(f"Email dispatch failed for {message_id}: {str(e)}")
        self.retry(exc=e)