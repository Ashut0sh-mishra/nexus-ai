"""POST /api/import/pptx — Phase 6S PPTX ingestion endpoint.

Accepts a multipart .pptx upload, converts it into a canonical NEXUS deck,
validates it against :func:`agent.slide_schema.validate_deck`, and persists
a ``Task`` (status=``done``) plus ``SlideDeck`` row so the imported deck
flows through the existing /api/slides, /api/export, and /api/share
surface unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from agent.slide_schema import validate_deck
from database.connection import get_db
from database.models import SlideDeck, Task
from services.pptx_import_service import (
    PPTXImportError,
    import_pptx_bytes,
)

logger = logging.getLogger("nexus.api.import")

router = APIRouter()

MAX_BYTES = 100 * 1024 * 1024  # 100 MB
PPTX_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/octet-stream",  # some browsers/curl
}


@router.post("/import/pptx")
async def import_pptx(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Import a .pptx file into a new NEXUS task + deck.

    Errors:
    * 400 ``bad_extension`` — filename does not end in ``.pptx``.
    * 400 ``too_large`` — file exceeds 100 MB.
    * 400 ``corrupt`` — file cannot be parsed as a PPTX archive.
    * 400 ``empty`` — PPTX has no slides.
    * 400 ``invalid_deck`` — converted deck failed schema validation
      (should be unreachable for the conservative converter; surfaced
      defensively so a future relaxed converter cannot silently persist
      a malformed deck).
    """
    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".pptx"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bad_extension",
                "message": "Only .pptx files are accepted.",
            },
        )

    # Read up to MAX_BYTES + 1 so we can reject over-limit uploads
    # without buffering arbitrary amounts of memory.
    chunk_size = 1 * 1024 * 1024
    buf = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_BYTES:
            logger.info("import.too_large", extra={"bytes": len(buf)})
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "too_large",
                    "message": f"File exceeds the {MAX_BYTES // (1024 * 1024)} MB limit.",
                },
            )

    try:
        imported = import_pptx_bytes(bytes(buf), filename=filename)
    except PPTXImportError as exc:
        logger.info(
            "import.rejected",
            extra={"code": exc.code, "filename": filename},
        )
        raise HTTPException(
            status_code=400,
            detail={"error": exc.code, "message": exc.message},
        )

    # Validate the converted deck. The converter is conservative so this
    # should always pass, but if it ever returns a malformed slide we want
    # the failure to surface as a clean 400 instead of a corrupt SlideDeck
    # row.
    results = validate_deck(imported.slides)
    invalid = [
        {"index": i, "errors": [e.to_dict() for e in r.errors]}
        for i, r in enumerate(results)
        if not r.ok
    ]
    if invalid:  # pragma: no cover - converter should never produce invalid slides
        logger.error(
            "import.invalid_deck", extra={"invalid_count": len(invalid)}
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_deck",
                "message": "Imported deck failed schema validation.",
                "invalid_slides": invalid,
            },
        )

    normalized = [r.normalized for r in results if r.normalized is not None]

    # Persist as a completed Task + SlideDeck so the imported deck flows
    # through GET /api/slides, PUT /api/slides, /api/export, /api/share
    # without any new code paths.
    task = Task(
        topic=imported.title,
        slide_count=len(normalized),
        theme="Editorial",
        search_web=False,
        status="done",
        progress_pct=100.0,
        current_step="imported",
        completed_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.flush()

    deck = SlideDeck(
        task_id=task.id,
        slide_data=normalized,
        theme="Editorial",
        slide_count=len(normalized),
    )
    db.add(deck)
    await db.commit()
    await db.refresh(task)
    await db.refresh(deck)

    logger.info(
        "import.ok",
        extra={
            "task_id": task.id,
            "slide_count": deck.slide_count,
            "source_slides": imported.source_slide_count,
            "source_filename": imported.source_filename,
        },
    )

    return {
        "task_id": task.id,
        "topic": task.topic,
        "theme": deck.theme,
        "slide_count": deck.slide_count,
        "slides": deck.slide_data,
        "source": {
            "filename": imported.source_filename,
            "source_slide_count": imported.source_slide_count,
            "imported_slide_count": len(normalized),
            "truncated": imported.source_slide_count > len(normalized),
        },
    }
