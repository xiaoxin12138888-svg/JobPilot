from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class JobModel(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("normalized_source_url", name="uq_jobs_normalized_source_url"),
        CheckConstraint("source IN ('manual','boss','nowcoder')", name="ck_jobs_source"),
        Index("ix_jobs_updated_at", "updated_at"),
        Index("ix_jobs_source", "source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company: Mapped[str] = mapped_column(String(200), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300))
    salary_text: Mapped[str | None] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    normalized_source_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ResumeVersionModel(Base):
    __tablename__ = "resume_versions"
    __table_args__ = (Index("ix_resume_versions_updated_at", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AutofillProfileModel(Base):
    __tablename__ = "autofill_profiles"
    __table_args__ = (CheckConstraint("id = 1", name="ck_autofill_profiles_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    personal_json: Mapped[str] = mapped_column(Text, nullable=False)
    education_json: Mapped[str] = mapped_column(Text, nullable=False)
    experience_json: Mapped[str] = mapped_column(Text, nullable=False)
    projects_json: Mapped[str] = mapped_column(Text, nullable=False)
    links_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ApplicationModel(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_applications_job_id"),
        CheckConstraint(
            "status IN ('planned','applied','screening','assessment','interviewing','offer','rejected','withdrawn','closed')",
            name="ck_applications_status",
        ),
        CheckConstraint(
            "rejection_reason IS NULL OR rejection_reason IN ("
            "'TECHNICAL','EXPERIENCE','PRODUCT','BUSINESS','COMMUNICATION',"
            "'ROLE_FIT','HEADCOUNT','UNKNOWN','OTHER')",
            name="ck_applications_rejection_reason",
        ),
        Index("ix_applications_status_updated_at", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    resume_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("resume_versions.id", ondelete="RESTRICT"),
    )
    outcome_note: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(String(32))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class JDAnalysisRecordModel(Base):
    __tablename__ = "jd_analysis_records"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_jd_analysis_records_job_id"),
        CheckConstraint("schema_version = 1", name="ck_jd_analysis_records_schema_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_version: Mapped[int] = mapped_column(nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceMapRecordModel(Base):
    __tablename__ = "evidence_map_records"
    __table_args__ = (
        UniqueConstraint("job_id", "resume_version_id", name="uq_evidence_map_records_job_resume"),
        CheckConstraint("schema_version IN (1, 2)", name="ck_evidence_map_records_schema_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    resume_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("resume_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    schema_version: Mapped[int] = mapped_column(nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    job_analysis_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    resume_content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CopilotRecordModel(Base):
    __tablename__ = "copilot_records"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('MATCH','RESUME_ADVICE','INTERVIEW_PREP')",
            name="ck_copilot_records_kind",
        ),
        CheckConstraint("schema_version = 1", name="ck_copilot_records_schema_version"),
        Index(
            "ix_copilot_records_context_created",
            "job_id",
            "kind",
            "resume_version_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    resume_version_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterviewRoundModel(Base):
    __tablename__ = "interview_rounds"
    __table_args__ = (
        CheckConstraint(
            "interview_type IN ('PHONE','VIDEO','ONSITE','OTHER')",
            name="ck_interview_rounds_type",
        ),
        CheckConstraint(
            "status IN ('PLANNED','COMPLETED','CANCELLED')",
            name="ck_interview_rounds_status",
        ),
        Index("ix_interview_rounds_application_scheduled", "application_id", "scheduled_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    round_name: Mapped[str] = mapped_column(String(200), nullable=False)
    interview_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    interviewer_note: Mapped[str | None] = mapped_column(Text)
    went_well: Mapped[str | None] = mapped_column(Text)
    could_improve: Mapped[str | None] = mapped_column(Text)
    learning_notes: Mapped[str | None] = mapped_column(Text)
    other_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class InterviewQuestionModel(Base):
    __tablename__ = "interview_questions"
    __table_args__ = (
        CheckConstraint(
            "category IN ('PRODUCT','AI','TECHNICAL','PROJECT','BEHAVIORAL','BUSINESS','OTHER')",
            name="ck_interview_questions_category",
        ),
        CheckConstraint(
            "performance IN ('GOOD','OK','POOR','NOT_SURE')",
            name="ck_interview_questions_performance",
        ),
        Index("ix_interview_questions_round_created", "interview_round_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    interview_round_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("interview_rounds.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    answer_summary: Mapped[str | None] = mapped_column(Text)
    performance: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
