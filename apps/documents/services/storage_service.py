import os
from pathlib import Path
from django.conf import settings
from ..utils.formatter import DocFormatter
from ..integrations.cloud_storage import S3StorageBackend
import logging

logger = logging.getLogger(__name__)

class StorageService:
    _backend = None

    @classmethod
    def get_backend(cls) -> S3StorageBackend:
        if cls._backend is None:
            cls._backend = S3StorageBackend()
        return cls._backend

    @classmethod
    def upload_file(cls, local_path: str, filename: str) -> str:
        """Uploads to cloud, returns secure URL."""
        key = DocFormatter.generate_safe_filename(filename, "pdf")
        return cls.get_backend().upload_file(local_path, key)

    @classmethod
    def generate_signed_url(cls, file_url: str, expires_hours: int = 24) -> str:
        """Extracts key from URL and returns presigned link."""
        # In production: store `file_key` in DB instead of parsing URL
        key = Path(file_url).name
        return cls.get_backend().get_signed_url(key, expires_hours * 3600)

    @classmethod
    def cleanup_temp(cls, file_path: str):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Temp cleanup failed: {str(e)}")