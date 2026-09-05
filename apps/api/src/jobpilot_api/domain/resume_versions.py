from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from jobpilot_api.domain.errors import DomainValidationError
from jobpilot_api.domain.jobs import CONTROL_CHARACTER_TRANSLATION

MAX_RESUME_NAME_LENGTH = 200
MAX_RESUME_CONTENT_LENGTH = 100_000


@dataclass(frozen=True, slots=True)
class ResumeVersionDraft:
    name: str
    content: str

    @classmethod
    def create(cls, *, name: str, content: str) -> ResumeVersionDraft:
        return cls(
            name=_required_plain_text("name", name, MAX_RESUME_NAME_LENGTH),
            content=_required_plain_text("content", content, MAX_RESUME_CONTENT_LENGTH),
        )


@dataclass(frozen=True, slots=True)
class ResumeVersion:
    id: str
    name: str
    content: str
    application_count: int
    created_at: datetime
    updated_at: datetime


def _required_plain_text(field: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise DomainValidationError(f"{field}: must be text")
    cleaned = (
        value.replace("\r\n", "\n")
        .replace("\r", "\n")
        .translate(CONTROL_CHARACTER_TRANSLATION)
        .strip()
    )
    if not cleaned:
        raise DomainValidationError(f"{field}: must not be blank")
    if len(cleaned) > maximum:
        raise DomainValidationError(f"{field}: must be at most {maximum} characters")
    return cleaned
