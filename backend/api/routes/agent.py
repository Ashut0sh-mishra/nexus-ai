"""Phase 2.5 — POST /api/agent/test-run.

Safe internal surface that exercises :class:`agent.runtime.AgentRuntime`.

Deliberately scoped:
- Server enforces a *safe default allowlist* and rejects requests that ask for
  shell / file-write / deploy / browser-console tools.
- Browser navigation / view tools are only allowed when the browser layer is
  in its disabled-safe stub state.
- No real LLM call in tests: tests override ``get_planner`` with a fake.
- Persists ``AgentRun`` and ``AgentStep`` rows via the runtime, which uses
  ``services.agent_run_service``.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.planners import build_default_planner
from agent.runtime import AgentRuntime, Planner, RuntimeConfig
from agent.tools import TOOLS
from config import settings
from database.connection import get_db
from database.models import User
from services.agent_run_service import list_artifacts_for_run
from services.auth_service import AuthService

logger = logging.getLogger("nexus.api.agent")

router = APIRouter()
_auth_svc = AuthService()


# ── Safety policy ──────────────────────────────────────────────────────────
DANGEROUS_TOOLS: set[str] = {
    "shell_exec",
    "shell_view",
    "shell_wait",
    "shell_write_to_process",
    "shell_kill_process",
    "file_write",
    "file_str_replace",
    "deploy_expose_port",
    "deploy_apply_deployment",
    "make_manus_page",
    "browser_console_exec",
}

# Always-safe baseline: messaging, search, idle, file READ.
_SAFE_BASE: set[str] = {
    "message_notify_user",
    "message_ask_user",
    "info_search_web",
    "idle",
    "file_read",
    "file_find_in_content",
    "file_find_by_name",
}

# Browser navigation / view tools are *only* added to the default allowlist
# when the real Playwright layer is disabled, i.e. they are guaranteed to be
# inert stubs. When BROWSER_ENABLED is true the operator must opt in
# explicitly per-run.
_BROWSER_SAFE_WHEN_DISABLED: set[str] = {
    "browser_view",
    "browser_navigate",
    "browser_restart",
    "browser_click",
    "browser_input",
    "browser_move_mouse",
    "browser_press_key",
    "browser_select_option",
    "browser_scroll_up",
    "browser_scroll_down",
    "browser_console_view",
}


def safe_default_allowlist() -> set[str]:
    base = set(_SAFE_BASE)
    if not getattr(settings, "BROWSER_ENABLED", False):
        base |= _BROWSER_SAFE_WHEN_DISABLED
    # Defence-in-depth: never let a dangerous tool sneak in via this default.
    return (base & set(TOOLS.keys())) - DANGEROUS_TOOLS


# ── Schemas ───────────────────────────────────────────────────────────────
class AgentRunRequest(BaseModel):
    goal: str = Field(..., min_length=4, max_length=4000)
    max_steps: Optional[int] = Field(None, ge=1, le=20)
    allowed_tools: Optional[list[str]] = None
    user_id: Optional[str] = None


class StepSummary(BaseModel):
    index: int
    kind: str
    action: Optional[str] = None
    error: Optional[str] = None


class AgentRunResponse(BaseModel):
    run_id: str
    status: str
    final: Optional[str] = None
    steps: list[StepSummary]
    error: Optional[str] = None
    artifacts: dict = Field(
        default_factory=lambda: {"total": 0, "sources": 0, "by_type": {}}
    )


# ── Dependency: planner ───────────────────────────────────────────────────
async def get_planner() -> Planner:
    """Default planner provider (AIService). Tests override this."""
    planner = build_default_planner()
    if planner is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "no_ai_provider_configured",
                "hint": "Set GROQ_API_KEY (or another provider) in the backend env.",
            },
        )
    return planner


# ── Dependency: authentication ────────────────────────────────────────────
async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a valid bearer token issued by ``AuthService.create_access_token``.

    Mirrors the inline pattern used by ``GET /api/auth/me``. Returns the
    persisted ``User`` row. Tests override this dependency to inject a fake
    user and bypass JWT verification.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = _auth_svc.decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    user_id = payload.get("sub") if isinstance(payload, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


# ── Route ─────────────────────────────────────────────────────────────────
@router.post("/agent/test-run", response_model=AgentRunResponse)
async def agent_test_run(
    payload: AgentRunRequest,
    db: AsyncSession = Depends(get_db),
    planner: Planner = Depends(get_planner),
    current_user: User = Depends(get_current_user),
) -> AgentRunResponse:
    # Resolve effective allowlist.
    if payload.allowed_tools is None:
        allowed = safe_default_allowlist()
    else:
        requested = set(payload.allowed_tools)
        unknown = requested - set(TOOLS.keys())
        if unknown:
            raise HTTPException(
                status_code=400,
                detail={"error": "unknown_tools", "tools": sorted(unknown)},
            )
        forbidden = requested & DANGEROUS_TOOLS
        if forbidden:
            raise HTTPException(
                status_code=400,
                detail={"error": "unsafe_tools_requested", "tools": sorted(forbidden)},
            )
        allowed = requested

    if not allowed:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_allowlist"},
        )

    cfg = RuntimeConfig(
        max_steps=payload.max_steps or 8,
        max_tool_failures=3,
        per_step_timeout=20.0,
        allowed_tools=allowed,
    )
    runtime = AgentRuntime(planner, cfg)

    result = await runtime.run(
        db,
        goal=payload.goal,
        user_id=current_user.id,
    )

    # Phase 3: surface artifact counts (no large payloads in the response).
    artifacts = await list_artifacts_for_run(db, result.run_id)
    by_type: dict[str, int] = {}
    for a in artifacts:
        by_type[a.artifact_type] = by_type.get(a.artifact_type, 0) + 1
    artifact_summary = {
        "total": len(artifacts),
        "sources": by_type.get("source", 0),
        "by_type": by_type,
    }

    return AgentRunResponse(
        run_id=result.run_id,
        status=result.status,
        final=result.final_text,
        steps=[
            StepSummary(index=s.index, kind=s.kind, action=s.action, error=s.error)
            for s in result.steps
        ],
        error=result.error,
        artifacts=artifact_summary,
    )
