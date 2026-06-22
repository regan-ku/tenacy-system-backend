from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags

@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_email: str, full_name: str):
    """
    Sends a welcome email to newly registered users.
    Retries up to 3 times if the SMTP server is temporarily unavailable.
    """
    subject = "Welcome to Tennacy Platform!"
    message = f"Hello {full_name},\n\nWelcome to Tennacy! Your account has been successfully created."
    html_message = f"<p>Hello <strong>{full_name}</strong>,</p><p>Welcome to Tennacy! Your account has been successfully created.</p>"
    
    try:
        send_mail(
            subject=subject,
            message=message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception as exc:
        # Retry the task in 60 seconds if it fails
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_verification_status_email(self, user_email: str, status: str, reason: str = ""):
    """
    Notifies the user when their verification status changes (Approved/Rejected).
    """
    if status == 'verified':
        subject = "Verification Approved ✅"
        message = "Congratulations! Your identity verification has been approved. You now have full access to landlord/agency features."
    else:
        subject = "Verification Requires Attention ⚠️"
        message = f"Your verification was {status}. Reason: {reason or 'Please check your dashboard for details.'}"

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)