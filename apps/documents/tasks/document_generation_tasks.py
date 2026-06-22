from celery import shared_task
import logging
from ..services.document_service import DocumentService
from ..models import Document, GeneratedDocument
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_document_task(self, document_type_code: str, entity_ref: dict, variables: dict, 
                           title: str = None, user_id: str = None, expires_at_iso: str = None):
    """
    Async entry point for system-generated documents (leases, receipts, welcome letters, etc.).
    Delegates to DocumentService, handles retries, and returns generation metadata.
    Aligns with §3.1, §7.3 (Automated document generation & secure routing)
    """
    try:
        User = get_user_model()
        user = User.objects.get(id=user_id) if user_id else None
        
        from datetime import datetime
        expires_at = datetime.fromisoformat(expires_at_iso) if expires_at_iso else None

        doc, gen_doc = DocumentService.generate_from_template(
            document_type_code=document_type_code,
            entity_ref=entity_ref,
            variables=variables,
            title=title,
            expires_at=expires_at,
            generated_by_user=user
        )

        logger.info(f"Document generated successfully | ID: {doc.id} | Type: {document_type_code}")
        return {
            "status": "success", 
            "document_id": str(doc.id), 
            "gen_record_id": str(gen_doc.id),
            "file_url": doc.file_url
        }
    except Exception as e:
        logger.error(f"Document generation task failed: {str(e)}")
        self.retry(exc=e)