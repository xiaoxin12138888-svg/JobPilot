"""Allow Nowcoder as a Job source.

Revision ID: 0003_nowcoder_job_source
Revises: 0002_boss_job_source
Create Date: 2026-09-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_nowcoder_job_source"
down_revision: str | None = "0002_boss_job_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _replace_source_constraint("source IN ('manual','boss','nowcoder')")


def downgrade() -> None:
    nowcoder_jobs = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM jobs WHERE source = 'nowcoder'")
    )
    if nowcoder_jobs:
        raise RuntimeError("Cannot downgrade while Nowcoder jobs exist")
    _replace_source_constraint("source IN ('manual','boss')")


def _replace_source_constraint(expression: str) -> None:
    op.execute(
        """
        CREATE TEMP TABLE jobpilot_application_backup AS
        SELECT id, job_id, status, applied_at, created_at, updated_at FROM applications
        """
    )
    with op.batch_alter_table("jobs", recreate="always") as batch:
        batch.drop_constraint("ck_jobs_source", type_="check")
        batch.create_check_constraint("ck_jobs_source", expression)
    op.execute(
        """
        INSERT OR IGNORE INTO applications (
            id, job_id, status, applied_at, created_at, updated_at
        )
        SELECT id, job_id, status, applied_at, created_at, updated_at
        FROM jobpilot_application_backup
        """
    )
    op.execute("DROP TABLE jobpilot_application_backup")
