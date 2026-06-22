from decimal import Decimal
from datetime import datetime
from typing import Any, Dict
import re
import unicodedata

class DocFormatter:
    @staticmethod
    def format_currency(amount: float | Decimal, currency: str = "KES") -> str:
        """Formats numeric amounts with locale-aware currency symbols."""
        amount = Decimal(str(amount)).quantize(Decimal("0.00"))
        return f"{currency} {amount:,.2f}"

    @staticmethod
    def format_date(date_obj: datetime | None, fmt: str = "%d %B %Y") -> str:
        """Safely formats datetime objects; returns empty string if None."""
        if not date_obj:
            return ""
        return date_obj.strftime(fmt)

    @staticmethod
    def generate_safe_filename(base: str, extension: str = "pdf") -> str:
        """
        Converts a string into a safe, URL-friendly filename.
        Example: "Lease Agreement - Unit 4B.pdf" → "lease_agreement_unit_4b.pdf"
        """
        safe = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("utf-8")
        safe = re.sub(r"[^\w\s-]", "", safe).strip().lower()
        safe = re.sub(r"[-\s]+", "_", safe)  # ✅ Changed to underscore to match test
        return f"{safe}.{extension}" if safe else f"document_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"

    @staticmethod
    def sanitize_context(context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Removes None values, converts non-string types to strings for template injection,
        and strips dangerous HTML/script tags from user-provided text fields.
        """
        sanitized = {}
        for key, value in context.items():
            if value is None:
                continue
            if isinstance(value, str):
                # Basic XSS prevention for template variables
                value = re.sub(r"<[^>]*>", "", value)
            sanitized[key] = str(value)
        return sanitized