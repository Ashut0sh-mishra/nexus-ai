"""Add workspaces, workspace_members, brand_kits, assets, api_keys, webhooks,
audit_logs, deck_versions tables (PRD §12, §13, §14, §16, §21).

All operations are idempotent — they no-op if the table already exists, so
this is safe to run on dev DBs that ``init_models()`` has already populated.

Revision ID: 0003_workspaces_brand_assets
Revises: 0002_decks_uploads
Create Date: 2026-05-08 01:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0003_workspaces_brand_assets"
down_revision: Union[str, None] = "0002_decks_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return inspector.has_table(table)
    except Exception:
        return False


def _json():
    return sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    if not _has_table("workspaces"):
        op.create_table(
            "workspaces",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("slug", sa.String(64), unique=True, nullable=False),
            sa.Column("plan", sa.String(32), nullable=False, server_default="free"),
            sa.Column("settings_json", _json()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _has_table("workspace_members"):
        op.create_table(
            "workspace_members",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
            sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
        )

    if not _has_table("brand_kits"):
        op.create_table(
            "brand_kits",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("primary_color", sa.String(16)),
            sa.Column("secondary_color", sa.String(16)),
            sa.Column("accent_color", sa.String(16)),
            sa.Column("background_color", sa.String(16)),
            sa.Column("text_color", sa.String(16)),
            sa.Column("palette_json", _json()),
            sa.Column("heading_font", sa.String(128)),
            sa.Column("body_font", sa.String(128)),
            sa.Column("logo_url", sa.Text),
            sa.Column("industry", sa.String(64)),
            sa.Column("audience", sa.String(64)),
            sa.Column("tone", sa.String(64)),
            sa.Column("voice_guidelines", sa.Text),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _has_table("assets"):
        op.create_table(
            "assets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True),
            sa.Column("kind", sa.String(32), nullable=False, server_default="image", index=True),
            sa.Column("name", sa.String(512), nullable=False),
            sa.Column("file_path", sa.Text, nullable=False),
            sa.Column("file_url", sa.Text),
            sa.Column("file_size", sa.Integer, nullable=False, server_default="0"),
            sa.Column("mime_type", sa.String(128)),
            sa.Column("width", sa.Integer),
            sa.Column("height", sa.Integer),
            sa.Column("tags_json", _json()),
            sa.Column("collection", sa.String(128), index=True),
            sa.Column("source", sa.String(32)),
            sa.Column("credit_json", _json()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _has_table("api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
            sa.Column("name", sa.String(128), nullable=False, server_default="default"),
            sa.Column("key_prefix", sa.String(16), nullable=False, index=True),
            sa.Column("key_hash", sa.String(128), nullable=False),
            sa.Column("scopes_json", _json()),
            sa.Column("last_used_at", sa.DateTime(timezone=True)),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("expires_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _has_table("webhooks"):
        op.create_table(
            "webhooks",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), index=True),
            sa.Column("url", sa.Text, nullable=False),
            sa.Column("secret", sa.String(128)),
            sa.Column("events_json", _json()),
            sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("last_delivery_at", sa.DateTime(timezone=True)),
            sa.Column("last_status", sa.Integer),
            sa.Column("failure_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not _has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
            sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="SET NULL"), index=True),
            sa.Column("action", sa.String(64), nullable=False, index=True),
            sa.Column("resource_type", sa.String(64), index=True),
            sa.Column("resource_id", sa.String(64), index=True),
            sa.Column("ip_address", sa.String(64)),
            sa.Column("user_agent", sa.String(512)),
            sa.Column("metadata_json", _json()),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        )

    if not _has_table("deck_versions"):
        op.create_table(
            "deck_versions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False),
            sa.Column("version", sa.Integer, nullable=False),
            sa.Column("label", sa.String(255)),
            sa.Column("snapshot_json", _json(), nullable=False),
            sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("task_id", "version", name="uq_deck_version"),
        )


def downgrade() -> None:
    for tbl in (
        "deck_versions",
        "audit_logs",
        "webhooks",
        "api_keys",
        "assets",
        "brand_kits",
        "workspace_members",
        "workspaces",
    ):
        if _has_table(tbl):
            op.drop_table(tbl)
