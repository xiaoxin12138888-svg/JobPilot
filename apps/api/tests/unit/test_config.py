from __future__ import annotations

import pytest

from jobpilot_api.config import ApiSettings, AuthSettings


def _auth_environment() -> dict[str, str]:
    return {
        "JOBPILOT_ENVIRONMENT": "test",
        "JOBPILOT_AUTH_ISSUER": "https://tenant.example.invalid/",
        "JOBPILOT_AUTH_JWKS_URL": "https://tenant.example.invalid/.well-known/jwks.json",
        "JOBPILOT_AUTH_TOKEN_URL": "https://tenant.example.invalid/oauth/token",
        "JOBPILOT_AUTH_AUDIENCE": "https://api.jobpilot.example.invalid",
        "JOBPILOT_AUTH_EXTENSION_CLIENT_ID": "extension-client-id",
        "JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_CLAIM": ("https://jobpilot.example.invalid/claims/email"),
        "JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_VERIFIED_CLAIM": (
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
        "JOBPILOT_AUTH_CLOCK_SKEW_SECONDS": "45",
        "JOBPILOT_AUTH_JWKS_CACHE_SECONDS": "240",
        "JOBPILOT_AUTH_JWKS_TIMEOUT_SECONDS": "4.5",
    }


def test_api_settings_loads_typed_bearer_auth_configuration() -> None:
    settings = ApiSettings.from_environment(_auth_environment())

    assert settings.auth == AuthSettings(
        issuer="https://tenant.example.invalid/",
        jwks_url="https://tenant.example.invalid/.well-known/jwks.json",
        token_url="https://tenant.example.invalid/oauth/token",
        audience="https://api.jobpilot.example.invalid",
        extension_client_id="extension-client-id",
        access_token_email_claim="https://jobpilot.example.invalid/claims/email",
        access_token_email_verified_claim=(
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
        clock_skew_seconds=45,
        jwks_cache_seconds=240,
        jwks_timeout_seconds=4.5,
    )


def test_api_settings_without_auth_environment_keeps_auth_disabled() -> None:
    settings = ApiSettings.from_environment({"JOBPILOT_ENVIRONMENT": "development"})

    assert settings.auth is None


def test_partial_auth_environment_fails_closed() -> None:
    with pytest.raises(ValueError, match="Incomplete authentication configuration"):
        ApiSettings.from_environment(
            {
                "JOBPILOT_ENVIRONMENT": "test",
                "JOBPILOT_AUTH_ISSUER": "https://tenant.example.invalid/",
            }
        )


def test_non_numeric_auth_timing_environment_fails_with_a_stable_config_error() -> None:
    environment = _auth_environment()
    environment["JOBPILOT_AUTH_JWKS_TIMEOUT_SECONDS"] = "not-a-number"

    with pytest.raises(ValueError, match="Authentication timing configuration must be numeric"):
        ApiSettings.from_environment(environment)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("issuer", "http://tenant.example.invalid/"),
        ("issuer", "https://tenant.example.invalid:0/"),
        ("jwks_url", "https://user@tenant.example.invalid/jwks.json"),
        ("access_token_email_claim", "email"),
        ("access_token_email_verified_claim", "https://claims.example.invalid/value#part"),
    ],
)
def test_auth_urls_and_claim_names_require_fixed_clean_https_urls(
    field_name: str,
    invalid_value: str,
) -> None:
    values = {
        "issuer": "https://tenant.example.invalid/",
        "jwks_url": "https://tenant.example.invalid/.well-known/jwks.json",
        "token_url": "https://tenant.example.invalid/oauth/token",
        "audience": "https://api.jobpilot.example.invalid",
        "extension_client_id": "extension-client-id",
        "access_token_email_claim": "https://jobpilot.example.invalid/claims/email",
        "access_token_email_verified_claim": (
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        AuthSettings(**values)


def test_email_claim_names_must_be_distinct() -> None:
    claim_name = "https://jobpilot.example.invalid/claims/email"

    with pytest.raises(ValueError, match="must be distinct"):
        AuthSettings(
            issuer="https://tenant.example.invalid/",
            jwks_url="https://tenant.example.invalid/.well-known/jwks.json",
            token_url="https://tenant.example.invalid/oauth/token",
            audience="https://api.jobpilot.example.invalid",
            extension_client_id="extension-client-id",
            access_token_email_claim=claim_name,
            access_token_email_verified_claim=claim_name,
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("clock_skew_seconds", -1),
        ("clock_skew_seconds", 301),
        ("clock_skew_seconds", True),
        ("jwks_cache_seconds", 0),
        ("jwks_cache_seconds", 3601),
        ("jwks_cache_seconds", 1.5),
        ("jwks_timeout_seconds", 0),
        ("jwks_timeout_seconds", 31),
        ("jwks_timeout_seconds", True),
    ],
)
def test_auth_timing_controls_are_bounded(field_name: str, invalid_value: object) -> None:
    values = {
        "issuer": "https://tenant.example.invalid/",
        "jwks_url": "https://tenant.example.invalid/.well-known/jwks.json",
        "token_url": "https://tenant.example.invalid/oauth/token",
        "audience": "https://api.jobpilot.example.invalid",
        "extension_client_id": "extension-client-id",
        "access_token_email_claim": "https://jobpilot.example.invalid/claims/email",
        "access_token_email_verified_claim": (
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
        field_name: invalid_value,
    }

    with pytest.raises(ValueError, match=field_name):
        AuthSettings(**values)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("issuer", "https://tenant.example.invalid"),
        ("jwks_url", "https://keys.example.invalid/jwks.json"),
        ("token_url", "https://tokens.example.invalid/oauth/token"),
    ],
)
def test_provider_urls_require_a_canonical_issuer_and_one_origin(
    field_name: str,
    invalid_value: str,
) -> None:
    values = {
        "issuer": "https://tenant.example.invalid/",
        "jwks_url": "https://tenant.example.invalid/.well-known/jwks.json",
        "token_url": "https://tenant.example.invalid/oauth/token",
        "audience": "https://api.jobpilot.example.invalid",
        "extension_client_id": "extension-client-id",
        "access_token_email_claim": "https://jobpilot.example.invalid/claims/email",
        "access_token_email_verified_claim": (
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
    }
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        AuthSettings(**values)
