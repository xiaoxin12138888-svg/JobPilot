"""Add append-only grounded Copilot results.

Revision ID: 0011_copilot_records
Revises: 0010_profile_projects
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_copilot_records"
down_revision: str | None = "0010_profile_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "copilot_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("resume_version_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("input_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('MATCH','RESUME_ADVICE','INTERVIEW_PREP')",
            name="ck_copilot_records_kind",
        ),
        sa.CheckConstraint("schema_version = 1", name="ck_copilot_records_schema_version"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_copilot_records_context_created",
        "copilot_records",
        ["job_id", "kind", "resume_version_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_copilot_records_context_created", table_name="copilot_records")
    op.drop_table("copilot_records")
