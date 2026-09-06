from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from jobpilot_api.domain.errors import DomainValidationError, InvalidTransitionError
from jobpilot_api.domain.jobs import CONTROL_CHARACTER_TRANSLATION

MAX_OUTCOME_NOTE_LENGTH = 20_000


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


class RejectionReason(StrEnum):
    TECHNICAL = "TECHNICAL"
    EXPERIENCE = "EXPERIENCE"
    PRODUCT = "PRODUCT"
    BUSINESS = "BUSINESS"
    COMMUNICATION = "COMMUNICATION"
    ROLE_FIT = "ROLE_FIT"
    HEADCOUNT = "HEADCOUNT"
    UNKNOWN = "UNKNOWN"
    OTHER = "OTHER"


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
    outcome_note: str | None
    rejection_reason: RejectionReason | None
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


def normalize_application_outcome(
    *,
    status: ApplicationStatus,
    outcome_note: str | None,
    rejection_reason: RejectionReason | None,
) -> tuple[str | None, RejectionReason | None]:
    if rejection_reason is not None and status is not ApplicationStatus.REJECTED:
        raise DomainValidationError("rejectionReason: requires rejected application status")
    return _optional_plain_text(
        "outcomeNote", outcome_note, MAX_OUTCOME_NOTE_LENGTH
    ), rejection_reason


def _optional_plain_text(field: str, value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainValidationError(f"{field}: must be text")
    cleaned = (
        value.replace("\r\n", "\n")
        .replace("\r", "\n")
        .translate(CONTROL_CHARACTER_TRANSLATION)
        .strip()
    )
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise DomainValidationError(f"{field}: must be at most {maximum} characters")
    return cleaned
