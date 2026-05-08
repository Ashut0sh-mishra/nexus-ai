"""Utilities for safely handling user-uploaded files.

Used by ``backend/api/routes/upload.py``. Keeps file-type detection,
extension validation, and safe-name handling in one place so route code
can stay thin.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path
from typing import Final

from config import settings

# Canonical extension set for the AI PPT generator pipeline.
SUPPORTED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {"csv", "xlsx", "xls", "json", "pdf", "docx", "pptx", "txt", "md"}
)

# Extensions we explicitly never accept regardless of MIME, to avoid hosting
# executable content in /storage/uploads which is served by /api/files in dev.
BLOCKED_EXTENSIONS: Final[frozenset[str]] = frozenset(
    {
        "exe", "bat", "cmd", "com", "sh", "ps1", "msi", "scr",
        "js", "ts", "html", "htm", "svg", "php", "py", "pyc",
        "dll", "so", "dylib", "jar",
    }
)


def get_extension(filename: str) -> str:
    """Return lowercase extension without the leading dot, or ``""``."""
    if not filename:
        return ""
    name = filename.strip().rsplit(".", 1)
    return name[1].lower() if len(name) == 2 else ""


def is_allowed_extension(filename: str) -> bool:
    ext = get_extension(filename)
    if not ext or ext in BLOCKED_EXTENSIONS:
        return False
    allowed = settings.allowed_upload_extensions or SUPPORTED_EXTENSIONS
    return ext in allowed


def safe_filename(filename: str) -> str:
    """Strip path components, normalize unicode, keep only [A-Za-z0-9._-]."""
    base = Path(filename or "").name
    norm = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode()
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", norm).strip("._") or "file"
    # Guard against silly long names.
    return cleaned[:200]


def build_storage_path(filename: str) -> tuple[str, Path]:
    """Return ``(file_id, absolute_path)`` for a new upload.

    The on-disk filename is ``{uuid}_{safe_original_name}`` to keep originals
    debuggable while preventing collisions and traversal.
    """
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    final = settings.UPLOAD_DIR / f"{file_id}_{safe_filename(filename)}"
    return file_id, final


def detect_file_type(filename: str) -> str:
    """Map an extension to the canonical ``file_type`` stored on UploadedFile."""
    ext = get_extension(filename)
    if ext == "xls":
        return "xlsx"  # parsed via pandas with the same loader
    return ext
