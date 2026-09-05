from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from jobpilot_api.domain.errors import DomainValidationError, InvalidTransitionError


class ApplicationStatus(StrEnum):
    PLANNED = "planned"
    APPLIED = "applied"
    SCREENING = "screening"
    ASSESSMENT = "assessment"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"


ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.PLANNED: frozenset(
        {ApplicationStatus.APPLIED, ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED}
    ),
    ApplicationStatus.APPLIED: frozenset(
        {
            ApplicationStatus.PLANNED,
            ApplicationStatus.SCREENING,
            ApplicationStatus.ASSESSMENT,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.CLOSED,
        }
    ),
    ApplicationStatus.SCREENING: frozenset(
        {
            ApplicationStatus.APPLIED,
            ApplicationStatus.ASSESSMENT,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.CLOSED,
        }
    ),
    ApplicationStatus.ASSESSMENT: frozenset(
        {
            ApplicationStatus.SCREENING,
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.CLOSED,
        }
    ),
    ApplicationStatus.INTERVIEWING: frozenset(
        {
            ApplicationStatus.ASSESSMENT,
            ApplicationStatus.OFFER,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
            ApplicationStatus.CLOSED,
        }
    ),
    ApplicationStatus.OFFER: frozenset({ApplicationStatus.INTERVIEWING, ApplicationStatus.CLOSED}),
    ApplicationStatus.REJECTED: frozenset(
        {ApplicationStatus.INTERVIEWING, ApplicationStatus.CLOSED}
    ),
    ApplicationStatus.WITHDRAWN: frozenset({ApplicationStatus.APPLIED, ApplicationStatus.CLOSED}),
    ApplicationStatus.CLOSED: frozenset(
        {ApplicationStatus.OFFER, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
    ),
}


@dataclass(frozen=True, slots=True)
class Application:
    id: str
    job_id: str
    status: ApplicationStatus
    resume_version_id: str | None
    applied_at: datetime | None
    created_at: datetime
    updated_at: datetime


def validate_status_transition(
    current: ApplicationStatus,
    target: ApplicationStatus,
    *,
    confirm_applied: bool,
) -> None:
    if current == target:
        return
    if target == ApplicationStatus.APPLIED and not confirm_applied:
        raise DomainValidationError("进入已投递状态前必须明确确认已完成投递")
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransitionError(f"不能从 {current.value} 直接变更为 {target.value}")
