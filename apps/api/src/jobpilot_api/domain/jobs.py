from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

from jobpilot_api.domain.errors import DomainValidationError

MAX_TITLE_LENGTH = 200
MAX_COMPANY_LENGTH = 200
MAX_SHORT_TEXT_LENGTH = 300
MAX_URL_LENGTH = 2_048
MAX_DESCRIPTION_LENGTH = 100_000
MAX_NOTES_LENGTH = 20_000


@dataclass(frozen=True, slots=True)
class JobDraft:
    title: str
    company: str
    location: str | None
    salary_text: str | None
    source: str
    source_url: str | None
    normalized_source_url: str | None
    description: str | None
    notes: str | None

    @classmethod
    def create(
        cls,
        *,
        title: str,
        company: str,
        location: str | None = None,
        salary_text: str | None = None,
        source: str = "manual",
        source_url: str | None = None,
        description: str | None = None,
        notes: str | None = None,
    ) -> JobDraft:
        clean_title = _required_text("title", title, MAX_TITLE_LENGTH)
        clean_company = _required_text("company", company, MAX_COMPANY_LENGTH)
        if source != "manual":
            raise DomainValidationError("source: Phase 3 only accepts manual jobs")
        clean_url = _optional_text("sourceUrl", source_url, MAX_URL_LENGTH)
        return cls(
            title=clean_title,
            company=clean_company,
            location=_optional_text("location", location, MAX_SHORT_TEXT_LENGTH),
            salary_text=_optional_text("salaryText", salary_text, MAX_SHORT_TEXT_LENGTH),
            source=source,
            source_url=clean_url,
            normalized_source_url=normalize_source_url(clean_url),
            description=_optional_text("description", description, MAX_DESCRIPTION_LENGTH),
            notes=_optional_text("notes", notes, MAX_NOTES_LENGTH),
        )


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    title: str
    company: str
    location: str | None
    salary_text: str | None
    source: str
    source_url: str | None
    normalized_source_url: str | None
    description: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


def normalize_source_url(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise DomainValidationError("sourceUrl: must be a valid HTTP or HTTPS URL") from None
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise DomainValidationError("sourceUrl: must be an HTTP or HTTPS URL without credentials")
    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    include_port = port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    )
    netloc = f"{hostname}:{port}" if include_port else hostname
    return urlunsplit((scheme, netloc, parsed.path, parsed.query, ""))


def _required_text(field: str, value: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise DomainValidationError(f"{field}: must be text")
    cleaned = value.strip()
    if not cleaned:
        raise DomainValidationError(f"{field}: must not be blank")
    if len(cleaned) > maximum:
        raise DomainValidationError(f"{field}: must be at most {maximum} characters")
    return cleaned


def _optional_text(field: str, value: str | None, maximum: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise DomainValidationError(f"{field}: must be at most {maximum} characters")
    return cleaned
