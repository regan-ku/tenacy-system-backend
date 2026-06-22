from typing import Dict, Any
from django.db import transaction
from django.utils import timezone
from ..models import Document, DocumentTemplate, DocumentStatus, GeneratedDocument, DocumentAuditLog
from .template_service import TemplateService
from .pdf_generator_service import PdfGeneratorService
from .storage_service import StorageService
from ..utils.formatter import DocFormatter
import logging

logger = logging.getLogger(__name__)

class DocumentService:
    @staticmethod
    @transaction.atomic
    def generate_from_template(
        document_type_code: str,
        entity_ref: Dict[str, str],
        variables: Dict[str, Any],
        title: str = None,
        expires_at: timezone.datetime = None,
        generated_by_user=None
    ):
        template = TemplateService.get_active_template(document_type_code)
        if not template:
            raise ValueError(f"No active template for type: {document_type_code}")

        payload = TemplateService.prepare_generation_context(template, variables)
        pdf_result = PdfGeneratorService.render_html_to_pdf(payload["html"])

        doc = Document.objects.create(
            document_type=template.document_type,
            template=template,
            title=title or f"{template.document_type.name} - {timezone.now().strftime('%Y-%m-%d')}",
            status=DocumentStatus.DRAFT,
            expires_at=expires_at,
            uploaded_by=generated_by_user,
            metadata={"generation_params": payload["variables"]}
        )

        gen_doc = GeneratedDocument.objects.create(
            document=doc,
            template=template,
            status="generated",
            generation_variables=payload["variables"],
            generated_by=generated_by_user,
            checksum=pdf_result["checksum"],
            file_size=pdf_result["size"],
            page_count=pdf_result["pages"]
        )

        # Link to entities
        if "tenancy_id" in entity_ref:
            from tenancy.models import Tenancy
            gen_doc.tenancy = Tenancy.objects.get(id=entity_ref["tenancy_id"])
        if "payment_id" in entity_ref:
            from payments.models import Payment
            gen_doc.payment = Payment.objects.get(id=entity_ref["payment_id"])
        gen_doc.save()

        dest_key = DocFormatter.generate_safe_filename(doc.title, "pdf")
        file_url = StorageService.upload_file(pdf_result["file_path"], dest_key)
        
        doc.file_url = file_url
        doc.status = DocumentStatus.ACTIVE
        doc.save(update_fields=["file_url", "status"])

        DocumentAuditLog.objects.create(
            document=doc, action="uploaded", user=generated_by_user,
            metadata={"size": pdf_result["size"], "checksum": pdf_result["checksum"]}
        )
        StorageService.cleanup_temp(pdf_result["file_path"])

        return doc, gen_doc