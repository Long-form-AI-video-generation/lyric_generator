"""Cloudflare R2 / AWS S3 / SeaweedFS Object Storage Service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from backend.core.config import settings

logger = logging.getLogger(__name__)


class S3StorageService:
    """Manages uploads, downloads, and presigned URLs for Cloudflare R2 / AWS S3 / SeaweedFS."""

    def __init__(self) -> None:
        self.bucket = settings.s3_bucket
        self.endpoint_url = settings.s3_endpoint_url
        self.region = settings.s3_region
        self.access_key = settings.aws_access_key_id
        self.secret_key = settings.aws_secret_access_key
        self.expiry = settings.s3_presigned_expiry_seconds
        self._client: Any = None

    def is_configured(self) -> bool:
        """Returns True if S3/R2/SeaweedFS storage is enabled and credentials are present."""
        return bool(settings.use_s3_storage and self.bucket and self.access_key and self.secret_key)

    @property
    def client(self) -> Any:
        if self._client is None:
            # S3v4 + path-style addressing ensures seamless compatibility across Cloudflare R2,
            # AWS S3, MinIO, and SeaweedFS
            s3_config = Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
            )
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=s3_config,
            )
        return self._client

    def ensure_bucket(self) -> bool:
        """Ensures that the S3/R2/SeaweedFS bucket exists, creating it if needed."""
        if not self.is_configured():
            return False

        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except ClientError as exc:
            err_code = str(exc.response.get("Error", {}).get("Code", ""))
            if err_code in ("404", "NoSuchBucket", "NotFound"):
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    logger.info("Created S3/SeaweedFS bucket: %s", self.bucket)
                    return True
                except Exception as create_exc:
                    logger.error("Failed to auto-create bucket %s: %s", self.bucket, create_exc)
                    return False
            logger.error("Failed to inspect bucket %s: %s", self.bucket, exc)
            return False

    def upload_file(
        self,
        local_path: Path | str,
        s3_key: str,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """Uploads a local file to the configured S3/R2/SeaweedFS bucket."""
        if not self.is_configured():
            logger.info("S3 storage not configured. Skipping S3 upload for %s", s3_key)
            return False

        path = Path(local_path)
        if not path.is_file():
            logger.error("Local file does not exist: %s", local_path)
            return False

        extra_args = {"ContentType": content_type}
        try:
            self.client.upload_file(
                str(path),
                self.bucket,
                s3_key,
                ExtraArgs=extra_args,
            )
            logger.info("Successfully uploaded %s to s3://%s/%s", path, self.bucket, s3_key)
            return True
        except ClientError as exc:
            err_code = str(exc.response.get("Error", {}).get("Code", ""))
            if err_code in ("NoSuchBucket", "404", "NotFound"):
                logger.info("Bucket %s not found. Auto-creating bucket for SeaweedFS/S3...", self.bucket)
                if self.ensure_bucket():
                    try:
                        self.client.upload_file(
                            str(path),
                            self.bucket,
                            s3_key,
                            ExtraArgs=extra_args,
                        )
                        logger.info("Successfully uploaded %s after creating bucket %s", path, self.bucket)
                        return True
                    except Exception as retry_exc:
                        logger.error("Retry upload failed for %s: %s", s3_key, retry_exc)
            logger.error("Failed to upload %s to S3: %s", s3_key, exc)
            return False

    def download_file(self, s3_key: str, dest_path: Path | str) -> bool:
        """Downloads an object from the S3/R2 bucket to local disk."""
        if not self.is_configured():
            logger.info("S3 storage not configured. Cannot download %s", s3_key)
            return False

        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            self.client.download_file(self.bucket, s3_key, str(dest))
            logger.info("Successfully downloaded s3://%s/%s to %s", self.bucket, s3_key, dest)
            return True
        except ClientError as exc:
            logger.error("Failed to download %s from S3: %s", s3_key, exc)
            return False

    def generate_presigned_download_url(
        self,
        s3_key: str,
        expires_in: int | None = None,
        download_filename: str | None = None,
    ) -> str | None:
        """Generates a secure presigned GET URL for streaming or downloading."""
        if not self.is_configured():
            return None

        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": s3_key,
        }
        if download_filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'

        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=expires_in or self.expiry,
            )
            return str(url)
        except ClientError as exc:
            logger.error("Failed to generate presigned download URL for %s: %s", s3_key, exc)
            return None

    def delete_file(self, s3_key: str) -> bool:
        """Deletes an object from the S3/R2 bucket."""
        if not self.is_configured():
            return False

        try:
            self.client.delete_object(Bucket=self.bucket, Key=s3_key)
            logger.info("Deleted object s3://%s/%s", self.bucket, s3_key)
            return True
        except ClientError as exc:
            logger.error("Failed to delete %s from S3: %s", s3_key, exc)
            return False


s3_storage = S3StorageService()

