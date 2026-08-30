from __future__ import annotations

import traceback

import pytest
from sqlalchemy.exc import SQLAlchemyError

from jobpilot_api.application.identity_service import IdentityPersistenceError
from jobpilot_api.infrastructure.database.identity_repository import (
    SqlAlchemyIdentityUnitOfWork,
)


class CleanupSession:
    def __init__(self, failing_operation: str, sensitive_value: str) -> None:
        self._failing_operation = failing_operation
        self._sensitive_value = sensitive_value
        self.rollback_called = False
        self.close_called = False

    def rollback(self) -> None:
        self.rollback_called = True
        if self._failing_operation == "rollback":
            raise SQLAlchemyError(f"rollback leaked {self._sensitive_value}")

    def close(self) -> None:
        self.close_called = True
        if self._failing_operation == "close":
            raise SQLAlchemyError(f"close leaked {self._sensitive_value}")


@pytest.mark.parametrize("failing_operation", ["rollback", "close"])
def test_cleanup_failure_is_sanitized_and_close_is_always_attempted(
    failing_operation: str,
) -> None:
    sensitive_value = "private-identity@example.com"
    session = CleanupSession(failing_operation, sensitive_value)
    unit_of_work = object.__new__(SqlAlchemyIdentityUnitOfWork)
    unit_of_work._session = session  # type: ignore[assignment]

    with pytest.raises(IdentityPersistenceError) as captured:
        unit_of_work.__exit__(RuntimeError, RuntimeError("operation failed"), None)

    assert session.rollback_called
    assert session.close_called
    assert sensitive_value not in "".join(traceback.format_exception(captured.value))
