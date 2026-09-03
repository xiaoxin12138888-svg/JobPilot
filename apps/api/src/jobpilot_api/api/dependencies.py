from __future__ import annotations

from pathlib import Path
from threading import Lock

from fastapi import Request
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from jobpilot_api.application.services import ApplicationService, JobService
from jobpilot_api.infrastructure.database.engine import create_database_engine
from jobpilot_api.infrastructure.database.repositories import (
    SqlAlchemyApplicationRepository,
    SqlAlchemyJobRepository,
)


class ServiceProvider:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._lock = Lock()
        self._engine: Engine | None = None
        self._jobs: JobService | None = None
        self._applications: ApplicationService | None = None

    def services(self) -> tuple[JobService, ApplicationService]:
        if self._jobs is None or self._applications is None:
            with self._lock:
                if self._jobs is None or self._applications is None:
                    engine = create_database_engine(self._database_path)
                    sessions = sessionmaker(engine, expire_on_commit=False)
                    job_repository = SqlAlchemyJobRepository(sessions)
                    application_repository = SqlAlchemyApplicationRepository(sessions)
                    self._engine = engine
                    self._jobs = JobService(job_repository)
                    self._applications = ApplicationService(
                        application_repository,
                        job_repository,
                    )
        return self._jobs, self._applications

    def close(self) -> None:
        if self._engine is not None:
            self._engine.dispose()


def get_job_service(request: Request) -> JobService:
    jobs, _ = request.app.state.service_provider.services()
    return jobs


def get_application_service(request: Request) -> ApplicationService:
    _, applications = request.app.state.service_provider.services()
    return applications
