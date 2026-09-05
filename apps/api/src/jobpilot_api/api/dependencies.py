from __future__ import annotations

from pathlib import Path
from threading import Lock

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from jobpilot_api.application.jd_analysis import JDAnalysisService
from jobpilot_api.application.providers import JDAnalysisProvider
from jobpilot_api.application.services import ApplicationService, JobService, ResumeVersionService
from jobpilot_api.config import LLMSettings
from jobpilot_api.infrastructure.ai.openai_compatible import (
    OpenAICompatibleJDAnalysisProvider,
)
from jobpilot_api.infrastructure.database.engine import create_database_engine
from jobpilot_api.infrastructure.database.repositories import (
    SqlAlchemyApplicationRepository,
    SqlAlchemyJDAnalysisRepository,
    SqlAlchemyJobRepository,
    SqlAlchemyResumeVersionRepository,
)


class ServiceProvider:
    def __init__(
        self,
        database_path: Path,
        llm_settings: LLMSettings | None,
        analysis_provider: JDAnalysisProvider | None = None,
    ) -> None:
        self._database_path = database_path
        self._lock = Lock()
        self._engine: Engine | None = None
        self._jobs: JobService | None = None
        self._applications: ApplicationService | None = None
        self._analysis: JDAnalysisService | None = None
        self._resumes: ResumeVersionService | None = None
        self._analysis_provider = analysis_provider or (
            OpenAICompatibleJDAnalysisProvider(llm_settings) if llm_settings is not None else None
        )

    def services(
        self,
    ) -> tuple[JobService, ApplicationService, JDAnalysisService, ResumeVersionService]:
        if (
            self._jobs is None
            or self._applications is None
            or self._analysis is None
            or self._resumes is None
        ):
            with self._lock:
                if (
                    self._jobs is None
                    or self._applications is None
                    or self._analysis is None
                    or self._resumes is None
                ):
                    engine = create_database_engine(self._database_path)
                    sessions = sessionmaker(engine, expire_on_commit=False)
                    job_repository = SqlAlchemyJobRepository(sessions)
                    application_repository = SqlAlchemyApplicationRepository(sessions)
                    analysis_repository = SqlAlchemyJDAnalysisRepository(sessions)
                    resume_repository = SqlAlchemyResumeVersionRepository(sessions)
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
        return self._jobs, self._applications, self._analysis, self._resumes

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()


def get_job_service(request: Request) -> JobService:
    jobs, _, _, _ = request.app.state.service_provider.services()
    return jobs


def get_application_service(request: Request) -> ApplicationService:
    _, applications, _, _ = request.app.state.service_provider.services()
    return applications


def get_analysis_service(request: Request) -> JDAnalysisService:
    _, _, analysis, _ = request.app.state.service_provider.services()
    return analysis


def get_resume_version_service(request: Request) -> ResumeVersionService:
    _, _, _, resumes = request.app.state.service_provider.services()
    return resumes
