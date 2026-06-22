import base64
import logging
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)

def _validate_fernet_key(key: str | bytes) -> bytes:
    """
    Validates that the provided key is a proper 32-byte url-safe base64 Fernet key.
    Returns bytes if valid, raises ValueError otherwise.
    """
    key_bytes = key if isinstance(key, bytes) else key.strip().encode("utf-8")
    try:
        # Fernet constructor validates format internally, but we pre-check for clearer errors
        decoded = base64.urlsafe_b64decode(key_bytes)
        if len(decoded) != 32:
            raise ValueError(f"Key decodes to {len(decoded)} bytes. Fernet requires exactly 32.")
        return key_bytes
    except Exception as e:
        raise ValueError(f"Invalid INTEGRATION_ENCRYPTION_KEY format: {e}")

def get_fernet_key() -> bytes:
    """
    Retrieves and validates the encryption key from Django settings.
    - Production: Strictly requires a valid key. Fails fast if missing/invalid.
    - Development: Falls back to a generated key with a clear warning.
    """
    raw_key = getattr(settings, "INTEGRATION_ENCRYPTION_KEY", None)

    if raw_key:
        try:
            return _validate_fernet_key(raw_key)
        except ValueError as e:
            if not settings.DEBUG:
                logger.critical(f"Encryption key validation failed: {e}")
                raise
            logger.warning(f"Invalid key provided. Falling back to temp key for DEBUG: {e}")

    # Fallback for DEBUG only
    if not settings.DEBUG:
        raise ValueError(
            "INTEGRATION_ENCRYPTION_KEY is missing or invalid. "
            "Generate a valid key and add it to your .env/settings for production."
        )

    logger.warning(
        "INTEGRATION_ENCRYPTION_KEY not set. Using a temporary generated key. "
        "⚠️ Encrypted data WILL NOT survive server restarts."
    )
    return Fernet.generate_key()

# Initialize Fernet (runs once at app startup)
try:
    fernet = Fernet(get_fernet_key())
except Exception as e:
    logger.critical(f"Fernet initialization failed: {e}")
    raise

def encrypt_secret(secret: str) -> str:
    """Encrypts a plaintext string. Returns empty string if input is empty."""
    if not secret:
        return ""
    return fernet.encrypt(secret.encode("utf-8")).decode("utf-8")

def decrypt_secret(encrypted_secret: str) -> str:
    """
    Decrypts a Fernet-encrypted string.
    Raises ValueError on failure instead of silently returning garbage data.
    """
    if not encrypted_secret:
        return ""
    try:
        return fernet.decrypt(encrypted_secret.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        logger.error(f"Decryption failed (InvalidToken): {e}")
        raise ValueError(
            "Failed to decrypt secret. This usually means INTEGRATION_ENCRY_KEY "
            "changed or the encrypted data is corrupted."
        ) from e
    except Exception as e:
        logger.error(f"Unexpected decryption error: {e}")
        raise ValueError("Decryption failed due to an unexpected error.") from e