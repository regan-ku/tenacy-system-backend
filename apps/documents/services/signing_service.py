from django.db import transaction
from django.utils import timezone
from ..models import Document, DocumentStatus, DocumentAuditLog
import logging

logger = logging.getLogger(__name__)

class SigningService:
    @staticmethod
    @transaction.atomic
    def request_signature(document_id: str, signer_id: str):
        doc = Document.objects.get(id=document_id)
        if doc.status not in [DocumentStatus.DRAFT, DocumentStatus.PENDING_SIGNATURE]:
            raise ValueError(f"Cannot request signature for document in '{doc.status}' state.")
        
        doc.status = DocumentStatus.PENDING_SIGNATURE
        doc.assigned_to_id = signer_id
        doc.save(update_fields=["status", "assigned_to", "updated_at"])
        
        DocumentAuditLog.objects.create(document=doc, action="viewed", user_id=signer_id, metadata={"action": "signature_requested"})
        return doc

    @staticmethod
    @transaction.atomic
    def mark_signed(document_id: str, signer_id: str, signature_metadata: dict = None):
        doc = Document.objects.get(id=document_id, assigned_to_id=signer_id)
        if doc.status != DocumentStatus.PENDING_SIGNATURE:
            raise ValueError("Document is not pending signature.")
        
        doc.status = DocumentStatus.ACTIVE
        doc.metadata.update({"signed_at": timezone.now().isoformat(), "signature_data": signature_metadata or {}})
        doc.save(update_fields=["status", "metadata"])
        
        DocumentAuditLog.objects.create(document=doc, action="signed", user_id=signer_id, metadata=signature_metadata or {})
        logger.info(f"Document {document_id} signed by user {signer_id}")
        return doc

    @staticmethod
    @transaction.atomic
    def reject_document(document_id: str, user_id: str, reason: str):
        doc = Document.objects.get(id=document_id, assigned_to_id=user_id)
        doc.status = DocumentStatus.REJECTED
        doc.save(update_fields=["status", "updated_at"])
        
        DocumentAuditLog.objects.create(document=doc, action="rejected", user_id=user_id, metadata={"reason": reason})
        logger.info(f"Document {document_id} rejected. Reason: {reason}")
        return doc