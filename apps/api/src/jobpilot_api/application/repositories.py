from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from jobpilot_api.domain.applications import Application, ApplicationStatus
from jobpilot_api.domain.jobs import Job, JobDraft


@dataclass(frozen=True, slots=True)
class JobListEntry:
    job: Job
    application_status: ApplicationStatus | None


@dataclass(frozen=True, slots=True)
class ApplicationListEntry:
    application: Application
    job_title: str
    company: str


class JobRepository(Protocol):
    def create(self, draft: JobDraft) -> Job: ...

    def get(self, job_id: str) -> Job | None: ...

    def update(self, job_id: str, draft: JobDraft) -> Job | None: ...

    def delete(self, job_id: str) -> bool: ...

    def list(
        self,
        *,
        keyword: str | None,
        source: str | None,
        application_status: ApplicationStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[JobListEntry], int]: ...


class ApplicationRepository(Protocol):
    def create(self, job_id: str) -> Application: ...

    def get(self, application_id: str) -> Application | None: ...

    def update_status(
        self,
        application_id: str,
        status: ApplicationStatus,
    ) -> Application | None: ...

    def list(
        self,
        *,
        job_id: str | None,
        status: ApplicationStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ApplicationListEntry], int]: ...
