from __future__ import annotations


class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 422

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


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


class DatabaseBusyError(DomainError):
    code = "DATABASE_BUSY"
    status_code = 503
