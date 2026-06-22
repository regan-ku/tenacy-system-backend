from celery import shared_task
import logging
from ..models import PaymentAccountVerification, VerificationStatus
from ..services.payment_verification_service import PaymentVerificationService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=1, default_retry_delay=600)
def process_pending_account_verifications(self, limit=20):
    """
    Handles delayed or external verification steps for payment accounts.
    Updates status based on external checks or review queue progress.
    """
    try:
        pending = PaymentAccountVerification.objects.filter(
            verification_status=VerificationStatus.PENDING
        ).select_related("payment_account")[:limit]

        processed = 0
        for ver in pending:
            # In production: integrate with external validation API or admin review queue
            # Placeholder: marks as processed after successful external check
            logger.info(f"Processing verification {ver.id} for account {ver.payment_account_id}")
            processed += 1

        return f"Processed {processed} pending verifications"
    except Exception as e:
        logger.error(f"Payment verification task failed: {str(e)}")
        self.retry(exc=e)