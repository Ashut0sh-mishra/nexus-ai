"""Asset library: upload custom images/icons/illustrations (PRD §13)."""

from __future__ import annotations

import logging
import mimetypes
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user
from config import settings
from database.connection import get_db
from database.models import Asset, User
from utils.file_parser import safe_filename

logger = logging.getLogger("nexus.api.assets")
router = APIRouter()


_ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "svg"}
_MAX_BYTES = 10 * 1024 * 1024  # 10 MiB per asset


def _serialize(a: Asset) -> dict[str, Any]:
    return {
        "id": a.id,
        "workspace_id": a.workspace_id,
        "user_id": a.user_id,
        "kind": a.kind,
        "name": a.name,
        "url": a.file_url or f"/api/files/assets/{Path(a.file_path).name}",
        "size": a.file_size,
        "mime_type": a.mime_type,
        "width": a.width,
        "height": a.height,
        "tags": a.tags_json or [],
        "collection": a.collection,
        "source": a.source,
        "credit": a.credit_json or None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/assets", summary="List assets in the user's library.")
async def list_assets(
    workspace_id: Optional[str] = None,
    collection: Optional[str] = None,
    kind: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    q = select(Asset).where(Asset.user_id == user.id)
    if workspace_id:
        q = q.where(Asset.workspace_id == workspace_id)
    if collection:
        q = q.where(Asset.collection == collection)
    if kind:
        q = q.where(Asset.kind == kind)
    rows = (await db.execute(q.order_by(Asset.created_at.desc()).limit(500))).scalars().all()
    return [_serialize(a) for a in rows]


@router.post("/assets", status_code=status.HTTP_201_CREATED, summary="Upload an asset.")
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    workspace_id: Optional[str] = Form(None),
    collection: Optional[str] = Form(None),
    kind: str = Form("image"),
    tags: Optional[str] = Form(None),  # comma-separated
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    ext = (file.filename.rsplit(".", 1)[-1] or "").lower()
    if ext not in _ALLOWED_IMAGE_EXT:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported asset type. Allowed: {', '.join(sorted(_ALLOWED_IMAGE_EXT))}",
        )
    settings.ASSET_DIR.mkdir(parents=True, exist_ok=True)
    asset_id = uuid.uuid4().hex
    safe = safe_filename(file.filename)
    target = settings.ASSET_DIR / f"{asset_id}_{safe}"

    written = 0
    try:
        with target.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_BYTES:
                    out.close()
                    target.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="Asset exceeds 10 MB limit.")
                out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        target.unlink(missing_ok=True)
        logger.exception("assets.write_failed")
        raise HTTPException(status_code=500, detail="Could not store asset.") from exc
    finally:
        await file.close()

    mime, _ = mimetypes.guess_type(file.filename)
    width = height = None
    try:
        from PIL import Image  # type: ignore
        with Image.open(target) as im:
            width, height = im.size
    except Exception:
        pass  # PIL may not be installed; dimensions are best-effort.

    a = Asset(
        id=asset_id,
        workspace_id=workspace_id,
        user_id=user.id,
        kind=kind,
        name=name or safe,
        file_path=str(target),
        file_url=f"/api/files/assets/{target.name}",
        file_size=written,
        mime_type=mime,
        width=width,
        height=height,
        tags_json=[t.strip() for t in (tags or "").split(",") if t.strip()],
        collection=collection,
        source="upload",
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    logger.info("assets.upload", extra={"id": a.id, "user_id": user.id, "size": written})
    return _serialize(a)


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    collection: Optional[str] = None
    tags: Optional[list[str]] = None


@router.put("/assets/{asset_id}", summary="Rename / re-tag an asset.")
async def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    a = (await db.execute(select(Asset).where(Asset.id == asset_id))).scalar_one_or_none()
    if a is None or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="Asset not found")
    if payload.name is not None:
        a.name = payload.name
    if payload.collection is not None:
        a.collection = payload.collection
    if payload.tags is not None:
        a.tags_json = payload.tags
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return _serialize(a)


@router.delete("/assets/{asset_id}", summary="Delete an asset (and its file).")
async def delete_asset(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    a = (await db.execute(select(Asset).where(Asset.id == asset_id))).scalar_one_or_none()
    if a is None or a.user_id != user.id:
        raise HTTPException(status_code=404, detail="Asset not found")
    try:
        Path(a.file_path).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(a)
    await db.commit()
    return {"deleted": asset_id}
