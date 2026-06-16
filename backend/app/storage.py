"""Object storage abstraction (H3).

Resumes, submission evidence, and screenshots go through a single `storage`
facade. Two backends:
  - **local** (default): files under UPLOAD_DIR/storage/<key>; served by the app.
  - **s3**: any S3-compatible bucket (AWS S3, MinIO, R2) when S3_BUCKET + creds
    are set; objects fetched/streamed via boto3, with presigned URLs.

Keeping one interface means multi-replica/Fargate works by flipping env vars —
no code change. `local_path(key)` always returns a readable local path
(downloading from S3 to a temp file when needed) so tools like pdfplumber work.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from .config import settings

S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL", "")          # for MinIO/R2; empty = AWS
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_PUBLIC_URL_TTL = int(os.getenv("S3_PRESIGN_TTL", "900"))

_LOCAL_ROOT = settings.UPLOAD_DIR / "storage"
_LOCAL_ROOT.mkdir(parents=True, exist_ok=True)


class _LocalBackend:
    name = "local"

    def save_bytes(self, key: str, data: bytes) -> str:
        path = _LOCAL_ROOT / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def save_file(self, key: str, local_path: str) -> str:
        return self.save_bytes(key, Path(local_path).read_bytes())

    def open_bytes(self, key: str) -> Optional[bytes]:
        path = _LOCAL_ROOT / key
        return path.read_bytes() if path.exists() else None

    def local_path(self, key: str) -> Optional[str]:
        path = _LOCAL_ROOT / key
        return str(path) if path.exists() else None

    def exists(self, key: str) -> bool:
        return (_LOCAL_ROOT / key).exists()

    def url(self, key: str) -> Optional[str]:
        return None  # served by the app


class _S3Backend:
    name = "s3"

    def __init__(self):
        import boto3
        self._c = boto3.client("s3", region_name=S3_REGION,
                               endpoint_url=S3_ENDPOINT or None)

    def save_bytes(self, key: str, data: bytes) -> str:
        self._c.put_object(Bucket=S3_BUCKET, Key=key, Body=data)
        return key

    def save_file(self, key: str, local_path: str) -> str:
        self._c.upload_file(local_path, S3_BUCKET, key)
        return key

    def open_bytes(self, key: str) -> Optional[bytes]:
        try:
            return self._c.get_object(Bucket=S3_BUCKET, Key=key)["Body"].read()
        except Exception:
            return None

    def local_path(self, key: str) -> Optional[str]:
        data = self.open_bytes(key)
        if data is None:
            return None
        fd, tmp = tempfile.mkstemp(suffix="-" + os.path.basename(key))
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return tmp

    def exists(self, key: str) -> bool:
        try:
            self._c.head_object(Bucket=S3_BUCKET, Key=key)
            return True
        except Exception:
            return False

    def url(self, key: str) -> Optional[str]:
        try:
            return self._c.generate_presigned_url(
                "get_object", Params={"Bucket": S3_BUCKET, "Key": key},
                ExpiresIn=S3_PUBLIC_URL_TTL)
        except Exception:
            return None


def _make_backend():
    if S3_BUCKET:
        try:
            return _S3Backend()
        except Exception as exc:  # boto3 missing / misconfigured → safe fallback
            print(f"[storage] S3 configured but unavailable ({exc}); using local")
    return _LocalBackend()


storage = _make_backend()
