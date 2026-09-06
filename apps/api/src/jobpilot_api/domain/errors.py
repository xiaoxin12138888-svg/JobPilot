from __future__ import annotations

from enum import StrEnum


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 422

    def __init__(self, message: str, *, resource_id: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.resource_id = resource_id


class DomainValidationError(DomainError):
    code = "VALIDATION_ERROR"


class InvalidTransitionError(DomainError):
    code = "INVALID_APPLICATION_TRANSITION"


class ResourceNotFoundError(DomainError):
    code = "RESOURCE_NOT_FOUND"
    status_code = 404


class DuplicateJobError(DomainError):
    code = "DUPLICATE_JOB_URL"
    status_code = 409


class ApplicationAlreadyExistsError(DomainError):
    code = "APPLICATION_ALREADY_EXISTS"
    status_code = 409


class ResumeVersionInUseError(DomainError):
    code = "RESUME_VERSION_IN_USE"
    status_code = 409


class DatabaseBusyError(DomainError):
    code = "DATABASE_BUSY"
    status_code = 503


class AnalysisNotConfiguredError(DomainError):
    code = "AI_NOT_CONFIGURED"
    status_code = 503


class AnalysisProviderUnavailableError(DomainError):
    code = "AI_PROVIDER_UNAVAILABLE"
    status_code = 503


class AnalysisInvalidResponseDiagnostic(StrEnum):
    INVALID_JSON = "INVALID_JSON"
    PROVIDER_ENVELOPE = "PROVIDER_ENVELOPE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    REQUIREMENT_MISMATCH = "REQUIREMENT_MISMATCH"
    EVIDENCE_LIMIT_EXCEEDED = "EVIDENCE_LIMIT_EXCEEDED"


class AnalysisInvalidResponseError(DomainError):
    code = "AI_INVALID_RESPONSE"
    status_code = 502

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: AnalysisInvalidResponseDiagnostic = (
            AnalysisInvalidResponseDiagnostic.SCHEMA_MISMATCH
        ),
    ) -> None:
        super().__init__(message)
        self.diagnostic_code = diagnostic_code.value


class JDAnalysisRequiredError(DomainError):
    code = "JD_ANALYSIS_REQUIRED"


class JDAnalysisStaleError(DomainError):
    code = "JD_ANALYSIS_STALE"
