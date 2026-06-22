from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

class StorageBackend(ABC):
    """
    Provider-agnostic contract for document storage operations.
    Allows swapping between S3, Spaces, MinIO, or local dev storage without touching business logic.
    """
    @abstractmethod
    def upload_file(self, local_path: str | Path, destination_key: str, content_type: str = "application/pdf") -> str:
        """Uploads file to cloud storage, returns secure URL."""
        pass

    @abstractmethod
    def get_signed_url(self, file_key: str, expires_in_seconds: int = 3600) -> str:
        """Generates a time-bound access URL for secure document sharing."""
        pass

    @abstractmethod
    def delete_file(self, file_key: str) -> bool:
        """Removes file from cloud storage."""
        pass

    @abstractmethod
    def file_exists(self, file_key: str) -> bool:
        """Checks if a file exists in storage."""
        pass