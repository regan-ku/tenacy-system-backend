from typing import Dict, Any
from ..models import DocumentTemplate, DocumentType
from ..utils.formatter import DocFormatter
from ..utils.pdf_utils import PdfUtils
import logging

logger = logging.getLogger(__name__)

class TemplateService:
    @staticmethod
    def get_active_template(document_type_code: str, template_name: str = None) -> DocumentTemplate:
        qs = DocumentTemplate.objects.filter(document_type__code=document_type_code, is_active=True)
        if template_name:
            qs = qs.filter(name=template_name)
        return qs.first() or qs.filter(is_default=True).first()

    @staticmethod
    def prepare_generation_context(template: DocumentTemplate, variables: Dict[str, Any]) -> Dict[str, Any]:
        """Validates variables, sanitizes input, and injects into template HTML."""
        missing = [v for v in template.variables if v not in variables]
        if missing:
            logger.warning(f"Missing template variables for {template.name}: {missing}")

        sanitized = DocFormatter.sanitize_context(variables)
        rendered_html = PdfUtils.inject_variables(template.template_content, sanitized)
        return {
            "template_id": str(template.id),
            "html": rendered_html,
            "variables": sanitized,
            "document_type": template.document_type.code
        }