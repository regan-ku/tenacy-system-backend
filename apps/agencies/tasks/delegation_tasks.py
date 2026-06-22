from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task(bind=True, max_retries=3)
def notify_landlord_of_delegation(self, landlord_email: str, agency_name: str, property_name: str):
    """Notifies the landlord when their property is successfully delegated to an agency."""
    subject = f"Property Delegation Confirmed: {property_name}"
    message = f"Your property '{property_name}' has been successfully delegated to '{agency_name}'. They can now manage it according to the agreed permissions."
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[landlord_email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def notify_agency_of_revocation(self, agency_email: str, property_name: str, reason: str):
    """Notifies the agency when a landlord revokes their delegation rights."""
    subject = f"Delegation Revoked: {property_name}"
    message = f"The delegation for property '{property_name}' has been revoked. Reason: {reason or 'No reason provided.'}. You no longer have operational access to this property."
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[agency_email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)