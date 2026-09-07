from __future__ import annotations

from pathlib import Path
from threading import Lock

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from jobpilot_api.application.evidence_maps import EvidenceMapService
from jobpilot_api.application.jd_analysis import JDAnalysisService
from jobpilot_api.application.providers import EvidenceMapProvider, JDAnalysisProvider
from jobpilot_api.application.resume_imports import ResumeImportService
from jobpilot_api.application.services import (
    ApplicationService,
    AutofillProfileService,
    FeedbackSummaryService,
    InterviewService,
    JobService,
    ResumeVersionService,
)
from jobpilot_api.config import LLMSettings
from jobpilot_api.infrastructure.ai.openai_compatible import (
    OpenAICompatibleJDAnalysisProvider,
)
from jobpilot_api.infrastructure.database.engine import create_database_engine
from jobpilot_api.infrastructure.database.repositories import (
    SqlAlchemyApplicationRepository,
    SqlAlchemyAutofillProfileRepository,
    SqlAlchemyEvidenceMapRepository,
    SqlAlchemyFeedbackSummaryRepository,
    SqlAlchemyInterviewRepository,
    SqlAlchemyJDAnalysisRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyResumeImportRepository,
    SqlAlchemyResumeVersionRepository,
)


class ServiceProvider:
    def __init__(
        self,
        database_path: Path,
        llm_settings: LLMSettings | None,
        analysis_provider: JDAnalysisProvider | None = None,
        evidence_map_provider: EvidenceMapProvider | None = None,
    ) -> None:
        self._database_path = database_path
        self._lock = Lock()
        self._engine: Engine | None = None
        self._jobs: JobService | None = None
        self._applications: ApplicationService | None = None
        self._analysis: JDAnalysisService | None = None
        self._resumes: ResumeVersionService | None = None
        self._evidence_maps: EvidenceMapService | None = None
        self._interviews: InterviewService | None = None
        self._feedback: FeedbackSummaryService | None = None
        self._autofill_profile: AutofillProfileService | None = None
        self._resume_import: ResumeImportService | None = None
        configured_provider = (
            OpenAICompatibleJDAnalysisProvider(llm_settings) if llm_settings is not None else None
        )
        self._analysis_provider = analysis_provider or configured_provider
        self._evidence_map_provider = evidence_map_provider or configured_provider

    def services(
        self,
    ) -> tuple[
        JobService,
        ApplicationService,
        JDAnalysisService,
        ResumeVersionService,
        EvidenceMapService,
        InterviewService,
        FeedbackSummaryService,
        AutofillProfileService,
    ]:
        if (
            self._jobs is None
            or self._applications is None
            or self._analysis is None
            or self._resumes is None
            or self._evidence_maps is None
            or self._interviews is None
            or self._feedback is None
            or self._autofill_profile is None
        ):
            with self._lock:
                if (
                    self._jobs is None
                    or self._applications is None
                    or self._analysis is None
                    or self._resumes is None
                    or self._evidence_maps is None
                    or self._interviews is None
                    or self._feedback is None
                    or self._autofill_profile is None
                ):
                    engine = create_database_engine(self._database_path)
                    sessions = sessionmaker(engine, expire_on_commit=False)
                    job_repository = SqlAlchemyJobRepository(sessions)
                    application_repository = SqlAlchemyApplicationRepository(sessions)
                    analysis_repository = SqlAlchemyJDAnalysisRepository(sessions)
                    resume_repository = SqlAlchemyResumeVersionRepository(sessions)
                    evidence_map_repository = SqlAlchemyEvidenceMapRepository(sessions)
                    interview_repository = SqlAlchemyInterviewRepository(sessions)
                    feedback_repository = SqlAlchemyFeedbackSummaryRepository(sessions)
                    autofill_profile_repository = SqlAlchemyAutofillProfileRepository(sessions)
                    resume_import_repository = SqlAlchemyResumeImportRepository(sessions)
                    self._engine = engine
                    self._jobs = JobService(job_repository)
                    self._applications = ApplicationService(
                        application_repository,
                        job_repository,
                        resume_repository,
                    )
                    self._analysis = JDAnalysisService(
                        analysis_repository,
                        job_repository,
                        self._analysis_provider,
                    )
                    self._resumes = ResumeVersionService(resume_repository)
                    self._evidence_maps = EvidenceMapService(
                        evidence_map_repository,
                        job_repository,
                        resume_repository,
                        self._analysis,
                        self._evidence_map_provider,
                    )
                    self._interviews = InterviewService(
                        interview_repository,
                        application_repository,
                    )
                    self._feedback = FeedbackSummaryService(feedback_repository)
                    self._autofill_profile = AutofillProfileService(autofill_profile_repository)
                    self._resume_import = ResumeImportService(resume_import_repository)
        return (
            self._jobs,
            self._applications,
            self._analysis,
            self._resumes,
            self._evidence_maps,
            self._interviews,
            self._feedback,
            self._autofill_profile,
        )

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()

    def resume_import_service(self) -> ResumeImportService:
        self.services()
        assert self._resume_import is not None
        return self._resume_import


def get_job_service(request: Request) -> JobService:
    jobs, _, _, _, _, _, _, _ = request.app.state.service_provider.services()
    return jobs


def get_application_service(request: Request) -> ApplicationService:
    _, applications, _, _, _, _, _, _ = request.app.state.service_provider.services()
    return applications


def get_analysis_service(request: Request) -> JDAnalysisService:
    _, _, analysis, _, _, _, _, _ = request.app.state.service_provider.services()
    return analysis


def get_resume_version_service(request: Request) -> ResumeVersionService:
    _, _, _, resumes, _, _, _, _ = request.app.state.service_provider.services()
    return resumes


def get_evidence_map_service(request: Request) -> EvidenceMapService:
    _, _, _, _, evidence_maps, _, _, _ = request.app.state.service_provider.services()
    return evidence_maps


def get_interview_service(request: Request) -> InterviewService:
    _, _, _, _, _, interviews, _, _ = request.app.state.service_provider.services()
    return interviews


def get_feedback_summary_service(request: Request) -> FeedbackSummaryService:
    _, _, _, _, _, _, feedback, _ = request.app.state.service_provider.services()
    return feedback


def get_autofill_profile_service(request: Request) -> AutofillProfileService:
    _, _, _, _, _, _, _, autofill_profile = request.app.state.service_provider.services()
    return autofill_profile


def get_resume_import_service(request: Request) -> ResumeImportService:
    return request.app.state.service_provider.resume_import_service()
