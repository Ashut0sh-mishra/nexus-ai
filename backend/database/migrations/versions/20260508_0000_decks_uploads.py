"""add Slide and UploadedFile tables; extend Task and Export columns.

Revision ID: 0002_decks_uploads
Revises: 0001_initial
Create Date: 2026-05-08 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002_decks_uploads"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _has_column(table: str, column: str) -> bool:
    """Return True if the given column already exists.

    ``init_models()`` calls ``Base.metadata.create_all`` on dev startup, so
    columns may already be present when this migration runs. Guard every
    add_column to keep the migration idempotent across fresh / dev DBs.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return any(col["name"] == column for col in inspector.get_columns(table))
    except Exception:
        return False


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    try:
        return inspector.has_table(table)
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Upgrade
# --------------------------------------------------------------------------- #
def upgrade() -> None:
    # ── tasks: deck-level metadata ─────────────────────────────────────────
    task_columns = [
        ("prompt", sa.Column("prompt", sa.Text(), nullable=True)),
        ("context_sources", sa.Column("context_sources", sa.JSON(), nullable=True)),
        ("deck_plan_json", sa.Column("deck_plan_json", sa.JSON(), nullable=True)),
        ("audience", sa.Column("audience", sa.String(length=64), nullable=True)),
        ("tone", sa.Column("tone", sa.String(length=64), nullable=True)),
        ("industry", sa.Column("industry", sa.String(length=64), nullable=True)),
        ("theme_settings", sa.Column("theme_settings", sa.JSON(), nullable=True)),
        (
            "updated_at",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        ),
    ]
    for name, col in task_columns:
        if not _has_column("tasks", name):
            op.add_column("tasks", col)

    # ── exports: status + output_path + error_msg + updated_at ─────────────
    export_columns = [
        (
            "status",
            sa.Column(
                "status",
                sa.String(length=32),
                server_default="completed",
                nullable=False,
            ),
        ),
        ("output_path", sa.Column("output_path", sa.Text(), nullable=True)),
        ("error_msg", sa.Column("error_msg", sa.Text(), nullable=True)),
        (
            "updated_at",
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        ),
    ]
    for name, col in export_columns:
        if not _has_column("exports", name):
            op.add_column("exports", col)

    # The model also renamed url/size_bytes → file_url/file_size at the ORM
    # level. The 0001 migration created the legacy names; rename only when
    # the legacy column is the one actually in the DB.
    if _has_column("exports", "url") and not _has_column("exports", "file_url"):
        op.alter_column("exports", "url", new_column_name="file_url")
    if _has_column("exports", "size_bytes") and not _has_column("exports", "file_size"):
        op.alter_column("exports", "size_bytes", new_column_name="file_size")

    # ── new table: deck_slides (per-slide rows) ────────────────────────────
    if not _has_table("deck_slides"):
        op.create_table(
            "deck_slides",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "task_id",
                sa.String(length=36),
                sa.ForeignKey("tasks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("slide_number", sa.Integer(), nullable=False),
            sa.Column(
                "slide_type",
                sa.String(length=32),
                nullable=False,
                server_default="content",
            ),
            sa.Column(
                "title", sa.String(length=512), nullable=False, server_default=""
            ),
            sa.Column("subtitle", sa.String(length=512), nullable=True),
            sa.Column("content_json", sa.JSON(), nullable=True),
            sa.Column("chart_data_json", sa.JSON(), nullable=True),
            sa.Column("image_data_json", sa.JSON(), nullable=True),
            sa.Column("speaker_notes", sa.Text(), nullable=True),
            sa.Column("layout_metadata", sa.JSON(), nullable=True),
            sa.Column("design_tokens", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "task_id", "slide_number", name="uq_deck_slide_number"
            ),
        )
        op.create_index("ix_deck_slides_task_id", "deck_slides", ["task_id"])

    # ── new table: uploaded_files ──────────────────────────────────────────
    if not _has_table("uploaded_files"):
        op.create_table(
            "uploaded_files",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column(
                "task_id",
                sa.String(length=36),
                sa.ForeignKey("tasks.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "user_id",
                sa.String(length=36),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("filename", sa.String(length=512), nullable=False),
            sa.Column("file_type", sa.String(length=16), nullable=False),
            sa.Column("file_path", sa.String(length=1024), nullable=False),
            sa.Column(
                "file_size", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column("extracted_text", sa.Text(), nullable=True),
            sa.Column("extracted_data_json", sa.JSON(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_uploaded_files_task_id", "uploaded_files", ["task_id"]
        )
        op.create_index(
            "ix_uploaded_files_user_id", "uploaded_files", ["user_id"]
        )


# --------------------------------------------------------------------------- #
# Downgrade
# --------------------------------------------------------------------------- #
def downgrade() -> None:
    if _has_table("uploaded_files"):
        op.drop_index(
            "ix_uploaded_files_user_id", table_name="uploaded_files"
        )
        op.drop_index(
            "ix_uploaded_files_task_id", table_name="uploaded_files"
        )
        op.drop_table("uploaded_files")

    if _has_table("deck_slides"):
        op.drop_index("ix_deck_slides_task_id", table_name="deck_slides")
        op.drop_table("deck_slides")

    for col in ("updated_at", "error_msg", "output_path", "status"):
        if _has_column("exports", col):
            op.drop_column("exports", col)

    for col in (
        "updated_at",
        "theme_settings",
        "industry",
        "tone",
        "audience",
        "deck_plan_json",
        "context_sources",
        "prompt",
    ):
        if _has_column("tasks", col):
            op.drop_column("tasks", col)
