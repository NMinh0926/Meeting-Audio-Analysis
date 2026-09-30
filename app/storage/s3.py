"""S3-compatible storage for original recordings (SeaweedFS in compose; AWS S3 or R2 by configuration only)."""
import logging
from pathlib import Path
from typing import Any, BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)

_MISSING_CODES = {"404", "NoSuchKey", "NotFound"}


class StorageError(Exception):
    pass


class ObjectNotFoundError(StorageError):
    pass


class S3Storage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str,
                 region: str = "us-east-1", client: Any = None):
        self.bucket = bucket
        # Path-style addressing works for SeaweedFS and R2; virtual-host style needs DNS per bucket.
        self.client = client or boto3.client(
            "s3", endpoint_url=endpoint or None, aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None, region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                          retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=5, read_timeout=60),
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "S3Storage":
        return cls(settings.S3_ENDPOINT, settings.S3_ACCESS_KEY, settings.S3_SECRET_KEY,
                   settings.S3_BUCKET, settings.S3_REGION)

    def _fail(self, action: str, key: str, exc: Exception) -> StorageError:
        code = exc.response.get("Error", {}).get("Code") if isinstance(exc, ClientError) else type(exc).__name__
        logger.error("storage %s failed bucket=%s key=%s code=%s", action, self.bucket, key, code)
        if code in _MISSING_CODES:
            return ObjectNotFoundError(f"Object not found: {key}")
        return StorageError(f"Storage {action} failed for {key}: {code}")

    def upload(self, key: str, fileobj: BinaryIO, content_type: str) -> None:
        """Stream a file object to storage (multipart for large files)."""
        try:
            self.client.upload_fileobj(fileobj, self.bucket, key, ExtraArgs={"ContentType": content_type})
        except (BotoCoreError, ClientError) as exc:
            raise self._fail("upload", key, exc) from exc

    def download(self, key: str, destination: Path) -> None:
        try:
            self.client.download_file(self.bucket, key, str(destination))
        except (BotoCoreError, ClientError) as exc:
            raise self._fail("download", key, exc) from exc

    def delete(self, key: str) -> None:
        # S3 delete is idempotent: a missing key is not an error.
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise self._fail("delete", key, exc) from exc
