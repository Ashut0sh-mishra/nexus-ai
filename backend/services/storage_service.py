"""Storage abstraction — Cloudflare R2 (S3 API) primary, local FS fallback."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger("nexus.services.storage")


class StorageService:
    def __init__(self) -> None:
        self._s3 = None
        if settings.has_r2:
            try:
                import boto3
                from botocore.config import Config

                self._s3 = boto3.client(
                    "s3",
                    endpoint_url=settings.R2_ENDPOINT,
                    aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                    config=Config(signature_version="s3v4"),
                    region_name="auto",
                )
            except Exception as exc:
                logger.warning("storage.r2_init_failed_falling_back_local", extra={"err": str(exc)})
                self._s3 = None

        Path(settings.EXPORT_DIR).mkdir(parents=True, exist_ok=True)

    def put(self, filename: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        if self._s3 is not None and settings.R2_BUCKET:
            try:
                self._s3.put_object(
                    Bucket=settings.R2_BUCKET,
                    Key=filename,
                    Body=data,
                    ContentType=content_type,
                )
                base = (settings.R2_PUBLIC_URL or "").rstrip("/")
                if base:
                    return f"{base}/{filename}"
                return self._presigned_url(filename)
            except Exception as exc:
                logger.warning("storage.r2_put_failed_local_fallback", extra={"err": str(exc)})

        # Local fallback — write under EXPORT_DIR and serve via /api/files static mount.
        path = Path(settings.EXPORT_DIR) / filename
        path.write_bytes(data)
        # Return a path-only URL so the frontend hits it through the Vite
        # proxy (or directly on the backend) regardless of host/port.
        return f"/api/files/{filename}"

    def _presigned_url(self, filename: str, expires: int = 3600) -> str:
        assert self._s3 is not None
        return self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.R2_BUCKET, "Key": filename},
            ExpiresIn=expires,
        )

    def local_path(self, filename: str) -> Path:
        return Path(settings.EXPORT_DIR) / filename
