from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jobpilot_api.application.evidence_maps import EvidenceMapState
from jobpilot_api.application.jd_analysis import JDAnalysisState
from jobpilot_api.application.repositories import ApplicationListEntry, JobListEntry
from jobpilot_api.application.resume_imports import ResumeImportParseResult
from jobpilot_api.domain.applications import Application, ApplicationStatus, RejectionReason
from jobpilot_api.domain.autofill_profiles import AutofillProfile
from jobpilot_api.domain.evidence_maps import (
    EvidenceMap,
    EvidenceMapping,
    EvidenceMapRecord,
    ResumeEvidence,
)
from jobpilot_api.domain.feedback import (
    FeedbackSummary,
    FeedbackTotals,
    FunnelStage,
    PerformanceCount,
    QuestionCategoryCount,
    RejectionReasonCount,
    ResumeVersionFeedbackStats,
    SourceFeedbackStats,
    WeakCategoryCount,
)
from jobpilot_api.domain.interviews import (
    InterviewQuestion,
    InterviewRoundDetail,
    InterviewStatus,
    InterviewType,
    QuestionCategory,
    QuestionPerformance,
)
from jobpilot_api.domain.jd_analysis import EvidenceItem, JDAnalysis, JDAnalysisRecord
from jobpilot_api.domain.jobs import Job
from jobpilot_api.domain.resume_imports import (
    DocumentBlock,
    ResumeImportConfirmation,
    ResumeProfileImportPatch,
    ResumeSection,
)
from jobpilot_api.domain.resume_versions import ResumeVersion


def _camel_case(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=_camel_case, populate_by_name=True, extra="forbid")


class ResumeImportBlockResponse(ApiModel):
    kind: str
    text: str

    @classmethod
    def from_domain(cls, block: DocumentBlock) -> ResumeImportBlockResponse:
        return cls(kind=block.kind.value, text=block.text)


class ResumeImportSectionResponse(ApiModel):
    type: str
    heading: str | None
    text: str

    @classmethod
    def from_domain(cls, section: ResumeSection) -> ResumeImportSectionResponse:
        return cls(type=section.kind.value, heading=section.heading, text=section.text)


class ResumeImportPersonalCandidateResponse(ApiModel):
    name: str | None
    phone: str | None
    email: str | None
    current_city: str | None


class ResumeImportEducationCandidateResponse(ApiModel):
    school: str | None
    major: str | None
    degree: str | None
    start: str | None
    end: str | None


class ResumeImportExperienceCandidateResponse(ApiModel):
    company: str | None
    position: str | None
    start: str | None
    end: str | None
    description: str | None


class ResumeImportLinksCandidateResponse(ApiModel):
    github: str | None
    portfolio: str | None
    homepage: str | None


class ResumeImportProfileCandidatesResponse(ApiModel):
    personal: ResumeImportPersonalCandidateResponse
    education: list[ResumeImportEducationCandidateResponse]
    experience: list[ResumeImportExperienceCandidateResponse]
    links: ResumeImportLinksCandidateResponse


class ResumeImportMetricsResponse(ApiModel):
    file_size_bytes: int
    page_count: int | None
    parse_latency_ms: int
    extracted_character_count: int


class ResumeImportWarningResponse(ApiModel):
    code: str
    message: str


class ResumeImportParseResponse(ApiModel):
    file_type: str
    extracted_text: str
    blocks: list[ResumeImportBlockResponse]
    sections: list[ResumeImportSectionResponse]
    profile_candidates: ResumeImportProfileCandidatesResponse
    warnings: list[ResumeImportWarningResponse]
    metrics: ResumeImportMetricsResponse

    @classmethod
    def from_result(cls, result: ResumeImportParseResult) -> ResumeImportParseResponse:
        preview = result.preview
        candidates = preview.profile_candidates
        return cls(
            file_type=preview.file_type.value.upper(),
            extracted_text=preview.extracted_text,
            blocks=[ResumeImportBlockResponse.from_domain(item) for item in preview.blocks],
            sections=[ResumeImportSectionResponse.from_domain(item) for item in preview.sections],
            profile_candidates=ResumeImportProfileCandidatesResponse(
                personal=ResumeImportPersonalCandidateResponse(
                    name=candidates.personal.name,
                    phone=candidates.personal.phone,
                    email=candidates.personal.email,
                    current_city=candidates.personal.current_city,
                ),
                education=[
                    ResumeImportEducationCandidateResponse(
                        school=item.school,
                        major=item.major,
                        degree=item.degree,
                        start=item.start,
                        end=item.end,
                    )
                    for item in candidates.education
                ],
                experience=[
                    ResumeImportExperienceCandidateResponse(
                        company=item.company,
                        position=item.position,
                        start=item.start,
                        end=item.end,
                        description=item.description,
                    )
                    for item in candidates.experience
                ],
                links=ResumeImportLinksCandidateResponse(
                    github=candidates.links.github,
                    portfolio=candidates.links.portfolio,
                    homepage=candidates.links.homepage,
                ),
            ),
            warnings=[
                ResumeImportWarningResponse(code=item.code, message=item.message)
                for item in preview.warnings
            ],
            metrics=ResumeImportMetricsResponse(
                file_size_bytes=result.metrics.size_bytes,
                page_count=result.metrics.page_count,
                parse_latency_ms=result.metrics.parse_latency_ms,
                extracted_character_count=result.metrics.character_count,
            ),
        )


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
    outcome_note: str | None = None
    rejection_reason: RejectionReason | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> ApplicationUpdateRequest:
        if (
            "status" not in self.model_fields_set
            and "resume_version_id" not in self.model_fields_set
            and "outcome_note" not in self.model_fields_set
            and "rejection_reason" not in self.model_fields_set
        ):
            raise ValueError(
                "status, resumeVersionId, outcomeNote or rejectionReason must be provided"
            )
        return self


class ApplicationResponse(ApiModel):
    id: str
    job_id: str
    status: ApplicationStatus
    resume_version_id: str | None
    outcome_note: str | None
    rejection_reason: RejectionReason | None
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
            outcome_note=application.outcome_note,
            rejection_reason=application.rejection_reason,
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


class InterviewRoundCreateRequest(ApiModel):
    round_name: str
    interview_type: InterviewType
    scheduled_at: datetime | None = None
    status: InterviewStatus = InterviewStatus.PLANNED
    interviewer_note: str | None = None
    went_well: str | None = None
    could_improve: str | None = None
    learning_notes: str | None = None
    other_notes: str | None = None


class InterviewRoundUpdateRequest(ApiModel):
    round_name: str | None = None
    interview_type: InterviewType | None = None
    scheduled_at: datetime | None = None
    status: InterviewStatus | None = None
    interviewer_note: str | None = None
    went_well: str | None = None
    could_improve: str | None = None
    learning_notes: str | None = None
    other_notes: str | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> InterviewRoundUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        required_fields = {"round_name", "interview_type", "status"}
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required_fields
        ):
            raise ValueError("roundName, interviewType and status must not be null")
        return self


class InterviewQuestionCreateRequest(ApiModel):
    question: str
    category: QuestionCategory
    answer_summary: str | None = None
    performance: QuestionPerformance = QuestionPerformance.NOT_SURE
    note: str | None = None


class InterviewQuestionUpdateRequest(ApiModel):
    question: str | None = None
    category: QuestionCategory | None = None
    answer_summary: str | None = None
    performance: QuestionPerformance | None = None
    note: str | None = None

    @model_validator(mode="after")
    def require_a_change(self) -> InterviewQuestionUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("at least one field must be provided")
        required_fields = {"question", "category", "performance"}
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required_fields
        ):
            raise ValueError("question, category and performance must not be null")
        return self


class InterviewQuestionResponse(ApiModel):
    id: str
    interview_round_id: str
    question: str
    category: QuestionCategory
    answer_summary: str | None
    performance: QuestionPerformance
    note: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, question: InterviewQuestion) -> InterviewQuestionResponse:
        return cls(
            id=question.id,
            interview_round_id=question.interview_round_id,
            question=question.question,
            category=question.category,
            answer_summary=question.answer_summary,
            performance=question.performance,
            note=question.note,
            created_at=question.created_at,
            updated_at=question.updated_at,
        )


class InterviewRoundResponse(ApiModel):
    id: str
    application_id: str
    round_name: str
    interview_type: InterviewType
    scheduled_at: datetime | None
    status: InterviewStatus
    interviewer_note: str | None
    went_well: str | None
    could_improve: str | None
    learning_notes: str | None
    other_notes: str | None
    questions: list[InterviewQuestionResponse]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, detail: InterviewRoundDetail) -> InterviewRoundResponse:
        interview = detail.interview
        return cls(
            id=interview.id,
            application_id=interview.application_id,
            round_name=interview.round_name,
            interview_type=interview.interview_type,
            scheduled_at=interview.scheduled_at,
            status=interview.status,
            interviewer_note=interview.interviewer_note,
            went_well=interview.went_well,
            could_improve=interview.could_improve,
            learning_notes=interview.learning_notes,
            other_notes=interview.other_notes,
            questions=[InterviewQuestionResponse.from_domain(item) for item in detail.questions],
            created_at=interview.created_at,
            updated_at=interview.updated_at,
        )


class InterviewRoundListResponse(ApiModel):
    items: list[InterviewRoundResponse]
    total: int
    limit: int
    offset: int


class FeedbackTotalsResponse(ApiModel):
    saved_jobs: int
    applications: int
    interview_applications: int
    interviews: int
    questions: int
    offers: int
    rejected: int

    @classmethod
    def from_domain(cls, totals: FeedbackTotals) -> FeedbackTotalsResponse:
        return cls(**{field: getattr(totals, field) for field in cls.model_fields})


class FunnelStageResponse(ApiModel):
    stage: str
    count: int
    conversion_rate: float | None

    @classmethod
    def from_domain(cls, stage: FunnelStage) -> FunnelStageResponse:
        return cls(
            stage=stage.stage.value,
            count=stage.count,
            conversion_rate=stage.conversion_rate,
        )


class QuestionCategoryCountResponse(ApiModel):
    category: QuestionCategory
    count: int

    @classmethod
    def from_domain(cls, item: QuestionCategoryCount) -> QuestionCategoryCountResponse:
        return cls(category=item.category, count=item.count)


class PerformanceCountResponse(ApiModel):
    performance: QuestionPerformance
    count: int

    @classmethod
    def from_domain(cls, item: PerformanceCount) -> PerformanceCountResponse:
        return cls(performance=item.performance, count=item.count)


class WeakCategoryCountResponse(ApiModel):
    category: QuestionCategory
    question_count: int
    weak_count: int

    @classmethod
    def from_domain(cls, item: WeakCategoryCount) -> WeakCategoryCountResponse:
        return cls(
            category=item.category,
            question_count=item.question_count,
            weak_count=item.weak_count,
        )


class RejectionReasonCountResponse(ApiModel):
    reason: RejectionReason
    count: int

    @classmethod
    def from_domain(cls, item: RejectionReasonCount) -> RejectionReasonCountResponse:
        return cls(reason=item.reason, count=item.count)


class FeedbackGroupStatsResponse(ApiModel):
    applications: int
    interview_applications: int
    offers: int


class SourceFeedbackStatsResponse(FeedbackGroupStatsResponse):
    source: Literal["manual", "boss", "nowcoder"]

    @classmethod
    def from_domain(cls, item: SourceFeedbackStats) -> SourceFeedbackStatsResponse:
        return cls(
            source=item.source,  # type: ignore[arg-type]
            applications=item.applications,
            interview_applications=item.interview_applications,
            offers=item.offers,
        )


class ResumeVersionFeedbackStatsResponse(FeedbackGroupStatsResponse):
    resume_version_id: str
    resume_version_name: str

    @classmethod
    def from_domain(cls, item: ResumeVersionFeedbackStats) -> ResumeVersionFeedbackStatsResponse:
        return cls(
            resume_version_id=item.resume_version_id,
            resume_version_name=item.resume_version_name,
            applications=item.applications,
            interview_applications=item.interview_applications,
            offers=item.offers,
        )


class FeedbackSummaryResponse(ApiModel):
    has_data: bool
    totals: FeedbackTotalsResponse
    funnel: list[FunnelStageResponse]
    question_categories: list[QuestionCategoryCountResponse]
    performances: list[PerformanceCountResponse]
    weak_categories: list[WeakCategoryCountResponse]
    rejection_reasons: list[RejectionReasonCountResponse]
    unrecorded_rejection_reasons: int
    resume_versions: list[ResumeVersionFeedbackStatsResponse]
    sources: list[SourceFeedbackStatsResponse]

    @classmethod
    def from_domain(cls, summary: FeedbackSummary) -> FeedbackSummaryResponse:
        return cls(
            has_data=summary.has_data,
            totals=FeedbackTotalsResponse.from_domain(summary.totals),
            funnel=[FunnelStageResponse.from_domain(item) for item in summary.funnel],
            question_categories=[
                QuestionCategoryCountResponse.from_domain(item)
                for item in summary.question_categories
            ],
            performances=[
                PerformanceCountResponse.from_domain(item) for item in summary.performances
            ],
            weak_categories=[
                WeakCategoryCountResponse.from_domain(item) for item in summary.weak_categories
            ],
            rejection_reasons=[
                RejectionReasonCountResponse.from_domain(item) for item in summary.rejection_reasons
            ],
            unrecorded_rejection_reasons=summary.unrecorded_rejection_reasons,
            resume_versions=[
                ResumeVersionFeedbackStatsResponse.from_domain(item)
                for item in summary.resume_versions
            ],
            sources=[SourceFeedbackStatsResponse.from_domain(item) for item in summary.sources],
        )


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


class PersonalDetailsPayload(ApiModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    current_city: str | None = None


class EducationEntryPayload(ApiModel):
    school: str | None = None
    major: str | None = None
    degree: str | None = None
    start: str | None = None
    end: str | None = None


class ExperienceEntryPayload(ApiModel):
    company: str | None = None
    position: str | None = None
    start: str | None = None
    end: str | None = None
    description: str | None = None


class ProfileLinksPayload(ApiModel):
    github: str | None = None
    portfolio: str | None = None
    homepage: str | None = None


class AutofillProfilePutRequest(ApiModel):
    personal: PersonalDetailsPayload
    education: list[EducationEntryPayload] = Field(max_length=20)
    experience: list[ExperienceEntryPayload] = Field(max_length=20)
    links: ProfileLinksPayload


class AutofillProfileDataResponse(ApiModel):
    personal: PersonalDetailsPayload
    education: list[EducationEntryPayload]
    experience: list[ExperienceEntryPayload]
    links: ProfileLinksPayload
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, profile: AutofillProfile) -> AutofillProfileDataResponse:
        return cls(
            personal=PersonalDetailsPayload(
                name=profile.personal.name,
                phone=profile.personal.phone,
                email=profile.personal.email,
                current_city=profile.personal.current_city,
            ),
            education=[
                EducationEntryPayload(
                    school=item.school,
                    major=item.major,
                    degree=item.degree,
                    start=item.start,
                    end=item.end,
                )
                for item in profile.education
            ],
            experience=[
                ExperienceEntryPayload(
                    company=item.company,
                    position=item.position,
                    start=item.start,
                    end=item.end,
                    description=item.description,
                )
                for item in profile.experience
            ],
            links=ProfileLinksPayload(
                github=profile.links.github,
                portfolio=profile.links.portfolio,
                homepage=profile.links.homepage,
            ),
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


class AutofillProfileResponse(ApiModel):
    profile: AutofillProfileDataResponse | None

    @classmethod
    def from_domain(cls, profile: AutofillProfile | None) -> AutofillProfileResponse:
        return cls(
            profile=(
                AutofillProfileDataResponse.from_domain(profile) if profile is not None else None
            )
        )


class ResumeProfileImportRequest(ApiModel):
    personal: PersonalDetailsPayload = Field(default_factory=PersonalDetailsPayload)
    education: list[EducationEntryPayload] = Field(default_factory=list, max_length=20)
    experience: list[ExperienceEntryPayload] = Field(default_factory=list, max_length=20)
    links: ProfileLinksPayload = Field(default_factory=ProfileLinksPayload)

    def to_domain(self) -> ResumeProfileImportPatch:
        return ResumeProfileImportPatch.create(
            personal=self.personal.model_dump(exclude_unset=True),
            education=[item.model_dump() for item in self.education],
            experience=[item.model_dump() for item in self.experience],
            links=self.links.model_dump(exclude_unset=True),
        )


class ResumeImportConfirmRequest(ApiModel):
    resume_version: ResumeVersionCreateRequest | None = None
    profile_import: ResumeProfileImportRequest | None = None

    @model_validator(mode="after")
    def require_a_target(self) -> ResumeImportConfirmRequest:
        if self.resume_version is None and self.profile_import is None:
            raise ValueError("at least one import target must be provided")
        return self


class ResumeImportConfirmResponse(ApiModel):
    resume_version: ResumeVersionResponse | None
    profile: AutofillProfileDataResponse | None

    @classmethod
    def from_domain(cls, result: ResumeImportConfirmation) -> ResumeImportConfirmResponse:
        return cls(
            resume_version=(
                ResumeVersionResponse.from_domain(result.resume_version)
                if result.resume_version is not None
                else None
            ),
            profile=(
                AutofillProfileDataResponse.from_domain(result.profile)
                if result.profile is not None
                else None
            ),
        )


class EvidenceMapGenerateRequest(ApiModel):
    resume_version_id: str = Field(max_length=36)
    confirm_external_ai: Literal[True]


class ResumeEvidenceResponse(ApiModel):
    quote: str

    @classmethod
    def from_domain(cls, evidence: ResumeEvidence) -> ResumeEvidenceResponse:
        return cls(quote=evidence.quote)


class EvidenceMappingResponse(ApiModel):
    requirement_type: Literal[
        "MUST_HAVE",
        "PREFERRED",
        "RESPONSIBILITY",
        "SKILL",
        "EXPERIENCE",
        "EDUCATION",
    ]
    requirement_text: str
    coverage: Literal["DIRECT", "PARTIAL", "GAP"]
    resume_evidence: list[ResumeEvidenceResponse]
    reason: str

    @classmethod
    def from_domain(cls, mapping: EvidenceMapping) -> EvidenceMappingResponse:
        return cls(
            requirement_type=mapping.requirement_type.value,
            requirement_text=mapping.requirement_text,
            coverage=mapping.coverage.value,
            resume_evidence=[
                ResumeEvidenceResponse.from_domain(evidence) for evidence in mapping.resume_evidence
            ],
            reason=mapping.reason,
        )


class EvidenceMapResultResponse(ApiModel):
    mappings: list[EvidenceMappingResponse]

    @classmethod
    def from_domain(cls, result: EvidenceMap) -> EvidenceMapResultResponse:
        return cls(mappings=[EvidenceMappingResponse.from_domain(item) for item in result.mappings])


class EvidenceMapRecordResponse(ApiModel):
    id: str
    job_id: str
    resume_version_id: str
    schema_version: int
    result: EvidenceMapResultResponse
    is_stale: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: EvidenceMapRecord, *, is_stale: bool) -> EvidenceMapRecordResponse:
        return cls(
            id=record.id,
            job_id=record.job_id,
            resume_version_id=record.resume_version_id,
            schema_version=record.schema_version,
            result=EvidenceMapResultResponse.from_domain(record.result),
            is_stale=is_stale,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class JobEvidenceMapResponse(ApiModel):
    is_configured: bool
    evidence_map: EvidenceMapRecordResponse | None

    @classmethod
    def from_state(cls, state: EvidenceMapState) -> JobEvidenceMapResponse:
        return cls(
            is_configured=state.is_configured,
            evidence_map=(
                EvidenceMapRecordResponse.from_domain(state.record, is_stale=state.is_stale)
                if state.record is not None
                else None
            ),
        )
