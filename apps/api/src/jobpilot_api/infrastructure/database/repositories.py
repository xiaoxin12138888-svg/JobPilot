from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from jobpilot_api.application.repositories import ApplicationListEntry, JobListEntry
from jobpilot_api.domain.applications import Application, ApplicationStatus
from jobpilot_api.domain.errors import (
    ApplicationAlreadyExistsError,
    DatabaseBusyError,
    DuplicateJobError,
)
from jobpilot_api.domain.jd_analysis import (
    JD_ANALYSIS_SCHEMA_VERSION,
    JDAnalysis,
    JDAnalysisRecord,
    analysis_from_stored_json,
)
from jobpilot_api.domain.jobs import Job, JobDraft
from jobpilot_api.infrastructure.database.models import (
    ApplicationModel,
    JDAnalysisRecordModel,
    JobModel,
)


class SqlAlchemyJobRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, draft: JobDraft) -> Job:
        now = datetime.now(UTC)
        model = JobModel(
            id=str(uuid4()),
            **_draft_values(draft),
            created_at=now,
            updated_at=now,
        )
        try:
            with self._sessions.begin() as session:
                session.add(model)
        except IntegrityError as error:
            raise DuplicateJobError(
                "该岗位链接已经保存",
                resource_id=self._existing_job_id(draft.normalized_source_url),
            ) from error
        except OperationalError as error:
            raise _database_error(error) from error
        return _job(model)

    def get(self, job_id: str) -> Job | None:
        try:
            with self._sessions() as session:
                model = session.get(JobModel, job_id)
                return _job(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error

    def update(self, job_id: str, draft: JobDraft) -> Job | None:
        try:
            with self._sessions.begin() as session:
                model = session.get(JobModel, job_id)
                if model is None:
                    return None
                for name, value in _draft_values(draft).items():
                    setattr(model, name, value)
                model.updated_at = datetime.now(UTC)
        except IntegrityError as error:
            raise DuplicateJobError(
                "该岗位链接已经保存",
                resource_id=self._existing_job_id(draft.normalized_source_url),
            ) from error
        except OperationalError as error:
            raise _database_error(error) from error
        return _job(model)

    def _existing_job_id(self, normalized_source_url: str | None) -> str | None:
        if normalized_source_url is None:
            return None
        try:
            with self._sessions() as session:
                return session.scalar(
                    select(JobModel.id).where(
                        JobModel.normalized_source_url == normalized_source_url
                    )
                )
        except OperationalError as error:
            raise _database_error(error) from error

    def delete(self, job_id: str) -> bool:
        try:
            with self._sessions.begin() as session:
                model = session.get(JobModel, job_id)
                if model is None:
                    return False
                session.delete(model)
                return True
        except OperationalError as error:
            raise _database_error(error) from error

    def list(
        self,
        *,
        keyword: str | None,
        source: str | None,
        application_status: ApplicationStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[JobListEntry], int]:
        statement = select(JobModel, ApplicationModel.status).outerjoin(
            ApplicationModel, ApplicationModel.job_id == JobModel.id
        )
        count_statement = (
            select(func.count())
            .select_from(JobModel)
            .outerjoin(ApplicationModel, ApplicationModel.job_id == JobModel.id)
        )
        filters = []
        if keyword:
            pattern = f"%{keyword}%"
            filters.append(
                or_(
                    JobModel.title.ilike(pattern),
                    JobModel.company.ilike(pattern),
                    JobModel.location.ilike(pattern),
                )
            )
        if source:
            filters.append(JobModel.source == source)
        if application_status:
            filters.append(ApplicationModel.status == application_status.value)
        if filters:
            statement = statement.where(*filters)
            count_statement = count_statement.where(*filters)
        statement = (
            statement.order_by(JobModel.updated_at.desc(), JobModel.id).limit(limit).offset(offset)
        )
        try:
            with self._sessions() as session:
                rows = session.execute(statement).all()
                total = session.scalar(count_statement) or 0
                entries = [
                    JobListEntry(
                        job=_job(model),
                        application_status=ApplicationStatus(status) if status else None,
                    )
                    for model, status in rows
                ]
                return entries, total
        except OperationalError as error:
            raise _database_error(error) from error


class SqlAlchemyApplicationRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, job_id: str) -> Application:
        now = datetime.now(UTC)
        model = ApplicationModel(
            id=str(uuid4()),
            job_id=job_id,
            status=ApplicationStatus.PLANNED.value,
            applied_at=None,
            created_at=now,
            updated_at=now,
        )
        try:
            with self._sessions.begin() as session:
                session.add(model)
        except IntegrityError as error:
            raise ApplicationAlreadyExistsError("该岗位已经有投递记录") from error
        except OperationalError as error:
            raise _database_error(error) from error
        return _application(model)

    def get(self, application_id: str) -> Application | None:
        try:
            with self._sessions() as session:
                model = session.get(ApplicationModel, application_id)
                return _application(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error

    def update_status(
        self,
        application_id: str,
        status: ApplicationStatus,
    ) -> Application | None:
        try:
            with self._sessions.begin() as session:
                model = session.get(ApplicationModel, application_id)
                if model is None:
                    return None
                now = datetime.now(UTC)
                model.status = status.value
                if status == ApplicationStatus.APPLIED and model.applied_at is None:
                    model.applied_at = now
                model.updated_at = now
        except OperationalError as error:
            raise _database_error(error) from error
        return _application(model)

    def list(
        self,
        *,
        job_id: str | None,
        status: ApplicationStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ApplicationListEntry], int]:
        statement = select(ApplicationModel, JobModel.title, JobModel.company).join(JobModel)
        count_statement = select(func.count()).select_from(ApplicationModel)
        if job_id:
            statement = statement.where(ApplicationModel.job_id == job_id)
            count_statement = count_statement.where(ApplicationModel.job_id == job_id)
        if status:
            statement = statement.where(ApplicationModel.status == status.value)
            count_statement = count_statement.where(ApplicationModel.status == status.value)
        statement = (
            statement.order_by(ApplicationModel.updated_at.desc(), ApplicationModel.id)
            .limit(limit)
            .offset(offset)
        )
        try:
            with self._sessions() as session:
                rows = session.execute(statement).all()
                total = session.scalar(count_statement) or 0
                return (
                    [
                        ApplicationListEntry(
                            application=_application(model),
                            job_title=title,
                            company=company,
                        )
                        for model, title, company in rows
                    ],
                    total,
                )
        except OperationalError as error:
            raise _database_error(error) from error


class SqlAlchemyJDAnalysisRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self, job_id: str) -> JDAnalysisRecord | None:
        try:
            with self._sessions() as session:
                model = session.scalar(
                    select(JDAnalysisRecordModel).where(JDAnalysisRecordModel.job_id == job_id)
                )
                return _analysis_record(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error

    def upsert(
        self,
        job_id: str,
        result: JDAnalysis,
        source_fingerprint: str,
    ) -> JDAnalysisRecord:
        now = datetime.now(UTC)
        result_json = json.dumps(
            result.as_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        try:
            with self._sessions.begin() as session:
                model = session.scalar(
                    select(JDAnalysisRecordModel).where(JDAnalysisRecordModel.job_id == job_id)
                )
                if model is None:
                    model = JDAnalysisRecordModel(
                        id=str(uuid4()),
                        job_id=job_id,
                        schema_version=JD_ANALYSIS_SCHEMA_VERSION,
                        result_json=result_json,
                        source_fingerprint=source_fingerprint,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(model)
                else:
                    model.schema_version = JD_ANALYSIS_SCHEMA_VERSION
                    model.result_json = result_json
                    model.source_fingerprint = source_fingerprint
                    model.updated_at = now
        except OperationalError as error:
            raise _database_error(error) from error
        return _analysis_record(model)


def _draft_values(draft: JobDraft) -> dict[str, object]:
    return {
        "title": draft.title,
        "company": draft.company,
        "location": draft.location,
        "salary_text": draft.salary_text,
        "source": draft.source,
        "source_url": draft.source_url,
        "normalized_source_url": draft.normalized_source_url,
        "description": draft.description,
        "notes": draft.notes,
    }


def _job(model: JobModel) -> Job:
    return Job(
        id=model.id,
        title=model.title,
        company=model.company,
        location=model.location,
        salary_text=model.salary_text,
        source=model.source,
        source_url=model.source_url,
        normalized_source_url=model.normalized_source_url,
        description=model.description,
        notes=model.notes,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _application(model: ApplicationModel) -> Application:
    return Application(
        id=model.id,
        job_id=model.job_id,
        status=ApplicationStatus(model.status),
        applied_at=_utc(model.applied_at) if model.applied_at else None,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _analysis_record(model: JDAnalysisRecordModel) -> JDAnalysisRecord:
    return JDAnalysisRecord(
        id=model.id,
        job_id=model.job_id,
        schema_version=model.schema_version,
        result=analysis_from_stored_json(model.result_json),
        source_fingerprint=model.source_fingerprint,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _database_error(error: OperationalError) -> DatabaseBusyError:
    message = str(error.orig).lower()
    if "locked" in message or "busy" in message:
        return DatabaseBusyError("本地数据库暂时繁忙，请稍后重试")
    raise error
