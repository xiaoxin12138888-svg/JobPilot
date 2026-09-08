"""Add structured project experience to the local profile.

Revision ID: 0010_profile_projects
Revises: 0009_autofill_profile
Create Date: 2026-09-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_profile_projects"
down_revision: str | None = "0009_autofill_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("autofill_profiles") as batch:
        batch.add_column(
            sa.Column(
                "projects_json",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("autofill_profiles") as batch:
        batch.drop_column("projects_json")
