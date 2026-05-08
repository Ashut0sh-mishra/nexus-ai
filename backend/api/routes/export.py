"""POST /api/export/pptx and POST /api/export/pdf — generate downloadable files."""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import Export, SlideDeck, Task
from services.export_service import ExportService
from agent.theme_picker import resolve_theme

logger = logging.getLogger("nexus.api.export")

router = APIRouter()


class ExportRequest(BaseModel):
    task_id: str = Field(..., min_length=4)
    theme: str | None = None


class ExportResponse(BaseModel):
    download_url: str
    format: Literal["pptx", "pdf"]
    file_size: int


async def _load_deck(task_id: str, db: AsyncSession) -> tuple[Task, SlideDeck]:
    task_res = await db.execute(select(Task).where(Task.id == task_id))
    task = task_res.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "done":
        raise HTTPException(status_code=409, detail="Task not complete yet")
    deck_res = await db.execute(select(SlideDeck).where(SlideDeck.task_id == task_id))
    deck = deck_res.scalar_one_or_none()
    if deck is None:
        raise HTTPException(status_code=404, detail="Slide deck not found")
    return task, deck


@router.post("/export/pptx", response_model=ExportResponse)
async def export_pptx(
    payload: ExportRequest, db: AsyncSession = Depends(get_db)
) -> ExportResponse:
    task, deck = await _load_deck(payload.task_id, db)
    theme = resolve_theme(payload.theme or deck.theme, task.topic)
    try:
        url, size = await ExportService().export_pptx(
            task_id=task.id, slides=deck.slide_data or [], theme=theme
        )
    except Exception as exc:
        logger.exception("export.pptx_failed", extra={"task_id": task.id})
        raise HTTPException(status_code=500, detail=f"PPTX export failed: {exc}") from exc

    db.add(Export(task_id=task.id, format="pptx", file_url=url, file_size=size))
    await db.commit()
    return ExportResponse(download_url=url, format="pptx", file_size=size)


@router.post("/export/pdf", response_model=ExportResponse)
async def export_pdf(
    payload: ExportRequest, db: AsyncSession = Depends(get_db)
) -> ExportResponse:
    task, deck = await _load_deck(payload.task_id, db)
    theme = resolve_theme(payload.theme or deck.theme, task.topic)
    try:
        url, size = await ExportService().export_pdf(
            task_id=task.id, slides=deck.slide_data or [], theme=theme
        )
    except Exception as exc:
        logger.exception("export.pdf_failed", extra={"task_id": task.id})
        raise HTTPException(status_code=500, detail=f"PDF export failed: {exc}") from exc

    db.add(Export(task_id=task.id, format="pdf", file_url=url, file_size=size))
    await db.commit()
    return ExportResponse(download_url=url, format="pdf", file_size=size)
