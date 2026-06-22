from celery import shared_task
import logging
from ..models import Payment, Reconciliation
from ..services.reconciliation_service import ReconciliationService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def auto_reconcile_pending_payments(self, limit=50):
    """
    Scans for completed but unallocated payments and attempts to match them
    to invoices using account references, tenancy codes, or callback payloads.
    """
    try:
        matched_payments = Reconciliation.objects.filter(status="matched").values_list("payment_id", flat=True)
        pending = Payment.objects.filter(status="completed").exclude(id__in=matched_payments)[:limit]

        matched_count = 0
        flagged_count = 0

        for payment in pending:
            ref = payment.raw_payload.get("AccountReference") or payment.account_received_at
            
            if not ref:
                ReconciliationService.flag_unallocated_payment(str(payment.id), reason="Missing account reference")
                flagged_count += 1
                continue

            try:
                # Service handles reference → invoice mapping logic
                ReconciliationService.match_payment_to_invoice(
                    payment_id=str(payment.id),
                    invoice_id=ref,
                    notes="Auto-reconciled via background task"
                )
                matched_count += 1
            except Exception:
                ReconciliationService.flag_unallocated_payment(
                    str(payment.id), reason="No matching invoice found for reference"
                )
                flagged_count += 1

        logger.info(f"Reconciliation task: Matched {matched_count}, Flagged {flagged_count}")
        return {"matched": matched_count, "flagged": flagged_count}
    except Exception as e:
        logger.error(f"Reconciliation task failed: {str(e)}")
        self.retry(exc=e)