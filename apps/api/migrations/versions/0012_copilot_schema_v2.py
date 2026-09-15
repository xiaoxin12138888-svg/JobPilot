"""Allow Copilot schema version 2.

Revision ID: 0012_copilot_schema_v2
Revises: 0011_copilot_records
Create Date: 2026-09-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_copilot_schema_v2"
down_revision: str | None = "0011_copilot_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _replace_schema_version_constraint("schema_version IN (1, 2)")


def downgrade() -> None:
    schema_two_records = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM copilot_records WHERE schema_version = 2")
    )
    if schema_two_records:
        raise RuntimeError("Cannot downgrade while Copilot schema version 2 records exist")
    _replace_schema_version_constraint("schema_version = 1")


def _replace_schema_version_constraint(expression: str) -> None:
    with op.batch_alter_table("copilot_records", recreate="always") as batch:
        batch.drop_constraint("ck_copilot_records_schema_version", type_="check")
        batch.create_check_constraint("ck_copilot_records_schema_version", expression)
