"""Add local interview records and Application outcome detail.

Revision ID: 0008_interview_feedback
Revises: 0007_evidence_map_schema_v2
Create Date: 2026-09-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_interview_feedback"
down_revision: str | None = "0007_evidence_map_schema_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("outcome_note", sa.Text(), nullable=True))
        batch.add_column(sa.Column("rejection_reason", sa.String(length=32), nullable=True))
        batch.create_check_constraint(
            "ck_applications_rejection_reason",
            "rejection_reason IS NULL OR rejection_reason IN ("
            "'TECHNICAL','EXPERIENCE','PRODUCT','BUSINESS','COMMUNICATION',"
            "'ROLE_FIT','HEADCOUNT','UNKNOWN','OTHER')",
        )

    op.create_table(
        "interview_rounds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("round_name", sa.String(length=200), nullable=False),
        sa.Column("interview_type", sa.String(length=32), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("interviewer_note", sa.Text(), nullable=True),
        sa.Column("went_well", sa.Text(), nullable=True),
        sa.Column("could_improve", sa.Text(), nullable=True),
        sa.Column("learning_notes", sa.Text(), nullable=True),
        sa.Column("other_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "interview_type IN ('PHONE','VIDEO','ONSITE','OTHER')",
            name="ck_interview_rounds_type",
        ),
        sa.CheckConstraint(
            "status IN ('PLANNED','COMPLETED','CANCELLED')",
            name="ck_interview_rounds_status",
        ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_rounds_application_scheduled",
        "interview_rounds",
        ["application_id", "scheduled_at"],
        unique=False,
    )

    op.create_table(
        "interview_questions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("interview_round_id", sa.String(length=36), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("answer_summary", sa.Text(), nullable=True),
        sa.Column("performance", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('PRODUCT','AI','TECHNICAL','PROJECT','BEHAVIORAL','BUSINESS','OTHER')",
            name="ck_interview_questions_category",
        ),
        sa.CheckConstraint(
            "performance IN ('GOOD','OK','POOR','NOT_SURE')",
            name="ck_interview_questions_performance",
        ),
        sa.ForeignKeyConstraint(
            ["interview_round_id"], ["interview_rounds.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_questions_round_created",
        "interview_questions",
        ["interview_round_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_interview_questions_round_created", table_name="interview_questions")
    op.drop_table("interview_questions")
    op.drop_index("ix_interview_rounds_application_scheduled", table_name="interview_rounds")
    op.drop_table("interview_rounds")
    with op.batch_alter_table("applications") as batch:
        batch.drop_constraint("ck_applications_rejection_reason", type_="check")
        batch.drop_column("rejection_reason")
        batch.drop_column("outcome_note")
