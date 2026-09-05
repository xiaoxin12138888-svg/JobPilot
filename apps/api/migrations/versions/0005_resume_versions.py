"""Add local Resume Versions and optional Application association.

Revision ID: 0005_resume_versions
Revises: 0004_jd_analysis_records
Create Date: 2026-09-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_resume_versions"
down_revision: str | None = "0004_jd_analysis_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resume_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_resume_versions_updated_at", "resume_versions", ["updated_at"], unique=False
    )
    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("resume_version_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_applications_resume_version_id_resume_versions",
            "resume_versions",
            ["resume_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_constraint(
            "fk_applications_resume_version_id_resume_versions", type_="foreignkey"
        )
        batch_op.drop_column("resume_version_id")
    op.drop_index("ix_resume_versions_updated_at", table_name="resume_versions")
    op.drop_table("resume_versions")
