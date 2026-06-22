from celery import shared_task
import logging
from django.utils import timezone
from ..models import Document, DocumentStatus, DocumentAuditLog, AuditAction
from ..integrations.cloud_storage import S3StorageBackend

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=2, default_retry_delay=300)
def archive_expired_documents(self):
    """
    Daily scan: Moves documents past their expiry date to ARCHIVED status.
    Logs compliance event for audit trail.
    Aligns with §10.2, §11.17 (Data retention & compliance lifecycle)
    """
    now = timezone.now()
    expired_docs = Document.objects.filter(
        status=DocumentStatus.ACTIVE,
        expires_at__lte=now
    )

    archived_count = 0
    for doc in expired_docs:
        try:
            doc.status = DocumentStatus.ARCHIVED
            doc.save(update_fields=["status", "updated_at"])
            
            DocumentAuditLog.objects.create(
                document=doc, 
                action=AuditAction.ARCHIVED, 
                user=None, 
                metadata={"reason": "auto_expired", "archived_at": now.isoformat()}
            )
            archived_count += 1
        except Exception as e:
            logger.error(f"Failed to archive document {doc.id}: {str(e)}")

    return {"archived_count": archived_count, "status": "completed"}

@shared_task(bind=True, max_retries=1, default_retry_delay=120)
def cleanup_dangling_temp_files(self):
    """
    Removes orphaned temporary PDFs left from failed generation attempts.
    Keeps storage costs minimal and prevents disk leaks.
    """
    import tempfile
    import os
    temp_dir = tempfile.gettempdir()
    purged = 0
    for filename in os.listdir(temp_dir):
        if filename.startswith("doc_") and filename.endswith((".html", ".pdf")):
            try:
                os.remove(os.path.join(temp_dir, filename))
                purged += 1
            except Exception:
                pass
    return {"purged_files": purged}