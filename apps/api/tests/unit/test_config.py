from __future__ import annotations

import pytest

from jobpilot_api.config import ApiSettings, AuthSettings


def _auth_environment() -> dict[str, str]:
    return {
        "JOBPILOT_ENVIRONMENT": "test",
        "JOBPILOT_DATABASE_URL": (
            "postgresql+psycopg://jobpilot:database-secret@localhost:5432/jobpilot_test"
        ),
        "JOBPILOT_AUTH_ISSUER": "https://tenant.example.invalid/",
        "JOBPILOT_AUTH_JWKS_URL": "https://tenant.example.invalid/.well-known/jwks.json",
        "JOBPILOT_AUTH_AUTHORIZE_URL": "https://tenant.example.invalid/authorize",
        "JOBPILOT_AUTH_TOKEN_URL": "https://tenant.example.invalid/oauth/token",
        "JOBPILOT_AUTH_AUDIENCE": "https://api.jobpilot.example.invalid",
        "JOBPILOT_AUTH_EXTENSION_CLIENT_ID": "extension-client-id",
        "JOBPILOT_AUTH_WEB_CLIENT_ID": "web-client-id",
        "JOBPILOT_AUTH_WEB_CLIENT_SECRET": "web-client-secret",
        "JOBPILOT_WEB_ORIGIN": "https://jobpilot.example.invalid",
        "JOBPILOT_WEB_CALLBACK_URL": ("https://jobpilot.example.invalid/api/v1/auth/web/callback"),
        "JOBPILOT_WEB_SESSION_IDLE_SECONDS": "604800",
        "JOBPILOT_WEB_SESSION_ABSOLUTE_SECONDS": "2592000",
        "JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_CLAIM": ("https://jobpilot.example.invalid/claims/email"),
        "JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_VERIFIED_CLAIM": (
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
        "JOBPILOT_AUTH_CLOCK_SKEW_SECONDS": "45",
        "JOBPILOT_AUTH_JWKS_CACHE_SECONDS": "240",
        "JOBPILOT_AUTH_JWKS_TIMEOUT_SECONDS": "4.5",
    }


def _auth_values(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "issuer": "https://tenant.example.invalid/",
        "jwks_url": "https://tenant.example.invalid/.well-known/jwks.json",
        "authorize_url": "https://tenant.example.invalid/authorize",
        "token_url": "https://tenant.example.invalid/oauth/token",
        "audience": "https://api.jobpilot.example.invalid",
        "extension_client_id": "extension-client-id",
        "web_client_id": "web-client-id",
        "web_client_secret": "web-client-secret",
        "web_origin": "https://jobpilot.example.invalid",
        "web_callback_url": "https://jobpilot.example.invalid/api/v1/auth/web/callback",
        "access_token_email_claim": "https://jobpilot.example.invalid/claims/email",
        "access_token_email_verified_claim": (
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
    }
    values.update(overrides)
    return values


def test_api_settings_loads_typed_bearer_auth_configuration() -> None:
    settings = ApiSettings.from_environment(_auth_environment())

    assert settings.auth == AuthSettings(
        issuer="https://tenant.example.invalid/",
        jwks_url="https://tenant.example.invalid/.well-known/jwks.json",
        authorize_url="https://tenant.example.invalid/authorize",
        token_url="https://tenant.example.invalid/oauth/token",
        audience="https://api.jobpilot.example.invalid",
        extension_client_id="extension-client-id",
        web_client_id="web-client-id",
        web_client_secret="web-client-secret",
        web_origin="https://jobpilot.example.invalid",
        web_callback_url="https://jobpilot.example.invalid/api/v1/auth/web/callback",
        access_token_email_claim="https://jobpilot.example.invalid/claims/email",
        access_token_email_verified_claim=(
            "https://jobpilot.example.invalid/claims/email_verified"
        ),
        clock_skew_seconds=45,
        jwks_cache_seconds=240,
        jwks_timeout_seconds=4.5,
        web_session_idle_seconds=604800,
        web_session_absolute_seconds=2592000,
    )
    assert settings.database_url == (
        "postgresql+psycopg://jobpilot:database-secret@localhost:5432/jobpilot_test"
    )
    assert "database-secret" not in repr(settings)
    assert "web-client-secret" not in repr(settings)


def test_api_settings_without_auth_environment_keeps_auth_disabled() -> None:
    settings = ApiSettings.from_environment({"JOBPILOT_ENVIRONMENT": "development"})

    assert settings.auth is None
    assert settings.database_url is None


def test_database_url_must_be_an_exact_nonempty_value_when_provided() -> None:
    with pytest.raises(ValueError, match="database_url"):
        ApiSettings(environment="test", cors_origins=(), database_url=" postgresql://db ")


def test_partial_auth_environment_fails_closed() -> None:
    with pytest.raises(ValueError, match="Incomplete authentication configuration"):
        ApiSettings.from_environment(
            {
                "JOBPILOT_ENVIRONMENT": "test",
                "JOBPILOT_AUTH_ISSUER": "https://tenant.example.invalid/",
            }
        )


def test_web_client_secret_is_required_exact_and_never_rendered() -> None:
    environment = _auth_environment()
    environment["JOBPILOT_AUTH_WEB_CLIENT_SECRET"] = " private-secret "

    with pytest.raises(ValueError, match="web_client_secret") as captured:
        ApiSettings.from_environment(environment)

    assert "private-secret" not in str(captured.value)

    del environment["JOBPILOT_AUTH_WEB_CLIENT_SECRET"]
    with pytest.raises(ValueError, match="Incomplete authentication configuration"):
        ApiSettings.from_environment(environment)


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
        ("authorize_url", "http://tenant.example.invalid/authorize"),
        ("access_token_email_claim", "email"),
        ("access_token_email_verified_claim", "https://claims.example.invalid/value#part"),
    ],
)
def test_auth_urls_and_claim_names_require_fixed_clean_https_urls(
    field_name: str,
    invalid_value: str,
) -> None:
    values = _auth_values()
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        AuthSettings(**values)


def test_email_claim_names_must_be_distinct() -> None:
    claim_name = "https://jobpilot.example.invalid/claims/email"

    with pytest.raises(ValueError, match="must be distinct"):
        AuthSettings(
            **_auth_values(
                access_token_email_claim=claim_name,
                access_token_email_verified_claim=claim_name,
            )
        )


def test_web_and_extension_clients_must_be_distinct() -> None:
    with pytest.raises(ValueError, match="web_client_id"):
        AuthSettings(**_auth_values(web_client_id="extension-client-id"))


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("web_origin", "https://jobpilot.example.invalid/"),
        ("web_origin", "https://user@jobpilot.example.invalid"),
        (
            "web_callback_url",
            "https://jobpilot.example.invalid/api/v1/auth/web/callback/",
        ),
        (
            "web_callback_url",
            "https://jobpilot.example.invalid/api/v1/auth/web/callback?code=x",
        ),
    ],
)
def test_web_urls_are_fixed_and_use_the_exact_callback_path(
    field_name: str,
    invalid_value: str,
) -> None:
    with pytest.raises(ValueError, match=field_name):
        AuthSettings(**_auth_values(**{field_name: invalid_value}))


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
        ("web_session_idle_seconds", 0),
        ("web_session_idle_seconds", 604_801),
        ("web_session_idle_seconds", True),
        ("web_session_absolute_seconds", 0),
        ("web_session_absolute_seconds", 2_592_001),
        ("web_session_absolute_seconds", True),
    ],
)
def test_auth_timing_controls_are_bounded(field_name: str, invalid_value: object) -> None:
    values = _auth_values(**{field_name: invalid_value})

    with pytest.raises(ValueError, match=field_name):
        AuthSettings(**values)


def test_web_session_idle_lifetime_cannot_exceed_absolute_lifetime() -> None:
    with pytest.raises(ValueError, match="must not exceed"):
        AuthSettings(
            **_auth_values(
                web_session_idle_seconds=601,
                web_session_absolute_seconds=600,
            )
        )


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
    values = _auth_values()
    values[field_name] = invalid_value

    with pytest.raises(ValueError, match=field_name):
        AuthSettings(**values)


def test_development_allows_only_same_host_loopback_http_with_exact_cors() -> None:
    auth = AuthSettings(
        **_auth_values(
            web_origin="http://localhost:5173",
            web_callback_url="http://localhost:8000/api/v1/auth/web/callback",
        )
    )

    settings = ApiSettings(
        environment="development",
        cors_origins=("http://localhost:5173",),
        auth=auth,
    )

    assert settings.auth is auth


@pytest.mark.parametrize(
    ("environment", "web_origin", "callback_url", "cors_origins"),
    [
        (
            "production",
            "http://localhost:5173",
            "http://localhost:8000/api/v1/auth/web/callback",
            ("http://localhost:5173",),
        ),
        (
            "development",
            "http://192.168.1.10:5173",
            "http://192.168.1.10:8000/api/v1/auth/web/callback",
            ("http://192.168.1.10:5173",),
        ),
        (
            "development",
            "http://localhost:5173",
            "http://127.0.0.1:8000/api/v1/auth/web/callback",
            ("http://localhost:5173",),
        ),
        (
            "development",
            "http://localhost:5173",
            "http://localhost:8000/api/v1/auth/web/callback",
            (),
        ),
    ],
)
def test_web_deployment_topology_fails_closed(
    environment: str,
    web_origin: str,
    callback_url: str,
    cors_origins: tuple[str, ...],
) -> None:
    auth = AuthSettings(**_auth_values(web_origin=web_origin, web_callback_url=callback_url))

    with pytest.raises(ValueError):
        ApiSettings(
            environment=environment,
            cors_origins=cors_origins,
            auth=auth,
        )
