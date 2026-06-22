from typing import Dict, Any
from ..models import MessageTemplate
import logging

logger = logging.getLogger(__name__)

class MessageBuilder:
    @staticmethod
    def render_template(template_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fetches active template, validates required variables, and renders final content.
        Returns normalized payload ready for channel routing.
        """
        try:
            template = MessageTemplate.objects.get(id=template_id, is_active=True)
        except MessageTemplate.DoesNotExist:
            logger.error(f"Template {template_id} not found or inactive")
            raise ValueError("Invalid or inactive communication template")

        # Check for missing context variables
        missing = [var for var in template.required_variables if var not in context]
        if missing:
            logger.warning(f"Template {template_id} missing variables: {missing}")

        # Inject variables into body
        rendered_body = template.body
        for key, value in context.items():
            rendered_body = rendered_body.replace(f"{{{key}}}", str(value))

        return {
            "channel": template.channel,
            "subject": template.subject or "",
            "body": rendered_body,
            "template_id": str(template.id),
            "is_template": True
        }

    @staticmethod
    def build_adhoc_message(channel: str, content: str, subject: str = "") -> Dict[str, Any]:
        """Builds payload for direct, non-template messages (e.g., manual landlord alerts)."""
        return {
            "channel": channel,
            "body": content,
            "subject": subject,
            "is_template": False
        }