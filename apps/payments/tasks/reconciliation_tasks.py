from celery import shared_task
import logging
from ..models import Payment, Invoice, Reconciliation
from ..services.reconciliation_service import ReconciliationService

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def auto_reconcile_pending_payments(self, limit=50):
    """
    Scans for manual (Cash/Bank) or C2B Paybill payments that are pending reconciliation.
    Attempts to match them to invoices using the AccountReference (Invoice Number).
    """
    try:
        # ✅ FIX: Target payments awaiting reconciliation, NOT completed ones
        pending = Payment.objects.filter(
            status__in=["pending", "pending_reconciliation"]
        ).exclude(
            reconciliations__status="matched"
        )[:limit]

        matched_count = 0
        flagged_count = 0

        for payment in pending:
            # Extract reference (Tenant usually types Invoice Number or Tenancy ID in Paybill AccountReference)
            ref = payment.raw_payload.get("AccountReference") or payment.account_received_at
            
            if not ref:
                ReconciliationService.flag_unallocated_payment(str(payment.id), reason="Missing account reference")
                flagged_count += 1
                continue

            # ✅ Try to find the exact invoice by Invoice Number (e.g., "INV-202410-ABC123")
            invoice = Invoice.objects.filter(invoice_number__iexact=ref).first()
            
            if not invoice:
                # Fallback: Try to find invoice by ID (if reference was a UUID)
                try:
                    invoice = Invoice.objects.filter(id=ref).first()
                except Exception:
                    pass

            if invoice:
                try:
                    ReconciliationService.match_payment_to_invoice(
                        payment_id=str(payment.id),
                        invoice_id=str(invoice.id),
                        notes="Auto-reconciled via background task reference match"
                    )
                    matched_count += 1
                except Exception as e:
                    logger.warning(f"Failed to auto-match payment {payment.id} to invoice {invoice.id}: {str(e)}")
                    ReconciliationService.flag_unallocated_payment(
                        str(payment.id), reason=f"Match failed: {str(e)}"
                    )
                    flagged_count += 1
            else:
                # Could not find invoice. Flag for manual manager review.
                ReconciliationService.flag_unallocated_payment(
                    str(payment.id), reason=f"No matching invoice found for reference: '{ref}'"
                )
                flagged_count += 1

        logger.info(f"Reconciliation task: Matched {matched_count}, Flagged {flagged_count}")
        return {"matched": matched_count, "flagged": flagged_count}
    except Exception as e:
        logger.error(f"Reconciliation task failed: {str(e)}")
        self.retry(exc=e)