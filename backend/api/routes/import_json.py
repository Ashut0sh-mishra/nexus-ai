"""POST /api/import/json \u2014 Phase 6AN-JsonImport.

Accepts a user-supplied JSON payload (or a small uploaded .json file) and
queues a normal generation task that grounds on the payload instead of the
web. The deck flows through the same pipeline as ``/api/generate`` so all
the strategy / narrative / planner / writer steps still run \u2014 the only
difference is that the SEARCH step skips Tavily and reads the seed JSON
from the task's memory directory instead.

Two intake shapes are supported:

* **Free-form JSON payload** (``data`` field). Anything the LLM can read
  as research: lists of facts, a market overview, an annotated dataset,
  meeting notes. Serialized verbatim into ``seed_research.json``.

* **Pre-built slides** (``slides`` field). Same shape as the deck
  endpoint returns. We validate against ``agent.slide_schema`` and
  persist them directly as a completed deck \u2014 no LLM call. Mirrors
  the ``/api/import/pptx`` import path so the imported deck is editable
  immediately.

The endpoint is intentionally permissive on JSON content; the pipeline's
existing critic + grounding gates handle quality.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from agent.memory import AgentMemory
from agent.slide_schema import validate_deck
from database.connection import get_db
from database.models import SlideDeck, Task

logger = logging.getLogger("nexus.api.import_json")

router = APIRouter()

# Cap the seed payload so a runaway JSON file cannot blow the memory dir
# or the LLM context window. The loop's seed reader also slices at 20k
# chars before handing to the writer.
_MAX_SEED_CHARS = 64_000


class ImportJsonRequest(BaseModel):
    topic: str = Field(..., min_length=4, max_length=2000)
    slide_count: int = Field(8, ge=4, le=20)
    theme: str = Field("Editorial", max_length=64)
    user_id: Optional[str] = None
    # Free-form JSON payload to use as grounding data. Mutually
    # compatible with ``slides`` \u2014 if both are present, ``slides``
    # wins and ``data`` is recorded for reference only.
    data: Optional[Any] = None
    # Pre-built slide array (skips the LLM entirely).
    slides: Optional[list[dict[str, Any]]] = None

    @field_validator("topic")
    @classmethod
    def _strip_topic(cls, v: str) -> str:
        return v.strip()


class ImportJsonResponse(BaseModel):
    task_id: str
    status: str
    mode: str  # "generate" | "direct"
    slide_count: Optional[int] = None


def _serialize_seed(data: Any) -> str:
    """Render a JSON payload as the text the agent loop will read.

    Strings pass through. Anything else is dumped as pretty JSON so the
    LLM can scan headings and named values; lists/dicts are kept intact.
    Output is hard-capped at ``_MAX_SEED_CHARS``.
    """
    if isinstance(data, str):
        text = data
    else:
        try:
            text = json.dumps(data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            text = str(data)
    if len(text) > _MAX_SEED_CHARS:
        text = text[:_MAX_SEED_CHARS] + "\n... (truncated)"
    return text


@router.post(
    "/import/json",
    response_model=ImportJsonResponse,
    response_model_exclude_none=True,
)
async def import_json(
    payload: ImportJsonRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ImportJsonResponse:
    """Create a task that grounds on user-supplied JSON.

    * If ``slides`` is supplied and validates, persist directly as a
      completed deck (``mode="direct"``).
    * Otherwise enqueue a normal Celery generation but with
      ``search_web=False`` and the JSON written to the task memory dir as
      ``seed_research.json``. The agent loop picks up the seed file and
      uses it in place of web research (``mode="generate"``).
    """
    trace_id = getattr(request.state, "trace_id", "-")

    # ── Direct deck import path ────────────────────────────────────────
    if payload.slides:
        results = validate_deck(payload.slides)
        invalid = [
            {"index": i, "errors": [e.to_dict() for e in r.errors]}
            for i, r in enumerate(results)
            if not r.ok
        ]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_deck",
                    "message": "Slides failed schema validation.",
                    "invalid_slides": invalid,
                },
            )
        normalized = [r.normalized for r in results if r.normalized is not None]
        if not normalized:
            raise HTTPException(
                status_code=400,
                detail={"error": "empty", "message": "No valid slides supplied."},
            )

        task = Task(
            user_id=payload.user_id,
            topic=payload.topic,
            slide_count=len(normalized),
            theme=payload.theme or "Editorial",
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
            theme=task.theme,
            slide_count=len(normalized),
        )
        db.add(deck)
        await db.commit()
        await db.refresh(task)
        logger.info(
            "import_json.direct_ok",
            extra={
                "trace_id": trace_id,
                "task_id": task.id,
                "slide_count": len(normalized),
            },
        )
        return ImportJsonResponse(
            task_id=task.id, status="done", mode="direct", slide_count=len(normalized)
        )

    # ── Seed-research generation path ──────────────────────────────────
    if payload.data is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_payload",
                "message": "Provide either 'slides' (pre-built deck) or 'data' (JSON to ground on).",
            },
        )

    seed_text = _serialize_seed(payload.data)
    if not seed_text.strip():
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_data", "message": "JSON payload is empty."},
        )

    try:
        task = Task(
            user_id=payload.user_id,
            topic=payload.topic,
            slide_count=payload.slide_count,
            theme=payload.theme or "Editorial",
            # Skip web search; the loop will pick up seed_research.json.
            search_web=False,
            status="pending",
            current_step="queued",
            progress_pct=0.0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)
    except Exception as exc:
        await db.rollback()
        logger.exception("import_json.create_task_failed", extra={"trace_id": trace_id})
        raise HTTPException(status_code=500, detail="Could not create task.") from exc

    # Persist the seed payload into the task's memory dir so the worker
    # picks it up. Two files written for robustness:
    #   * seed_research.json \u2014 structured payload (preferred)
    #   * seed_research.txt  \u2014 serialized text (fallback)
    try:
        memory = AgentMemory(task.id)
        memory.write_artifact("seed_research.json", payload.data)
        (memory.root / "seed_research.txt").write_text(seed_text, encoding="utf-8")
    except Exception as exc:
        logger.warning(
            "import_json.seed_write_failed",
            extra={"trace_id": trace_id, "task_id": task.id, "err": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail={"error": "seed_write_failed", "message": str(exc)},
        ) from exc

    # Enqueue the same Celery task /api/generate uses. min_sources=0
    # because there is no web research to gate on.
    try:
        from workers.tasks import run_generation_task

        run_generation_task.delay(task.id, 0)
    except Exception as exc:
        logger.warning(
            "import_json.enqueue_failed",
            extra={"trace_id": trace_id, "task_id": task.id, "err": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail={"error": "enqueue_failed", "message": str(exc)},
        ) from exc

    logger.info(
        "import_json.generate_ok",
        extra={
            "trace_id": trace_id,
            "task_id": task.id,
            "seed_chars": len(seed_text),
            "topic_preview": payload.topic[:80],
        },
    )
    return ImportJsonResponse(task_id=task.id, status="pending", mode="generate")
