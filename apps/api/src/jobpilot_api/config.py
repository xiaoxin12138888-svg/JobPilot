import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

DEVELOPMENT_WEB_ORIGIN = "http://localhost:5173"
VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})
AUTH_REQUIRED_ENVIRONMENT_KEYS = (
    "JOBPILOT_AUTH_ISSUER",
    "JOBPILOT_AUTH_JWKS_URL",
    "JOBPILOT_AUTH_TOKEN_URL",
    "JOBPILOT_AUTH_AUDIENCE",
    "JOBPILOT_AUTH_EXTENSION_CLIENT_ID",
    "JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_CLAIM",
    "JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_VERIFIED_CLAIM",
)
AUTH_OPTIONAL_ENVIRONMENT_KEYS = (
    "JOBPILOT_AUTH_CLOCK_SKEW_SECONDS",
    "JOBPILOT_AUTH_JWKS_CACHE_SECONDS",
    "JOBPILOT_AUTH_JWKS_TIMEOUT_SECONDS",
)


@dataclass(frozen=True, slots=True)
class AuthSettings:
    issuer: str
    jwks_url: str
    token_url: str
    audience: str
    extension_client_id: str
    access_token_email_claim: str
    access_token_email_verified_claim: str
    clock_skew_seconds: int = 60
    jwks_cache_seconds: int = 300
    jwks_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        issuer_url = _validate_https_url("issuer", self.issuer)
        jwks_url = _validate_https_url("jwks_url", self.jwks_url)
        token_url = _validate_https_url("token_url", self.token_url)
        if not issuer_url.path.endswith("/"):
            raise ValueError("issuer must use its canonical trailing slash")
        issuer_origin = _url_origin(issuer_url)
        if _url_origin(jwks_url) != issuer_origin:
            raise ValueError("jwks_url must share the issuer origin")
        if _url_origin(token_url) != issuer_origin:
            raise ValueError("token_url must share the issuer origin")
        _validate_nonempty_exact_value("audience", self.audience)
        _validate_nonempty_exact_value("extension_client_id", self.extension_client_id)
        _validate_https_url("access_token_email_claim", self.access_token_email_claim)
        _validate_https_url(
            "access_token_email_verified_claim",
            self.access_token_email_verified_claim,
        )
        if self.access_token_email_claim == self.access_token_email_verified_claim:
            raise ValueError("Access-token email claim names must be distinct")
        if type(self.clock_skew_seconds) is not int or not 0 <= self.clock_skew_seconds <= 300:
            raise ValueError("clock_skew_seconds must be between 0 and 300")
        if type(self.jwks_cache_seconds) is not int or not 1 <= self.jwks_cache_seconds <= 3600:
            raise ValueError("jwks_cache_seconds must be between 1 and 3600")
        if type(self.jwks_timeout_seconds) not in {int, float} or not (
            0 < self.jwks_timeout_seconds <= 30
        ):
            raise ValueError("jwks_timeout_seconds must be greater than 0 and at most 30")


@dataclass(frozen=True)
class ApiSettings:
    environment: str
    cors_origins: tuple[str, ...]
    auth: AuthSettings | None = None

    def __post_init__(self) -> None:
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(f"Unsupported JOBPILOT_ENVIRONMENT: {self.environment}")
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are not allowed")

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "ApiSettings":
        values = os.environ if environment is None else environment
        name = values.get("JOBPILOT_ENVIRONMENT", "development").strip().lower()
        configured_origins = values.get("JOBPILOT_CORS_ORIGINS")

        if configured_origins is None:
            origins = (DEVELOPMENT_WEB_ORIGIN,) if name == "development" else ()
        else:
            origins = tuple(
                origin.strip() for origin in configured_origins.split(",") if origin.strip()
            )

        return cls(
            environment=name,
            cors_origins=origins,
            auth=_load_auth_settings(values),
        )


def _load_auth_settings(values: Mapping[str, str]) -> AuthSettings | None:
    auth_keys = AUTH_REQUIRED_ENVIRONMENT_KEYS + AUTH_OPTIONAL_ENVIRONMENT_KEYS
    if not any(values.get(key, "").strip() for key in auth_keys):
        return None

    missing_keys = [
        key for key in AUTH_REQUIRED_ENVIRONMENT_KEYS if not values.get(key, "").strip()
    ]
    if missing_keys:
        raise ValueError(
            "Incomplete authentication configuration; missing: " + ", ".join(missing_keys)
        )

    try:
        clock_skew_seconds = int(values.get("JOBPILOT_AUTH_CLOCK_SKEW_SECONDS", "60"))
        jwks_cache_seconds = int(values.get("JOBPILOT_AUTH_JWKS_CACHE_SECONDS", "300"))
        jwks_timeout_seconds = float(values.get("JOBPILOT_AUTH_JWKS_TIMEOUT_SECONDS", "5"))
    except ValueError:
        raise ValueError("Authentication timing configuration must be numeric") from None

    return AuthSettings(
        issuer=values["JOBPILOT_AUTH_ISSUER"].strip(),
        jwks_url=values["JOBPILOT_AUTH_JWKS_URL"].strip(),
        token_url=values["JOBPILOT_AUTH_TOKEN_URL"].strip(),
        audience=values["JOBPILOT_AUTH_AUDIENCE"].strip(),
        extension_client_id=values["JOBPILOT_AUTH_EXTENSION_CLIENT_ID"].strip(),
        access_token_email_claim=values["JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_CLAIM"].strip(),
        access_token_email_verified_claim=values[
            "JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_VERIFIED_CLAIM"
        ].strip(),
        clock_skew_seconds=clock_skew_seconds,
        jwks_cache_seconds=jwks_cache_seconds,
        jwks_timeout_seconds=jwks_timeout_seconds,
    )


def _validate_https_url(field_name: str, value: str) -> SplitResult:
    _validate_nonempty_exact_value(field_name, value)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError(f"{field_name} must be a valid HTTPS URL") from None
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or port == 0
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{field_name} must be a fixed HTTPS URL without credentials or suffixes")
    return parsed


def _url_origin(parsed: SplitResult) -> tuple[str, str, int]:
    return parsed.scheme, parsed.hostname, 443 if parsed.port is None else parsed.port


def _validate_nonempty_exact_value(field_name: str, value: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be a non-empty exact value")
