from typing import Dict, Any
from ..models import MessageTemplate
from ..utils.message_builder import MessageBuilder
import logging

logger = logging.getLogger(__name__)

class TemplateService:
    @staticmethod
    def get_active_template(template_id: str) -> MessageTemplate:
        try:
            return MessageTemplate.objects.get(id=template_id, is_active=True)
        except MessageTemplate.DoesNotExist:
            raise ValueError(f"Active template {template_id} not found")

    @staticmethod
    def render_template(template: MessageTemplate, context: Dict[str, Any]) -> Dict[str, Any]:
        if not template.is_active:
            raise ValueError("Template is inactive")
        return MessageBuilder.render_template(str(template.id), context)

    @staticmethod
    def validate_and_prepare(template_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        template = TemplateService.get_active_template(template_id)
        return TemplateService.render_template(template, context)