from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from jobpilot_api.application.repositories import ApplicationListEntry, JobListEntry
from jobpilot_api.domain.applications import Application, ApplicationStatus, RejectionReason
from jobpilot_api.domain.autofill_profiles import AutofillProfile, AutofillProfileDraft
from jobpilot_api.domain.copilot import (
    COPILOT_SCHEMA_VERSION,
    CopilotKind,
    CopilotRecord,
    CopilotResult,
    copilot_result_from_stored_json,
)
from jobpilot_api.domain.errors import (
    ApplicationAlreadyExistsError,
    DatabaseBusyError,
    DuplicateJobError,
    ResumeVersionInUseError,
)
from jobpilot_api.domain.evidence_maps import (
    EVIDENCE_MAP_SCHEMA_VERSION,
    EvidenceMap,
    EvidenceMapRecord,
    evidence_map_from_stored_json,
)
from jobpilot_api.domain.feedback import (
    FeedbackGroupStats,
    FeedbackSummary,
    FeedbackTotals,
    ResumeVersionFeedbackStats,
    build_feedback_summary,
)
from jobpilot_api.domain.interviews import (
    InterviewQuestion,
    InterviewQuestionDraft,
    InterviewRound,
    InterviewRoundDetail,
    InterviewRoundDraft,
    InterviewStatus,
    InterviewType,
    QuestionCategory,
    QuestionPerformance,
)
from jobpilot_api.domain.jd_analysis import (
    JD_ANALYSIS_SCHEMA_VERSION,
    JDAnalysis,
    JDAnalysisRecord,
    analysis_from_stored_json,
)
from jobpilot_api.domain.jobs import Job, JobDraft
from jobpilot_api.domain.resume_imports import (
    ResumeImportConfirmation,
    ResumeProfileImportPatch,
    merge_autofill_profile,
)
from jobpilot_api.domain.resume_versions import ResumeVersion, ResumeVersionDraft
from jobpilot_api.infrastructure.database.models import (
    ApplicationModel,
    AutofillProfileModel,
    CopilotRecordModel,
    EvidenceMapRecordModel,
    InterviewQuestionModel,
    InterviewRoundModel,
    JDAnalysisRecordModel,
    JobModel,
    ResumeVersionModel,
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
            resume_version_id=None,
            outcome_note=None,
            rejection_reason=None,
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

    def update(
        self,
        application_id: str,
        *,
        status: ApplicationStatus | None,
        resume_version_id: str | None,
        update_resume_version: bool,
        outcome_note: str | None = None,
        update_outcome_note: bool = False,
        rejection_reason: RejectionReason | None = None,
        update_rejection_reason: bool = False,
    ) -> Application | None:
        try:
            with self._sessions.begin() as session:
                model = session.get(ApplicationModel, application_id)
                if model is None:
                    return None
                now = datetime.now(UTC)
                if status is not None:
                    model.status = status.value
                    if status == ApplicationStatus.APPLIED and model.applied_at is None:
                        model.applied_at = now
                if update_resume_version:
                    model.resume_version_id = resume_version_id
                if update_outcome_note:
                    model.outcome_note = outcome_note
                if update_rejection_reason:
                    model.rejection_reason = (
                        rejection_reason.value if rejection_reason is not None else None
                    )
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


class SqlAlchemyResumeVersionRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, draft: ResumeVersionDraft) -> ResumeVersion:
        now = datetime.now(UTC)
        model = ResumeVersionModel(
            id=str(uuid4()),
            name=draft.name,
            content=draft.content,
            created_at=now,
            updated_at=now,
        )
        try:
            with self._sessions.begin() as session:
                session.add(model)
        except OperationalError as error:
            raise _database_error(error) from error
        return _resume_version(model, application_count=0)

    def get(self, resume_version_id: str) -> ResumeVersion | None:
        statement = (
            select(ResumeVersionModel, func.count(ApplicationModel.id))
            .outerjoin(
                ApplicationModel,
                ApplicationModel.resume_version_id == ResumeVersionModel.id,
            )
            .where(ResumeVersionModel.id == resume_version_id)
            .group_by(ResumeVersionModel.id)
        )
        try:
            with self._sessions() as session:
                row = session.execute(statement).one_or_none()
                return _resume_version(row[0], application_count=row[1]) if row else None
        except OperationalError as error:
            raise _database_error(error) from error

    def update(self, resume_version_id: str, draft: ResumeVersionDraft) -> ResumeVersion | None:
        try:
            with self._sessions.begin() as session:
                model = session.get(ResumeVersionModel, resume_version_id)
                if model is None:
                    return None
                model.name = draft.name
                model.content = draft.content
                model.updated_at = datetime.now(UTC)
                application_count = (
                    session.scalar(
                        select(func.count(ApplicationModel.id)).where(
                            ApplicationModel.resume_version_id == resume_version_id
                        )
                    )
                    or 0
                )
        except OperationalError as error:
            raise _database_error(error) from error
        return _resume_version(model, application_count=application_count)

    def delete(self, resume_version_id: str) -> bool:
        try:
            with self._sessions.begin() as session:
                model = session.get(ResumeVersionModel, resume_version_id)
                if model is None:
                    return False
                in_use = session.scalar(
                    select(func.count(ApplicationModel.id)).where(
                        ApplicationModel.resume_version_id == resume_version_id
                    )
                )
                if in_use:
                    raise ResumeVersionInUseError("该简历版本已关联投递记录，无法直接删除。")
                session.delete(model)
        except IntegrityError as error:
            raise ResumeVersionInUseError("该简历版本已关联投递记录，无法直接删除。") from error
        except OperationalError as error:
            raise _database_error(error) from error
        return True

    def list(self, *, limit: int, offset: int) -> tuple[list[ResumeVersion], int]:
        statement = (
            select(ResumeVersionModel, func.count(ApplicationModel.id))
            .outerjoin(
                ApplicationModel,
                ApplicationModel.resume_version_id == ResumeVersionModel.id,
            )
            .group_by(ResumeVersionModel.id)
            .order_by(ResumeVersionModel.updated_at.desc(), ResumeVersionModel.id)
            .limit(limit)
            .offset(offset)
        )
        try:
            with self._sessions() as session:
                rows = session.execute(statement).all()
                total = session.scalar(select(func.count()).select_from(ResumeVersionModel)) or 0
                return (
                    [
                        _resume_version(model, application_count=application_count)
                        for model, application_count in rows
                    ],
                    total,
                )
        except OperationalError as error:
            raise _database_error(error) from error


class SqlAlchemyAutofillProfileRepository:
    _PROFILE_ID = 1

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self) -> AutofillProfile | None:
        try:
            with self._sessions() as session:
                model = session.get(AutofillProfileModel, self._PROFILE_ID)
                return _autofill_profile(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error

    def upsert(self, draft: AutofillProfileDraft) -> AutofillProfile:
        now = datetime.now(UTC)
        values = _autofill_profile_draft_values(draft)
        try:
            with self._sessions.begin() as session:
                model = session.get(AutofillProfileModel, self._PROFILE_ID)
                if model is None:
                    model = AutofillProfileModel(
                        id=self._PROFILE_ID,
                        **values,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(model)
                else:
                    for name, value in values.items():
                        setattr(model, name, value)
                    model.updated_at = now
        except OperationalError as error:
            raise _database_error(error) from error
        return _autofill_profile(model)


class SqlAlchemyResumeImportRepository:
    _PROFILE_ID = 1

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def confirm(
        self,
        resume_version: ResumeVersionDraft | None,
        profile_import: ResumeProfileImportPatch | None,
    ) -> ResumeImportConfirmation:
        now = datetime.now(UTC)
        resume_model: ResumeVersionModel | None = None
        profile_model: AutofillProfileModel | None = None
        try:
            with self._sessions.begin() as session:
                if resume_version is not None:
                    resume_model = ResumeVersionModel(
                        id=str(uuid4()),
                        name=resume_version.name,
                        content=resume_version.content,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(resume_model)
                if profile_import is not None:
                    profile_model = session.get(AutofillProfileModel, self._PROFILE_ID)
                    current = (
                        _autofill_profile(profile_model) if profile_model is not None else None
                    )
                    merged = merge_autofill_profile(current, profile_import)
                    values = _autofill_profile_draft_values(merged)
                    if profile_model is None:
                        profile_model = AutofillProfileModel(
                            id=self._PROFILE_ID,
                            **values,
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(profile_model)
                    else:
                        for name, value in values.items():
                            setattr(profile_model, name, value)
                        profile_model.updated_at = now
        except OperationalError as error:
            raise _database_error(error) from error
        return ResumeImportConfirmation(
            resume_version=(
                _resume_version(resume_model, application_count=0)
                if resume_model is not None
                else None
            ),
            profile=_autofill_profile(profile_model) if profile_model is not None else None,
        )


class SqlAlchemyEvidenceMapRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get(self, job_id: str, resume_version_id: str) -> EvidenceMapRecord | None:
        try:
            with self._sessions() as session:
                model = session.scalar(
                    select(EvidenceMapRecordModel).where(
                        EvidenceMapRecordModel.job_id == job_id,
                        EvidenceMapRecordModel.resume_version_id == resume_version_id,
                    )
                )
                return _evidence_map_record(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error

    def upsert(
        self,
        job_id: str,
        resume_version_id: str,
        result: EvidenceMap,
        job_analysis_fingerprint: str,
        resume_content_fingerprint: str,
    ) -> EvidenceMapRecord:
        now = datetime.now(UTC)
        result_json = json.dumps(
            result.as_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
        try:
            with self._sessions.begin() as session:
                model = session.scalar(
                    select(EvidenceMapRecordModel).where(
                        EvidenceMapRecordModel.job_id == job_id,
                        EvidenceMapRecordModel.resume_version_id == resume_version_id,
                    )
                )
                if model is None:
                    model = EvidenceMapRecordModel(
                        id=str(uuid4()),
                        job_id=job_id,
                        resume_version_id=resume_version_id,
                        schema_version=EVIDENCE_MAP_SCHEMA_VERSION,
                        result_json=result_json,
                        job_analysis_fingerprint=job_analysis_fingerprint,
                        resume_content_fingerprint=resume_content_fingerprint,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(model)
                else:
                    model.schema_version = EVIDENCE_MAP_SCHEMA_VERSION
                    model.result_json = result_json
                    model.job_analysis_fingerprint = job_analysis_fingerprint
                    model.resume_content_fingerprint = resume_content_fingerprint
                    model.updated_at = now
        except OperationalError as error:
            raise _database_error(error) from error
        return _evidence_map_record(model)


class SqlAlchemyCopilotRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(
        self,
        *,
        job_id: str,
        resume_version_id: str | None,
        kind: CopilotKind,
        result: CopilotResult,
        input_fingerprint: str,
        model: str,
        prompt_version: str,
    ) -> CopilotRecord:
        record = CopilotRecordModel(
            id=str(uuid4()),
            job_id=job_id,
            resume_version_id=resume_version_id,
            kind=kind.value,
            schema_version=COPILOT_SCHEMA_VERSION,
            result_json=_canonical_json(result.as_dict()),
            input_fingerprint=input_fingerprint,
            model=model,
            prompt_version=prompt_version,
            created_at=datetime.now(UTC),
        )
        try:
            with self._sessions.begin() as session:
                session.add(record)
        except OperationalError as error:
            raise _database_error(error) from error
        return _copilot_record(record)

    def get(self, record_id: str) -> CopilotRecord | None:
        try:
            with self._sessions() as session:
                model = session.get(CopilotRecordModel, record_id)
                return _copilot_record(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error

    def get_latest(
        self,
        *,
        job_id: str,
        resume_version_id: str | None,
        kind: CopilotKind,
    ) -> CopilotRecord | None:
        statement = (
            select(CopilotRecordModel)
            .where(
                CopilotRecordModel.job_id == job_id,
                CopilotRecordModel.resume_version_id == resume_version_id,
                CopilotRecordModel.kind == kind.value,
            )
            .order_by(CopilotRecordModel.created_at.desc(), CopilotRecordModel.id.desc())
            .limit(1)
        )
        try:
            with self._sessions() as session:
                model = session.scalar(statement)
                return _copilot_record(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error


class SqlAlchemyInterviewRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create_round(self, application_id: str, draft: InterviewRoundDraft) -> InterviewRound:
        now = datetime.now(UTC)
        model = InterviewRoundModel(
            id=str(uuid4()),
            application_id=application_id,
            **_round_draft_values(draft),
            created_at=now,
            updated_at=now,
        )
        try:
            with self._sessions.begin() as session:
                session.add(model)
        except OperationalError as error:
            raise _database_error(error) from error
        return _interview_round(model)

    def get_round(self, interview_id: str) -> InterviewRoundDetail | None:
        try:
            with self._sessions() as session:
                model = session.get(InterviewRoundModel, interview_id)
                if model is None:
                    return None
                questions = session.scalars(
                    select(InterviewQuestionModel)
                    .where(InterviewQuestionModel.interview_round_id == interview_id)
                    .order_by(InterviewQuestionModel.created_at, InterviewQuestionModel.id)
                ).all()
                return InterviewRoundDetail(
                    interview=_interview_round(model),
                    questions=tuple(_interview_question(question) for question in questions),
                )
        except OperationalError as error:
            raise _database_error(error) from error

    def update_round(
        self, interview_id: str, draft: InterviewRoundDraft
    ) -> InterviewRoundDetail | None:
        try:
            with self._sessions.begin() as session:
                model = session.get(InterviewRoundModel, interview_id)
                if model is None:
                    return None
                for name, value in _round_draft_values(draft).items():
                    setattr(model, name, value)
                model.updated_at = datetime.now(UTC)
                questions = session.scalars(
                    select(InterviewQuestionModel)
                    .where(InterviewQuestionModel.interview_round_id == interview_id)
                    .order_by(InterviewQuestionModel.created_at, InterviewQuestionModel.id)
                ).all()
        except OperationalError as error:
            raise _database_error(error) from error
        return InterviewRoundDetail(
            interview=_interview_round(model),
            questions=tuple(_interview_question(question) for question in questions),
        )

    def delete_round(self, interview_id: str) -> bool:
        try:
            with self._sessions.begin() as session:
                model = session.get(InterviewRoundModel, interview_id)
                if model is None:
                    return False
                session.delete(model)
                return True
        except OperationalError as error:
            raise _database_error(error) from error

    def list_rounds(
        self, *, application_id: str, limit: int, offset: int
    ) -> tuple[list[InterviewRoundDetail], int]:
        statement = (
            select(InterviewRoundModel)
            .where(InterviewRoundModel.application_id == application_id)
            .order_by(
                InterviewRoundModel.scheduled_at.is_(None),
                InterviewRoundModel.scheduled_at,
                InterviewRoundModel.created_at,
                InterviewRoundModel.id,
            )
            .limit(limit)
            .offset(offset)
        )
        try:
            with self._sessions() as session:
                models = session.scalars(statement).all()
                total = (
                    session.scalar(
                        select(func.count())
                        .select_from(InterviewRoundModel)
                        .where(InterviewRoundModel.application_id == application_id)
                    )
                    or 0
                )
                questions_by_round: dict[str, list[InterviewQuestion]] = {
                    model.id: [] for model in models
                }
                if questions_by_round:
                    questions = session.scalars(
                        select(InterviewQuestionModel)
                        .where(InterviewQuestionModel.interview_round_id.in_(questions_by_round))
                        .order_by(InterviewQuestionModel.created_at, InterviewQuestionModel.id)
                    ).all()
                    for question in questions:
                        questions_by_round[question.interview_round_id].append(
                            _interview_question(question)
                        )
                return (
                    [
                        InterviewRoundDetail(
                            interview=_interview_round(model),
                            questions=tuple(questions_by_round[model.id]),
                        )
                        for model in models
                    ],
                    total,
                )
        except OperationalError as error:
            raise _database_error(error) from error

    def create_question(
        self, interview_id: str, draft: InterviewQuestionDraft
    ) -> InterviewQuestion:
        now = datetime.now(UTC)
        model = InterviewQuestionModel(
            id=str(uuid4()),
            interview_round_id=interview_id,
            **_question_draft_values(draft),
            created_at=now,
            updated_at=now,
        )
        try:
            with self._sessions.begin() as session:
                session.add(model)
        except OperationalError as error:
            raise _database_error(error) from error
        return _interview_question(model)

    def get_question(self, question_id: str) -> InterviewQuestion | None:
        try:
            with self._sessions() as session:
                model = session.get(InterviewQuestionModel, question_id)
                return _interview_question(model) if model is not None else None
        except OperationalError as error:
            raise _database_error(error) from error

    def update_question(
        self, question_id: str, draft: InterviewQuestionDraft
    ) -> InterviewQuestion | None:
        try:
            with self._sessions.begin() as session:
                model = session.get(InterviewQuestionModel, question_id)
                if model is None:
                    return None
                for name, value in _question_draft_values(draft).items():
                    setattr(model, name, value)
                model.updated_at = datetime.now(UTC)
        except OperationalError as error:
            raise _database_error(error) from error
        return _interview_question(model)

    def delete_question(self, question_id: str) -> bool:
        try:
            with self._sessions.begin() as session:
                model = session.get(InterviewQuestionModel, question_id)
                if model is None:
                    return False
                session.delete(model)
                return True
        except OperationalError as error:
            raise _database_error(error) from error


class SqlAlchemyFeedbackSummaryRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def get_summary(self) -> FeedbackSummary:
        try:
            with self._sessions() as session:
                totals = FeedbackTotals(
                    saved_jobs=_count(session, JobModel),
                    applications=_count(session, ApplicationModel),
                    interview_applications=(
                        session.scalar(
                            select(func.count(func.distinct(InterviewRoundModel.application_id)))
                        )
                        or 0
                    ),
                    interviews=_count(session, InterviewRoundModel),
                    questions=_count(session, InterviewQuestionModel),
                    offers=(
                        session.scalar(
                            select(func.count())
                            .select_from(ApplicationModel)
                            .where(ApplicationModel.status == ApplicationStatus.OFFER.value)
                        )
                        or 0
                    ),
                    rejected=(
                        session.scalar(
                            select(func.count())
                            .select_from(ApplicationModel)
                            .where(ApplicationModel.status == ApplicationStatus.REJECTED.value)
                        )
                        or 0
                    ),
                )
                category_counts = {
                    QuestionCategory(category): count
                    for category, count in session.execute(
                        select(InterviewQuestionModel.category, func.count())
                        .group_by(InterviewQuestionModel.category)
                        .order_by(InterviewQuestionModel.category)
                    )
                }
                performance_counts = {
                    QuestionPerformance(performance): count
                    for performance, count in session.execute(
                        select(InterviewQuestionModel.performance, func.count())
                        .group_by(InterviewQuestionModel.performance)
                        .order_by(InterviewQuestionModel.performance)
                    )
                }
                weak_counts = {
                    QuestionCategory(category): (question_count, weak_count)
                    for category, question_count, weak_count in session.execute(
                        select(
                            InterviewQuestionModel.category,
                            func.count(),
                            func.sum(
                                case(
                                    (
                                        InterviewQuestionModel.performance.in_(
                                            [
                                                QuestionPerformance.OK.value,
                                                QuestionPerformance.POOR.value,
                                            ]
                                        ),
                                        1,
                                    ),
                                    else_=0,
                                )
                            ),
                        ).group_by(InterviewQuestionModel.category)
                    )
                }
                rejection_reason_counts = {
                    RejectionReason(reason): count
                    for reason, count in session.execute(
                        select(ApplicationModel.rejection_reason, func.count())
                        .where(
                            ApplicationModel.status == ApplicationStatus.REJECTED.value,
                            ApplicationModel.rejection_reason.is_not(None),
                        )
                        .group_by(ApplicationModel.rejection_reason)
                    )
                }
                unrecorded_rejection_reasons = (
                    session.scalar(
                        select(func.count())
                        .select_from(ApplicationModel)
                        .where(
                            ApplicationModel.status == ApplicationStatus.REJECTED.value,
                            ApplicationModel.rejection_reason.is_(None),
                        )
                    )
                    or 0
                )
                source_counts = _source_feedback_counts(session)
                resume_versions = _resume_version_feedback_counts(session)
        except OperationalError as error:
            raise _database_error(error) from error
        return build_feedback_summary(
            totals=totals,
            category_counts=category_counts,
            performance_counts=performance_counts,
            weak_counts=weak_counts,
            rejection_reason_counts=rejection_reason_counts,
            unrecorded_rejection_reasons=unrecorded_rejection_reasons,
            resume_versions=resume_versions,
            source_counts=source_counts,
        )


def _source_feedback_counts(session: Session) -> dict[str, FeedbackGroupStats]:
    rows = session.execute(
        select(
            JobModel.source,
            func.count(func.distinct(ApplicationModel.id)),
            func.count(
                func.distinct(
                    case(
                        (InterviewRoundModel.id.is_not(None), ApplicationModel.id),
                        else_=None,
                    )
                )
            ),
            func.count(
                func.distinct(
                    case(
                        (
                            ApplicationModel.status == ApplicationStatus.OFFER.value,
                            ApplicationModel.id,
                        ),
                        else_=None,
                    )
                )
            ),
        )
        .select_from(JobModel)
        .outerjoin(ApplicationModel, ApplicationModel.job_id == JobModel.id)
        .outerjoin(InterviewRoundModel, InterviewRoundModel.application_id == ApplicationModel.id)
        .group_by(JobModel.source)
    )
    return {
        source: FeedbackGroupStats(
            applications=applications,
            interview_applications=interview_applications,
            offers=offers,
        )
        for source, applications, interview_applications, offers in rows
    }


def _resume_version_feedback_counts(
    session: Session,
) -> tuple[ResumeVersionFeedbackStats, ...]:
    rows = session.execute(
        select(
            ResumeVersionModel.id,
            ResumeVersionModel.name,
            func.count(func.distinct(ApplicationModel.id)),
            func.count(
                func.distinct(
                    case(
                        (InterviewRoundModel.id.is_not(None), ApplicationModel.id),
                        else_=None,
                    )
                )
            ),
            func.count(
                func.distinct(
                    case(
                        (
                            ApplicationModel.status == ApplicationStatus.OFFER.value,
                            ApplicationModel.id,
                        ),
                        else_=None,
                    )
                )
            ),
        )
        .select_from(ResumeVersionModel)
        .outerjoin(
            ApplicationModel,
            ApplicationModel.resume_version_id == ResumeVersionModel.id,
        )
        .outerjoin(InterviewRoundModel, InterviewRoundModel.application_id == ApplicationModel.id)
        .group_by(ResumeVersionModel.id, ResumeVersionModel.name)
        .order_by(ResumeVersionModel.name, ResumeVersionModel.id)
    )
    return tuple(
        ResumeVersionFeedbackStats(
            resume_version_id=resume_version_id,
            resume_version_name=resume_version_name,
            applications=applications,
            interview_applications=interview_applications,
            offers=offers,
        )
        for resume_version_id, resume_version_name, applications, interview_applications, offers in rows
    )


def _count(session: Session, model: type[object]) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


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


def _round_draft_values(draft: InterviewRoundDraft) -> dict[str, object]:
    return {
        "round_name": draft.round_name,
        "interview_type": draft.interview_type.value,
        "scheduled_at": draft.scheduled_at,
        "status": draft.status.value,
        "interviewer_note": draft.interviewer_note,
        "went_well": draft.went_well,
        "could_improve": draft.could_improve,
        "learning_notes": draft.learning_notes,
        "other_notes": draft.other_notes,
    }


def _question_draft_values(draft: InterviewQuestionDraft) -> dict[str, object]:
    return {
        "question": draft.question,
        "category": draft.category.value,
        "answer_summary": draft.answer_summary,
        "performance": draft.performance.value,
        "note": draft.note,
    }


def _autofill_profile_draft_values(draft: AutofillProfileDraft) -> dict[str, str]:
    return {
        "personal_json": _canonical_json(
            {
                "name": draft.personal.name,
                "phone": draft.personal.phone,
                "email": draft.personal.email,
                "currentCity": draft.personal.current_city,
            }
        ),
        "education_json": _canonical_json(
            [
                {
                    "school": item.school,
                    "major": item.major,
                    "degree": item.degree,
                    "start": item.start,
                    "end": item.end,
                }
                for item in draft.education
            ]
        ),
        "experience_json": _canonical_json(
            [
                {
                    "company": item.company,
                    "position": item.position,
                    "start": item.start,
                    "end": item.end,
                    "description": item.description,
                }
                for item in draft.experience
            ]
        ),
        "projects_json": _canonical_json(
            [
                {
                    "name": item.name,
                    "role": item.role,
                    "start": item.start,
                    "end": item.end,
                    "description": item.description,
                }
                for item in draft.projects
            ]
        ),
        "links_json": _canonical_json(
            {
                "github": draft.links.github,
                "portfolio": draft.links.portfolio,
                "homepage": draft.links.homepage,
            }
        ),
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


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
        resume_version_id=model.resume_version_id,
        outcome_note=model.outcome_note,
        rejection_reason=(
            RejectionReason(model.rejection_reason) if model.rejection_reason is not None else None
        ),
        applied_at=_utc(model.applied_at) if model.applied_at else None,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _interview_round(model: InterviewRoundModel) -> InterviewRound:
    return InterviewRound(
        id=model.id,
        application_id=model.application_id,
        round_name=model.round_name,
        interview_type=InterviewType(model.interview_type),
        scheduled_at=_utc(model.scheduled_at) if model.scheduled_at else None,
        status=InterviewStatus(model.status),
        interviewer_note=model.interviewer_note,
        went_well=model.went_well,
        could_improve=model.could_improve,
        learning_notes=model.learning_notes,
        other_notes=model.other_notes,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _interview_question(model: InterviewQuestionModel) -> InterviewQuestion:
    return InterviewQuestion(
        id=model.id,
        interview_round_id=model.interview_round_id,
        question=model.question,
        category=QuestionCategory(model.category),
        answer_summary=model.answer_summary,
        performance=QuestionPerformance(model.performance),
        note=model.note,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _resume_version(model: ResumeVersionModel, *, application_count: int) -> ResumeVersion:
    return ResumeVersion(
        id=model.id,
        name=model.name,
        content=model.content,
        application_count=application_count,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _autofill_profile(model: AutofillProfileModel) -> AutofillProfile:
    draft = AutofillProfileDraft.create(
        personal=json.loads(model.personal_json),
        education=json.loads(model.education_json),
        experience=json.loads(model.experience_json),
        projects=json.loads(model.projects_json),
        links=json.loads(model.links_json),
    )
    return AutofillProfile(
        personal=draft.personal,
        education=draft.education,
        experience=draft.experience,
        projects=draft.projects,
        links=draft.links,
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


def _evidence_map_record(model: EvidenceMapRecordModel) -> EvidenceMapRecord:
    return EvidenceMapRecord(
        id=model.id,
        job_id=model.job_id,
        resume_version_id=model.resume_version_id,
        schema_version=model.schema_version,
        result=evidence_map_from_stored_json(
            model.result_json,
            schema_version=model.schema_version,
        ),
        job_analysis_fingerprint=model.job_analysis_fingerprint,
        resume_content_fingerprint=model.resume_content_fingerprint,
        created_at=_utc(model.created_at),
        updated_at=_utc(model.updated_at),
    )


def _copilot_record(model: CopilotRecordModel) -> CopilotRecord:
    kind = CopilotKind(model.kind)
    return CopilotRecord(
        id=model.id,
        job_id=model.job_id,
        resume_version_id=model.resume_version_id,
        kind=kind,
        schema_version=model.schema_version,
        result=copilot_result_from_stored_json(kind, model.result_json),
        input_fingerprint=model.input_fingerprint,
        model=model.model,
        prompt_version=model.prompt_version,
        created_at=_utc(model.created_at),
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _database_error(error: OperationalError) -> DatabaseBusyError:
    message = str(error.orig).lower()
    if "locked" in message or "busy" in message:
        return DatabaseBusyError("本地数据库暂时繁忙，请稍后重试")
    raise error
