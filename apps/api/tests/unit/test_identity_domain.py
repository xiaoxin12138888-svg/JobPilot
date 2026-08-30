from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from jobpilot_api.domain.identity import AuthenticatedUser, SessionKind


def test_authenticated_user_is_an_immutable_provider_neutral_context() -> None:
    user_id = uuid4()

    authenticated_user = AuthenticatedUser(
        user_id=user_id,
        identity_issuer="https://tenant.example.invalid/",
        identity_subject="auth0|CaseSensitiveSubject",
        session_kind=SessionKind.EXTENSION,
        session_id=None,
    )

    assert authenticated_user.user_id == user_id
    assert authenticated_user.identity_issuer == "https://tenant.example.invalid/"
    assert authenticated_user.identity_subject == "auth0|CaseSensitiveSubject"
    assert authenticated_user.session_kind is SessionKind.EXTENSION
    assert authenticated_user.session_id is None
    with pytest.raises(FrozenInstanceError):
        authenticated_user.user_id = uuid4()  # type: ignore[misc]


@pytest.mark.parametrize("field_name", ["identity_issuer", "identity_subject"])
def test_authenticated_user_rejects_empty_identity_keys(field_name: str) -> None:
    values = {
        "user_id": uuid4(),
        "identity_issuer": "https://tenant.example.invalid/",
        "identity_subject": "auth0|subject",
        "session_kind": SessionKind.EXTENSION,
        "session_id": None,
    }
    values[field_name] = " "

    with pytest.raises(ValueError, match=field_name):
        AuthenticatedUser(**values)
