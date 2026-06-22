import re
from typing import Dict, Any

class CampaignTemplateRenderer:
    @staticmethod
    def render(template: str, context: Dict[str, Any]) -> str:
        """
        Replaces {key} placeholders in template with context values.
        Falls back to original placeholder if key is missing.
        """
        def replace_match(match):
            key = match.group(1)
            return str(context.get(key, match.group(0)))
            
        return re.sub(r"\{(\w+)\}", replace_match, template)

    @staticmethod
    def extract_variables(template: str) -> list:
        """Extracts all placeholder keys for validation"""
        return re.findall(r"\{(\w+)\}", template)

    @staticmethod
    def validate_template_compatibility(channel: str, template: str) -> bool:
        """Basic validation: WhatsApp templates require approved names, SMS/Email allow free text"""
        if channel == "whatsapp" and len(template) > 4096:
            return False
        if channel == "sms" and len(template) > 1600:
            return False
        return True