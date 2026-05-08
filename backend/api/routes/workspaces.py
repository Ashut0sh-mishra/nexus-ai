"""Workspace CRUD + member management (PRD §21)."""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from database.connection import get_db
from database.models import User, Workspace, WorkspaceMember

logger = logging.getLogger("nexus.api.workspaces")
router = APIRouter()


class WorkspaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = None


class MemberIn(BaseModel):
    user_id: str
    role: str = Field(default="viewer", pattern="^(owner|admin|editor|viewer)$")


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower())
    return s.strip("-")[:48] or "workspace"


def _serialize(w: Workspace) -> dict[str, Any]:
    return {
        "id": w.id,
        "name": w.name,
        "slug": w.slug,
        "owner_id": w.owner_id,
        "plan": w.plan,
        "settings": w.settings_json or {},
        "created_at": w.created_at.isoformat() if w.created_at else None,
    }


@router.get("/workspaces", summary="List workspaces the current user belongs to.")
async def list_workspaces(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    owned = (
        await db.execute(select(Workspace).where(Workspace.owner_id == user.id))
    ).scalars().all()
    member_ids = (
        await db.execute(
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
        )
    ).scalars().all()
    member_ws: list[Workspace] = []
    if member_ids:
        member_ws = (
            await db.execute(select(Workspace).where(Workspace.id.in_(list(member_ids))))
        ).scalars().all()
    seen: dict[str, Workspace] = {}
    for w in list(owned) + list(member_ws):
        seen[w.id] = w
    return [_serialize(w) for w in seen.values()]


@router.post("/workspaces", summary="Create a new workspace.")
async def create_workspace(
    payload: WorkspaceIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    base = _slugify(payload.slug or payload.name)
    slug = base
    n = 1
    while (
        await db.execute(select(Workspace).where(Workspace.slug == slug))
    ).scalar_one_or_none() is not None:
        n += 1
        slug = f"{base}-{n}"
    w = Workspace(name=payload.name.strip(), slug=slug, owner_id=user.id)
    db.add(w)
    await db.flush()
    db.add(WorkspaceMember(workspace_id=w.id, user_id=user.id, role="owner"))
    await db.commit()
    await db.refresh(w)
    logger.info("workspaces.create", extra={"id": w.id, "user_id": user.id})
    return _serialize(w)


@router.get("/workspaces/{workspace_id}", summary="Get one workspace.")
async def get_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    w = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if w is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _serialize(w)


@router.delete("/workspaces/{workspace_id}", summary="Delete a workspace (owner only).")
async def delete_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    w = (
        await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ).scalar_one_or_none()
    if w is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if w.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a workspace")
    await db.delete(w)
    await db.commit()
    return {"deleted": workspace_id}


@router.get("/workspaces/{workspace_id}/members", summary="List workspace members.")
async def list_members(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
        )
    ).scalars().all()
    return [
        {"id": r.id, "user_id": r.user_id, "role": r.role,
         "created_at": r.created_at.isoformat() if r.created_at else None}
        for r in rows
    ]


@router.post("/workspaces/{workspace_id}/members", summary="Add or update a member.")
async def add_member(
    workspace_id: str,
    payload: MemberIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    w = (await db.execute(select(Workspace).where(Workspace.id == workspace_id))).scalar_one_or_none()
    if w is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if w.owner_id != user.id:
        # Allow admins to add members too
        me = (
            await db.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if me is None or me.role not in {"owner", "admin"}:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
    existing = (
        await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == payload.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.role = payload.role
        db.add(existing)
        await db.commit()
        return {"id": existing.id, "user_id": existing.user_id, "role": existing.role}
    m = WorkspaceMember(workspace_id=workspace_id, user_id=payload.user_id, role=payload.role)
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return {"id": m.id, "user_id": m.user_id, "role": m.role}
