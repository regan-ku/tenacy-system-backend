import re
from typing import Dict, Any

class MessageFormatter:
    @staticmethod
    def truncate_for_sms(text: str, max_length: int = 160) -> str:
        """Truncates text to SMS character limits, preserving word boundaries."""
        if len(text) <= max_length:
            return text
        cut_point = text.rfind(' ', 0, max_length - 3)
        return f"{text[:cut_point]}..." if cut_point != -1 else f"{text[:max_length - 3]}..."

    @staticmethod
    def validate_whatsapp_template(template_name: str, language_code: str = "en") -> bool:
        """Basic compliance check for WhatsApp Business API templates."""
        if not template_name or len(template_name) > 200:
            return False
        return language_code in ["en", "sw", "fr", "es"]

    @staticmethod
    def prepare_email_payload(subject: str, body: str, is_html: bool = False) -> Dict[str, Any]:
        """Structures email content for transactional delivery."""
        return {
            "subject": subject,
            "body": body,
            "content_type": "html" if is_html else "text/plain"
        }

    @staticmethod
    def strip_html_for_fallback(html_content: str) -> str:
        """Removes HTML tags for SMS/plain-text fallback channels."""
        clean = re.sub(r'<[^>]+>', '', html_content)
        return re.sub(r'\s+', ' ', clean).strip()