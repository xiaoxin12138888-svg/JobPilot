"""Allow BOSS as a Job source.

Revision ID: 0002_boss_job_source
Revises: 0001_job_application
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_boss_job_source"
down_revision: str | None = "0001_job_application"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _replace_source_constraint(
        drop_name="ck_jobs_source_manual",
        create_name="ck_jobs_source",
        expression="source IN ('manual','boss')",
    )


def downgrade() -> None:
    boss_jobs = op.get_bind().scalar(sa.text("SELECT count(*) FROM jobs WHERE source = 'boss'"))
    if boss_jobs:
        raise RuntimeError("Cannot downgrade while BOSS jobs exist")
    _replace_source_constraint(
        drop_name="ck_jobs_source",
        create_name="ck_jobs_source_manual",
        expression="source = 'manual'",
    )


def _replace_source_constraint(*, drop_name: str, create_name: str, expression: str) -> None:
    op.execute(
        """
        CREATE TEMP TABLE jobpilot_application_backup AS
        SELECT id, job_id, status, applied_at, created_at, updated_at FROM applications
        """
    )
    with op.batch_alter_table("jobs", recreate="always") as batch:
        batch.drop_constraint(drop_name, type_="check")
        batch.create_check_constraint(create_name, expression)
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
