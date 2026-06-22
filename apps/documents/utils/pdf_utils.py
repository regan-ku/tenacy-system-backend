import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path
from django.conf import settings
from .formatter import DocFormatter

class PdfUtils:
    @staticmethod
    def inject_variables(template_html: str, context: Dict[str, str]) -> str:
        """
        Replaces {placeholder} tags in HTML templates with sanitized context values.
        Fails gracefully if a placeholder is missing (leaves original tag).
        """
        result = template_html
        for key, value in context.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    @staticmethod
    def compute_checksum(file_path: str | Path) -> str:
        """
        Generates SHA-256 hash of a file for tamper verification & audit trails.
        """
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def generate_secure_download_url(filename: str, expires_hours: int = 24) -> str:
        """
        Creates a time-bound, signed URL pattern for cloud storage (S3/Spaces).
        In production: delegates to Boto3 `generate_presigned_url` or similar.
        """
        expiry = datetime.now() + timedelta(hours=expires_hours)
        # Placeholder signature structure (replace with actual provider SDK)
        token = hashlib.sha256(f"{filename}{expiry.timestamp()}".encode()).hexdigest()[:16]
        return f"{settings.MEDIA_URL}/secure/{filename}?token={token}&expires={int(expiry.timestamp())}"

    @staticmethod
    def prepare_render_payload(template_html: str, context: Dict, css_path: Optional[str] = None) -> Dict:
        """
        Bundles sanitized HTML, variables, and optional CSS for async PDF generation tasks.
        """
        sanitized = DocFormatter.sanitize_context(context)
        rendered_html = PdfUtils.inject_variables(template_html, sanitized)
        return {
            "html": rendered_html,
            "context": sanitized,
            "css_path": css_path or "",
            "generated_at": datetime.now().isoformat()
        }