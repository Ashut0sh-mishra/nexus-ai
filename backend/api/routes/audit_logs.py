"""Audit log query endpoint (PRD §21)."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from database.connection import SessionLocal, get_db
from database.models import AuditLog, User

router = APIRouter()


def _serialize(a: AuditLog) -> dict[str, Any]:
    return {
        "id": a.id,
        "user_id": a.user_id,
        "workspace_id": a.workspace_id,
        "action": a.action,
        "resource_type": a.resource_type,
        "resource_id": a.resource_id,
        "ip": a.ip_address,
        "user_agent": a.user_agent,
        "metadata": a.metadata_json or {},
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/audit-logs", summary="List recent audit log entries for the current user.")
async def list_audit_logs(
    limit: int = 100,
    workspace_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    q = select(AuditLog).where(AuditLog.user_id == user.id)
    if workspace_id:
        q = q.where(AuditLog.workspace_id == workspace_id)
    q = q.order_by(AuditLog.created_at.desc()).limit(min(max(limit, 1), 1000))
    rows = (await db.execute(q)).scalars().all()
    return [_serialize(r) for r in rows]


# --------------------------------------------------------------------------- #
# Programmatic write API (call from anywhere — opens its own session)
# --------------------------------------------------------------------------- #
async def record_audit(
    *,
    action: str,
    user_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Append-only writer. Errors are swallowed — auditing must never break flows."""
    try:
        async with SessionLocal() as db:
            entry = AuditLog(
                user_id=user_id,
                workspace_id=workspace_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                user_agent=(user_agent or "")[:512] or None,
                metadata_json=metadata or None,
            )
            db.add(entry)
            await db.commit()
    except Exception:  # pragma: no cover
        pass
