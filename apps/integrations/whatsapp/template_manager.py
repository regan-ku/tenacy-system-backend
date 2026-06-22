from typing import Dict, List, Optional

class TemplateManager:
    @staticmethod
    def format_text_payload(text: str) -> Dict:
        return {"type": "text", "body": {"text": text}}

    @staticmethod
    def format_template_payload(
        template_name: str, 
        language_code: str = "en", 
        components: Optional[List[Dict]] = None
    ) -> Dict:
        payload = {
            "messaging_product": "whatsapp",
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }
        if components:
            payload["template"]["components"] = components
        return payload

    @staticmethod
    def build_header_variables(variables: List[str]) -> List[Dict]:
        return [{"type": "text", "text": var} for var in variables]

    @staticmethod
    def build_body_variables(variables: List[str]) -> List[Dict]:
        return [{"type": "text", "text": var} for var in variables]

    @staticmethod
    def validate_template_request(template_name: str, language_code: str, components: List[Dict] = None) -> bool:
        if not template_name or len(template_name) > 512:
            return False
        if len(language_code) not in [2, 5]:
            return False
        return True