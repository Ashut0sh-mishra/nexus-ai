"""POST /api/upload — accept user files and extract context.

Stores the file under ``settings.UPLOAD_DIR``, runs the format-aware parser
in :mod:`services.context_extractor`, and persists an ``UploadedFile`` row
with the extracted text + structured data. The returned ``file_id`` is later
passed to ``POST /api/generate`` (in ``file_ids``) so the agent loop can
ground the deck in user-supplied context.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.connection import get_db
from database.models import UploadedFile
from services import context_extractor
from services.intelligence_service import extract_business_intelligence
from utils.file_parser import (
    SUPPORTED_EXTENSIONS,
    build_storage_path,
    detect_file_type,
    is_allowed_extension,
)

logger = logging.getLogger("nexus.api.upload")

router = APIRouter()


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class UploadResponse(BaseModel):
    file_id: str = Field(..., description="UUID identifying the stored file.")
    filename: str = Field(..., description="Original (sanitized) filename.")
    file_type: str = Field(
        ...,
        description=(
            "Canonical type tag: csv | xlsx | json | pdf | docx | pptx | txt | md"
        ),
    )
    file_size: int = Field(..., description="Stored size in bytes.")
    extracted_preview: str = Field(
        "", description="First ~500 chars of extracted text for UI preview."
    )
    has_structured_data: bool = Field(
        False,
        description="True if the parser produced tabular / structured output.",
    )
    error: Optional[str] = Field(
        None, description="Non-fatal parser warning, if any."
    )


class UploadedFileInfo(BaseModel):
    file_id: str
    filename: str
    file_type: str
    file_size: int
    has_structured_data: bool
    extracted_preview: str
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a context file (CSV/XLSX/JSON/PDF/DOCX/PPTX/TXT/MD).",
)
async def upload_file(
    request: Request,
    file: UploadFile = File(..., description="Binary file payload."),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Persist a single uploaded file, parse it, and return a ``file_id``."""
    trace_id = getattr(request.state, "trace_id", "-")

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    if not is_allowed_extension(file.filename):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. Allowed: "
                + ", ".join(sorted(settings.allowed_upload_extensions or SUPPORTED_EXTENSIONS))
            ),
        )

    file_id, target_path = build_storage_path(file.filename)
    file_type = detect_file_type(file.filename)
    max_bytes = settings.max_upload_bytes

    # Stream to disk in chunks; reject anything over the configured cap.
    written = 0
    try:
        with target_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    out.close()
                    target_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB limit.",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("upload.write_failed", extra={"trace_id": trace_id})
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not store file: {exc}") from exc
    finally:
        await file.close()

    # Parse the saved file. Errors are non-fatal — record them on the row.
    result = context_extractor.extract(target_path, file_type)

    # Run business-intelligence extraction over the parser output. Failures
    # never block the upload — we just persist what we have.
    try:
        bi = extract_business_intelligence(result.text, result.data)
    except Exception as exc:  # pragma: no cover
        logger.warning("upload.bi_failed", extra={"err": str(exc)})
        bi = {}

    extracted_data: dict | None = None
    if result.data or bi:
        extracted_data = dict(result.data or {})
        if bi:
            extracted_data["business_intelligence"] = bi

    record = UploadedFile(
        id=file_id,
        # Store the user-facing original name so prompts/UI never echo the
        # internal uuid-prefixed disk name. The on-disk path is kept in file_path.
        filename=safe_filename(file.filename),
        file_type=file_type,
        file_path=str(target_path),
        file_size=written,
        extracted_text=(result.text or "")[:200_000] or None,
        extracted_data_json=extracted_data,
    )
    try:
        db.add(record)
        await db.commit()
        await db.refresh(record)
    except Exception as exc:
        await db.rollback()
        target_path.unlink(missing_ok=True)
        logger.exception("upload.db_failed", extra={"trace_id": trace_id})
        raise HTTPException(status_code=500, detail="Could not persist upload.") from exc

    logger.info(
        "upload.ok",
        extra={
            "trace_id": trace_id,
            "file_id": file_id,
            "file_type": file_type,
            "file_size": written,
            "parser_error": result.error,
        },
    )
    return UploadResponse(
        file_id=record.id,
        filename=record.filename,
        file_type=record.file_type,
        file_size=record.file_size,
        extracted_preview=result.preview(500),
        has_structured_data=bool(result.data),
        error=result.error,
    )


@router.get(
    "/upload/{file_id}",
    response_model=UploadedFileInfo,
    summary="Fetch metadata + extracted preview for a stored file.",
)
async def get_uploaded_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
) -> UploadedFileInfo:
    res = await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return UploadedFileInfo(
        file_id=row.id,
        filename=row.filename,
        file_type=row.file_type,
        file_size=row.file_size,
        has_structured_data=bool(row.extracted_data_json),
        extracted_preview=(row.extracted_text or "")[:500],
    )


@router.delete(
    "/upload/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a stored upload (file + DB row).",
)
async def delete_uploaded_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    res = await db.execute(select(UploadedFile).where(UploadedFile.id == file_id))
    row = res.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="File not found.")
    try:
        from pathlib import Path

        Path(row.file_path).unlink(missing_ok=True)
    except Exception as exc:  # pragma: no cover
        logger.warning("upload.unlink_failed", extra={"file_id": file_id, "err": str(exc)})
    await db.delete(row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
