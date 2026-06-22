import hmac
import hashlib
import base64
from typing import Optional

def verify_webhook_signature(payload: bytes, signature: str, secret: str, algorithm: str = "sha256") -> bool:
    """
    Validates HMAC signatures from external providers.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not payload or not signature or not secret:
        return False

    computed = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256 if algorithm == "sha256" else hashlib.sha1
    ).hexdigest()

    return hmac.compare_digest(computed, signature)

def verify_base64_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Handles providers that return base64-encoded signatures (e.g., WhatsApp)"""
    computed = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).digest()
    return hmac.compare_digest(base64.b64encode(computed).decode(), signature)