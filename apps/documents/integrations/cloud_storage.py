import logging
from pathlib import Path
from typing import Optional
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from .storage_backend import StorageBackend

logger = logging.getLogger(__name__)

class S3StorageBackend(StorageBackend):
    """
    Production-ready S3 adapter compatible with:
    - AWS S3
    - DigitalOcean Spaces
    - Wasabi / MinIO / Backblaze B2 (S3-compatible)
    """
    def __init__(self):
        # Fallbacks provided so settings errors don't crash the app immediately on import
        self.bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
        self.region_name = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
        self.endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
        self.access_key = getattr(settings, "AWS_ACCESS_KEY_ID", "")
        self.secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", "")

        if not self.bucket_name:
            logger.warning("AWS_STORAGE_BUCKET_NAME is not configured. S3 Storage may fail.")

        # Initialize S3 Client
        self.client = boto3.client(
            "s3",
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name,
            endpoint_url=self.endpoint_url
        )

    def upload_file(self, local_path: str | Path, destination_key: str, content_type: str = "application/pdf") -> str:
        try:
            extra_args = {"ContentType": content_type, "ServerSideEncryption": "AES256"}
            self.client.upload_file(str(local_path), self.bucket_name, destination_key, ExtraArgs=extra_args)
            return self._build_public_url(destination_key)
        except ClientError as e:
            logger.error(f"S3 upload failed for {destination_key}: {e}")
            raise

    def get_signed_url(self, file_key: str, expires_in_seconds: int = 3600) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": file_key},
                ExpiresIn=expires_in_seconds
            )
        except ClientError as e:
            logger.error(f"Failed to generate signed URL for {file_key}: {e}")
            raise

    def delete_file(self, file_key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete failed for {file_key}: {e}")
            return False

    def file_exists(self, file_key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except ClientError as e:
            return e.response["Error"]["Code"] == "404"

    def _build_public_url(self, key: str) -> str:
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket_name}/{key}"
        return f"https://{self.bucket_name}.s3.{self.region_name}.amazonaws.com/{key}"