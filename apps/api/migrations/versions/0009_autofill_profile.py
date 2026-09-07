"""Add the singleton local autofill profile.

Revision ID: 0009_autofill_profile
Revises: 0008_interview_feedback
Create Date: 2026-09-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_autofill_profile"
down_revision: str | None = "0008_interview_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "autofill_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("personal_json", sa.Text(), nullable=False),
        sa.Column("education_json", sa.Text(), nullable=False),
        sa.Column("experience_json", sa.Text(), nullable=False),
        sa.Column("links_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_autofill_profiles_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("autofill_profiles")
