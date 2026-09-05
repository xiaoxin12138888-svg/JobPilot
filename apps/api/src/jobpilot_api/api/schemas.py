from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jobpilot_api.application.jd_analysis import JDAnalysisState
from jobpilot_api.application.repositories import ApplicationListEntry, JobListEntry
from jobpilot_api.domain.applications import Application, ApplicationStatus
from jobpilot_api.domain.jd_analysis import EvidenceItem, JDAnalysis, JDAnalysisRecord
from jobpilot_api.domain.jobs import Job
from jobpilot_api.domain.resume_versions import ResumeVersion


def _camel_case(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel_case, populate_by_name=True, extra="forbid")


class JobCreateRequest(ApiModel):
    title: str
    company: str
    location: str | None = None
    salary_text: str | None = None
    source: Literal["manual", "boss", "nowcoder"] = "manual"
    source_url: str | None = None
    description: str | None = None
    notes: str | None = None


class JobUpdateRequest(ApiModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    salary_text: str | None = None
    source: Literal["manual", "boss", "nowcoder"] | None = None
    source_url: str | None = None
    description: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> JobUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class JobResponse(ApiModel):
    id: str
    title: str
    company: str
    location: str | None
    salary_text: str | None
    source: Literal["manual", "boss", "nowcoder"]
    source_url: str | None
    description: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, job: Job) -> JobResponse:
        return cls(
            id=job.id,
            title=job.title,
            company=job.company,
            location=job.location,
            salary_text=job.salary_text,
            source=job.source,
            source_url=job.source_url,
            description=job.description,
            notes=job.notes,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class JobListItem(JobResponse):
    application_status: ApplicationStatus | None

    @classmethod
    def from_entry(cls, entry: JobListEntry) -> JobListItem:
        return cls(
            **JobResponse.from_domain(entry.job).model_dump(),
            application_status=entry.application_status,
        )


class JobListResponse(ApiModel):
    items: list[JobListItem]
    total: int
    limit: int
    offset: int


class ApplicationCreateRequest(ApiModel):
    pass


class ApplicationUpdateRequest(ApiModel):
    status: ApplicationStatus | None = None
    confirm_applied: bool = False
    resume_version_id: str | None = Field(default=None, max_length=36)

    @model_validator(mode="after")
    def require_a_change(self) -> ApplicationUpdateRequest:
        if (
            "status" not in self.model_fields_set
            and "resume_version_id" not in self.model_fields_set
        ):
            raise ValueError("status or resumeVersionId must be provided")
        return self


class ApplicationResponse(ApiModel):
    id: str
    job_id: str
    status: ApplicationStatus
    resume_version_id: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, application: Application) -> ApplicationResponse:
        return cls(
            id=application.id,
            job_id=application.job_id,
            status=application.status,
            resume_version_id=application.resume_version_id,
            applied_at=application.applied_at,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


class ApplicationListItem(ApplicationResponse):
    job_title: str
    company: str

    @classmethod
    def from_entry(cls, entry: ApplicationListEntry) -> ApplicationListItem:
        return cls(
            **ApplicationResponse.from_domain(entry.application).model_dump(),
            job_title=entry.job_title,
            company=entry.company,
        )


class ApplicationListResponse(ApiModel):
    items: list[ApplicationListItem]
    total: int
    limit: int
    offset: int


class AnalysisCreateRequest(ApiModel):
    pass


class EvidenceItemResponse(ApiModel):
    text: str
    evidence: str | None

    @classmethod
    def from_domain(cls, item: EvidenceItem) -> EvidenceItemResponse:
        return cls(text=item.text, evidence=item.evidence)


class JDAnalysisResultResponse(ApiModel):
    summary: str
    responsibilities: list[EvidenceItemResponse]
    must_have_requirements: list[EvidenceItemResponse]
    preferred_requirements: list[EvidenceItemResponse]
    skills: list[str]
    experience_requirements: list[EvidenceItemResponse]
    education_requirements: list[EvidenceItemResponse]
    domain_keywords: list[str]
    interview_focus: list[EvidenceItemResponse]

    @classmethod
    def from_domain(cls, result: JDAnalysis) -> JDAnalysisResultResponse:
        return cls(
            summary=result.summary,
            responsibilities=[
                EvidenceItemResponse.from_domain(item) for item in result.responsibilities
            ],
            must_have_requirements=[
                EvidenceItemResponse.from_domain(item) for item in result.must_have_requirements
            ],
            preferred_requirements=[
                EvidenceItemResponse.from_domain(item) for item in result.preferred_requirements
            ],
            skills=list(result.skills),
            experience_requirements=[
                EvidenceItemResponse.from_domain(item) for item in result.experience_requirements
            ],
            education_requirements=[
                EvidenceItemResponse.from_domain(item) for item in result.education_requirements
            ],
            domain_keywords=list(result.domain_keywords),
            interview_focus=[
                EvidenceItemResponse.from_domain(item) for item in result.interview_focus
            ],
        )


class JDAnalysisRecordResponse(ApiModel):
    id: str
    job_id: str
    schema_version: int
    result: JDAnalysisResultResponse
    is_stale: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: JDAnalysisRecord, *, is_stale: bool) -> JDAnalysisRecordResponse:
        return cls(
            id=record.id,
            job_id=record.job_id,
            schema_version=record.schema_version,
            result=JDAnalysisResultResponse.from_domain(record.result),
            is_stale=is_stale,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class JobAnalysisResponse(ApiModel):
    is_configured: bool
    analysis: JDAnalysisRecordResponse | None

    @classmethod
    def from_state(cls, state: JDAnalysisState) -> JobAnalysisResponse:
        return cls(
            is_configured=state.is_configured,
            analysis=(
                JDAnalysisRecordResponse.from_domain(state.record, is_stale=state.is_stale)
                if state.record is not None
                else None
            ),
        )


class ResumeVersionCreateRequest(ApiModel):
    name: str
    content: str


class ResumeVersionUpdateRequest(ApiModel):
    name: str | None = None
    content: str | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> ResumeVersionUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        return self


class ResumeVersionDuplicateRequest(ApiModel):
    name: str


class ResumeVersionResponse(ApiModel):
    id: str
    name: str
    content: str
    application_count: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, resume: ResumeVersion) -> ResumeVersionResponse:
        return cls(
            id=resume.id,
            name=resume.name,
            content=resume.content,
            application_count=resume.application_count,
            created_at=resume.created_at,
            updated_at=resume.updated_at,
        )


class ResumeVersionListResponse(ApiModel):
    items: list[ResumeVersionResponse]
    total: int
    limit: int
    offset: int
