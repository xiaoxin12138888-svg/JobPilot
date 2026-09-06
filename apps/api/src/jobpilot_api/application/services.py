from __future__ import annotations

from jobpilot_api.application.repositories import (
    ApplicationListEntry,
    ApplicationRepository,
    FeedbackSummaryRepository,
    InterviewRepository,
    JobListEntry,
    JobRepository,
    ResumeVersionRepository,
)
from jobpilot_api.domain.applications import (
    Application,
    ApplicationStatus,
    RejectionReason,
    normalize_application_outcome,
    validate_status_transition,
)
from jobpilot_api.domain.errors import ResourceNotFoundError
from jobpilot_api.domain.feedback import FeedbackSummary
from jobpilot_api.domain.interviews import (
    InterviewQuestion,
    InterviewQuestionDraft,
    InterviewRoundDetail,
    InterviewRoundDraft,
)
from jobpilot_api.domain.jobs import Job, JobDraft
from jobpilot_api.domain.resume_versions import ResumeVersion, ResumeVersionDraft


class JobService:
    def __init__(self, repository: JobRepository) -> None:
        self._repository = repository

    def create(self, draft: JobDraft) -> Job:
        return self._repository.create(draft)

    def get(self, job_id: str) -> Job:
        job = self._repository.get(job_id)
        if job is None:
            raise ResourceNotFoundError("岗位不存在")
        return job

    def update(self, job_id: str, changes: dict[str, object]) -> Job:
        current = self.get(job_id)
        values: dict[str, object] = {
            "title": current.title,
            "company": current.company,
            "location": current.location,
            "salary_text": current.salary_text,
            "source": current.source,
            "source_url": current.source_url,
            "description": current.description,
            "notes": current.notes,
        }
        values.update(changes)
        draft = JobDraft.create(**values)  # type: ignore[arg-type]
        updated = self._repository.update(job_id, draft)
        if updated is None:
            raise ResourceNotFoundError("岗位不存在")
        return updated

    def delete(self, job_id: str) -> None:
        if not self._repository.delete(job_id):
            raise ResourceNotFoundError("岗位不存在")

    def list(
        self,
        *,
        keyword: str | None,
        source: str | None,
        application_status: ApplicationStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[JobListEntry], int]:
        return self._repository.list(
            keyword=keyword.strip() if keyword and keyword.strip() else None,
            source=source,
            application_status=application_status,
            limit=limit,
            offset=offset,
        )


class ApplicationService:
    def __init__(
        self,
        repository: ApplicationRepository,
        jobs: JobRepository,
        resumes: ResumeVersionRepository,
    ) -> None:
        self._repository = repository
        self._jobs = jobs
        self._resumes = resumes

    def create(self, job_id: str) -> Application:
        if self._jobs.get(job_id) is None:
            raise ResourceNotFoundError("岗位不存在")
        return self._repository.create(job_id)

    def get(self, application_id: str) -> Application:
        application = self._repository.get(application_id)
        if application is None:
            raise ResourceNotFoundError("投递记录不存在")
        return application

    def change_status(
        self,
        application_id: str,
        status: ApplicationStatus,
        *,
        confirm_applied: bool,
    ) -> Application:
        return self.update(
            application_id,
            status=status,
            confirm_applied=confirm_applied,
            resume_version_id=None,
            update_resume_version=False,
            outcome_note=None,
            update_outcome_note=False,
            rejection_reason=None,
            update_rejection_reason=False,
        )

    def update(
        self,
        application_id: str,
        *,
        status: ApplicationStatus | None,
        confirm_applied: bool,
        resume_version_id: str | None,
        update_resume_version: bool,
        outcome_note: str | None,
        update_outcome_note: bool,
        rejection_reason: RejectionReason | None,
        update_rejection_reason: bool,
    ) -> Application:
        current = self.get(application_id)
        if status is not None:
            validate_status_transition(current.status, status, confirm_applied=confirm_applied)
        if (
            update_resume_version
            and resume_version_id is not None
            and self._resumes.get(resume_version_id) is None
        ):
            raise ResourceNotFoundError("简历版本不存在")
        target_status = status or current.status
        target_outcome_note = outcome_note if update_outcome_note else current.outcome_note
        if update_rejection_reason:
            target_rejection_reason = rejection_reason
        elif target_status is ApplicationStatus.REJECTED:
            target_rejection_reason = current.rejection_reason
        else:
            target_rejection_reason = None
        target_outcome_note, target_rejection_reason = normalize_application_outcome(
            status=target_status,
            outcome_note=target_outcome_note,
            rejection_reason=target_rejection_reason,
        )
        updated = self._repository.update(
            application_id,
            status=status,
            resume_version_id=resume_version_id,
            update_resume_version=update_resume_version,
            outcome_note=target_outcome_note,
            update_outcome_note=update_outcome_note,
            rejection_reason=target_rejection_reason,
            update_rejection_reason=(
                update_rejection_reason or target_rejection_reason != current.rejection_reason
            ),
        )
        if updated is None:
            raise ResourceNotFoundError("投递记录不存在")
        return updated

    def list(
        self,
        *,
        job_id: str | None,
        status: ApplicationStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[ApplicationListEntry], int]:
        return self._repository.list(job_id=job_id, status=status, limit=limit, offset=offset)


class ResumeVersionService:
    def __init__(self, repository: ResumeVersionRepository) -> None:
        self._repository = repository

    def create(self, draft: ResumeVersionDraft) -> ResumeVersion:
        return self._repository.create(draft)

    def get(self, resume_version_id: str) -> ResumeVersion:
        resume = self._repository.get(resume_version_id)
        if resume is None:
            raise ResourceNotFoundError("简历版本不存在")
        return resume

    def update(self, resume_version_id: str, changes: dict[str, object]) -> ResumeVersion:
        current = self.get(resume_version_id)
        draft = ResumeVersionDraft.create(
            name=changes.get("name", current.name),  # type: ignore[arg-type]
            content=changes.get("content", current.content),  # type: ignore[arg-type]
        )
        updated = self._repository.update(resume_version_id, draft)
        if updated is None:
            raise ResourceNotFoundError("简历版本不存在")
        return updated

    def duplicate(self, resume_version_id: str, *, name: str) -> ResumeVersion:
        current = self.get(resume_version_id)
        return self.create(ResumeVersionDraft.create(name=name, content=current.content))

    def delete(self, resume_version_id: str) -> None:
        if not self._repository.delete(resume_version_id):
            raise ResourceNotFoundError("简历版本不存在")

    def list(self, *, limit: int, offset: int) -> tuple[list[ResumeVersion], int]:
        return self._repository.list(limit=limit, offset=offset)


class InterviewService:
    def __init__(
        self,
        repository: InterviewRepository,
        applications: ApplicationRepository,
    ) -> None:
        self._repository = repository
        self._applications = applications

    def create_round(self, application_id: str, draft: InterviewRoundDraft) -> InterviewRoundDetail:
        if self._applications.get(application_id) is None:
            raise ResourceNotFoundError("投递记录不存在")
        interview = self._repository.create_round(application_id, draft)
        return InterviewRoundDetail(interview=interview, questions=())

    def get_round(self, interview_id: str) -> InterviewRoundDetail:
        detail = self._repository.get_round(interview_id)
        if detail is None:
            raise ResourceNotFoundError("面试记录不存在")
        return detail

    def update_round(self, interview_id: str, changes: dict[str, object]) -> InterviewRoundDetail:
        current = self.get_round(interview_id).interview
        values: dict[str, object] = {
            "round_name": current.round_name,
            "interview_type": current.interview_type,
            "scheduled_at": current.scheduled_at,
            "status": current.status,
            "interviewer_note": current.interviewer_note,
            "went_well": current.went_well,
            "could_improve": current.could_improve,
            "learning_notes": current.learning_notes,
            "other_notes": current.other_notes,
        }
        values.update(changes)
        draft = InterviewRoundDraft.create(**values)  # type: ignore[arg-type]
        updated = self._repository.update_round(interview_id, draft)
        if updated is None:
            raise ResourceNotFoundError("面试记录不存在")
        return updated

    def delete_round(self, interview_id: str) -> None:
        if not self._repository.delete_round(interview_id):
            raise ResourceNotFoundError("面试记录不存在")

    def list_rounds(
        self, *, application_id: str, limit: int, offset: int
    ) -> tuple[list[InterviewRoundDetail], int]:
        if self._applications.get(application_id) is None:
            raise ResourceNotFoundError("投递记录不存在")
        return self._repository.list_rounds(
            application_id=application_id, limit=limit, offset=offset
        )

    def create_question(
        self, interview_id: str, draft: InterviewQuestionDraft
    ) -> InterviewQuestion:
        self.get_round(interview_id)
        return self._repository.create_question(interview_id, draft)

    def update_question(self, question_id: str, changes: dict[str, object]) -> InterviewQuestion:
        current = self._repository.get_question(question_id)
        if current is None:
            raise ResourceNotFoundError("面试题记录不存在")
        values: dict[str, object] = {
            "question": current.question,
            "category": current.category,
            "answer_summary": current.answer_summary,
            "performance": current.performance,
            "note": current.note,
        }
        values.update(changes)
        draft = InterviewQuestionDraft.create(**values)  # type: ignore[arg-type]
        updated = self._repository.update_question(question_id, draft)
        if updated is None:
            raise ResourceNotFoundError("面试题记录不存在")
        return updated

    def delete_question(self, question_id: str) -> None:
        if not self._repository.delete_question(question_id):
            raise ResourceNotFoundError("面试题记录不存在")


class FeedbackSummaryService:
    def __init__(self, repository: FeedbackSummaryRepository) -> None:
        self._repository = repository

    def get(self) -> FeedbackSummary:
        return self._repository.get_summary()
