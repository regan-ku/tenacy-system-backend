from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task(bind=True, max_retries=3)
def notify_director_of_verification_status(self, director_email: str, director_name: str, agency_name: str, status: str, reason: str = ""):
    """
    Notifies an agency director when their personal identity verification is approved or rejected by an admin.
    """
    if status == 'verified':
        subject = f"Director Verification Approved: {agency_name}"
        message = f"Dear {director_name},\n\nYour identity verification for {agency_name} has been successfully approved. The agency is now one step closer to full operational activation."
    else:
        subject = f"Director Verification Requires Attention: {agency_name}"
        message = f"Dear {director_name},\n\nYour identity verification for {agency_name} was {status}.\n\nReason: {reason or 'Please log in to your agency dashboard to view details and resubmit the required documents.'}"

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[director_email],
            fail_silently=False,
        )
    except Exception as exc:
        # Retry the task in 60 seconds if the SMTP server is temporarily unavailable
        raise self.retry(exc=exc, countdown=60)