from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task(bind=True, max_retries=3)
def notify_admin_of_new_agency_verification(self, agency_name: str, agency_email: str):
    """Notifies system admins when a new agency submits verification documents."""
    subject = f"New Agency Verification Submitted: {agency_name}"
    message = f"The agency '{agency_name}' ({agency_email}) has submitted their business verification documents for review."
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL], # Or a specific admin group email
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def notify_agency_of_verification_status(self, agency_email: str, status: str, reason: str = ""):
    """Notifies the agency contact when their verification is approved or rejected."""
    if status == 'verified':
        subject = "Agency Verification Approved ✅"
        message = "Congratulations! Your agency's business verification has been approved. You can now manage properties and add staff."
    else:
        subject = "Agency Verification Requires Attention ⚠️"
        message = f"Your agency verification was {status}. Reason: {reason or 'Please log in to your dashboard to view details and resubmit.'}"

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