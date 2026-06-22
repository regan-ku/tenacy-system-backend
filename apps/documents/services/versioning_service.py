from django.db import transaction, models
from django.utils import timezone
from ..models import Document, DocumentVersion, DocumentStatus, DocumentAuditLog
import logging

logger = logging.getLogger(__name__)

class VersioningService:
    @staticmethod
    @transaction.atomic
    def create_new_version(document_id: str, file_url: str, changed_by_user, change_reason: str, new_file_size: int = 0):
        """
        Creates a new version for an existing document.
        Increments the version number and logs the change for audit purposes.
        """
        try:
            doc = Document.objects.select_for_update().get(id=document_id)
            
            # Get current max version number
            max_v = DocumentVersion.objects.filter(document=doc).aggregate(max_v=models.Max("version_number"))["max_v"]
            new_version_num = (max_v or 0) + 1

            # Create new version record
            DocumentVersion.objects.create(
                document=doc,
                version_number=new_version_num,
                file_url=file_url,
                changed_by=changed_by_user,
                change_reason=change_reason
            )

            # Log the event
            DocumentAuditLog.objects.create(
                document=doc, 
                action="version_created", 
                user=changed_by_user,
                metadata={"version": new_version_num, "reason": change_reason}
            )

            logger.info(f"Version {new_version_num} created for document {document_id}")
            return new_version_num
        except Document.DoesNotExist:
            logger.error(f"Document {document_id} not found for versioning.")
            raise