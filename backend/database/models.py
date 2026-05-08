"""SQLAlchemy ORM models for NEXUS."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(255))
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    credits_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="user")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    # Mirror of `topic` populated by the new /api/generate request body to
    # keep PRD vocabulary ("prompt") alongside the legacy column. Nullable
    # so existing rows are unaffected.
    prompt: Mapped[Optional[str]] = mapped_column(Text)
    slide_count: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    theme: Mapped[str] = mapped_column(String(64), default="Editorial", nullable=False)
    search_web: Mapped[bool] = mapped_column(default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_step: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(64))
    # New deck-level metadata for the AI PPT generator.
    context_sources: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    deck_plan_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    audience: Mapped[Optional[str]] = mapped_column(String(64))
    tone: Mapped[Optional[str]] = mapped_column(String(64))
    industry: Mapped[Optional[str]] = mapped_column(String(64))
    theme_settings: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[Optional[User]] = relationship(back_populates="tasks")
    slides: Mapped[Optional["SlideDeck"]] = relationship(
        back_populates="task", uselist=False, cascade="all, delete-orphan"
    )
    deck_slides: Mapped[list["Slide"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="Slide.slide_number",
    )
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    exports: Mapped[list["Export"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    share_tokens: Mapped[list["ShareToken"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class SlideDeck(Base):
    __tablename__ = "slides"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), unique=True, index=True
    )
    slide_data: Mapped[list] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    theme: Mapped[str] = mapped_column(String(64), default="Editorial", nullable=False)
    slide_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="slides")


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    file_url: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Background-export job tracking (added for /api/export polling flow).
    status: Mapped[str] = mapped_column(
        String(32), default="completed", server_default="completed", nullable=False
    )
    output_path: Mapped[Optional[str]] = mapped_column(Text)
    error_msg: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    task: Mapped[Task] = relationship(back_populates="exports")


class ShareToken(Base):
    __tablename__ = "share_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_share_token"),)

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True
    )
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="share_tokens")


class Slide(Base):
    """Per-slide row table for the AI PPT generator.

    Lives alongside the existing ``SlideDeck`` JSON-blob row (table ``slides``)
    so the legacy renderer keeps working. Editor / CRUD endpoints read and
    write these rows; the agent loop writes both stores in parallel.
    """

    __tablename__ = "deck_slides"
    __table_args__ = (
        UniqueConstraint("task_id", "slide_number", name="uq_deck_slide_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    slide_number: Mapped[int] = mapped_column(Integer, nullable=False)
    slide_type: Mapped[str] = mapped_column(
        String(32), default="content", nullable=False
    )
    title: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    subtitle: Mapped[Optional[str]] = mapped_column(String(512))
    content_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    chart_data_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    image_data_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    speaker_notes: Mapped[Optional[str]] = mapped_column(Text)
    layout_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    design_tokens: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    task: Mapped[Task] = relationship(back_populates="deck_slides")


class UploadedFile(Base):
    """User-uploaded source file (CSV/XLSX/JSON/PDF/DOCX/PPTX/TXT/MD).

    May be linked to a task on creation, or attached later by passing the
    file_id into ``POST /api/generate``.
    """

    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        index=True,
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extracted_text: Mapped[Optional[str]] = mapped_column(Text)
    extracted_data_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task: Mapped[Optional[Task]] = relationship(back_populates="uploaded_files")


# --------------------------------------------------------------------------- #
# Workspace + brand kit + asset library + audit + api keys + webhooks
# (PRD §12, §13, §16, §21). All tables are additive — existing rows untouched.
# --------------------------------------------------------------------------- #
class Workspace(Base):
    """Tenant-style container for users, brand kits, assets, decks."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    settings_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkspaceMember(Base):
    """Role-based membership: owner | admin | editor | viewer (PRD §21 RBAC)."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class BrandKit(Base):
    """Brand colors, typography, logo, voice — used to bias slide rendering."""

    __tablename__ = "brand_kits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)
    primary_color: Mapped[Optional[str]] = mapped_column(String(16))
    secondary_color: Mapped[Optional[str]] = mapped_column(String(16))
    accent_color: Mapped[Optional[str]] = mapped_column(String(16))
    background_color: Mapped[Optional[str]] = mapped_column(String(16))
    text_color: Mapped[Optional[str]] = mapped_column(String(16))
    palette_json: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    heading_font: Mapped[Optional[str]] = mapped_column(String(128))
    body_font: Mapped[Optional[str]] = mapped_column(String(128))
    logo_url: Mapped[Optional[str]] = mapped_column(Text)
    industry: Mapped[Optional[str]] = mapped_column(String(64))
    audience: Mapped[Optional[str]] = mapped_column(String(64))
    tone: Mapped[Optional[str]] = mapped_column(String(64))
    voice_guidelines: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Asset(Base):
    """Reusable image / icon / illustration in a workspace asset library."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="image", nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_url: Mapped[Optional[str]] = mapped_column(Text)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128))
    width: Mapped[Optional[int]] = mapped_column(Integer)
    height: Mapped[Optional[int]] = mapped_column(Integer)
    tags_json: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    collection: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    source: Mapped[Optional[str]] = mapped_column(String(32))  # upload | unsplash | pollinations | ai
    credit_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ApiKey(Base):
    """Per-user API key for SDK / external integrations (PRD §16, §21)."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scopes_json: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Webhook(Base):
    """Outbound webhook subscription (deck.completed, deck.failed, etc.)."""

    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(128))
    events_json: Mapped[Optional[list]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_delivery_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[Optional[int]] = mapped_column(Integer)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditLog(Base):
    """Append-only audit trail for security-relevant actions (PRD §21)."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    user_agent: Mapped[Optional[str]] = mapped_column(String(512))
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class DeckVersion(Base):
    """Snapshot of a deck for version history / undo (PRD §14)."""

    __tablename__ = "deck_versions"
    __table_args__ = (
        UniqueConstraint("task_id", "version", name="uq_deck_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(255))
    snapshot_json: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    created_by: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


