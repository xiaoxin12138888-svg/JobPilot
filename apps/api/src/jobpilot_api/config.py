import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import SplitResult, urlsplit

DEVELOPMENT_WEB_ORIGIN = "http://localhost:5173"
VALID_ENVIRONMENTS = frozenset({"development", "test", "production"})
AUTH_REQUIRED_ENVIRONMENT_KEYS = (
    "JOBPILOT_AUTH_ISSUER",
    "JOBPILOT_AUTH_JWKS_URL",
    "JOBPILOT_AUTH_AUTHORIZE_URL",
    "JOBPILOT_AUTH_TOKEN_URL",
    "JOBPILOT_AUTH_AUDIENCE",
    "JOBPILOT_AUTH_EXTENSION_CLIENT_ID",
    "JOBPILOT_AUTH_WEB_CLIENT_ID",
    "JOBPILOT_AUTH_WEB_CLIENT_SECRET",
    "JOBPILOT_WEB_ORIGIN",
    "JOBPILOT_WEB_CALLBACK_URL",
    "JOBPILOT_WEB_SESSION_IDLE_SECONDS",
    "JOBPILOT_WEB_SESSION_ABSOLUTE_SECONDS",
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
    authorize_url: str
    token_url: str
    audience: str
    extension_client_id: str
    web_client_id: str
    web_client_secret: str = field(repr=False)
    web_origin: str
    web_callback_url: str
    access_token_email_claim: str
    access_token_email_verified_claim: str
    clock_skew_seconds: int = 60
    jwks_cache_seconds: int = 300
    jwks_timeout_seconds: float = 5.0
    web_session_idle_seconds: int = 604_800
    web_session_absolute_seconds: int = 2_592_000

    def __post_init__(self) -> None:
        issuer_url = _validate_https_url("issuer", self.issuer)
        jwks_url = _validate_https_url("jwks_url", self.jwks_url)
        authorize_url = _validate_https_url("authorize_url", self.authorize_url)
        token_url = _validate_https_url("token_url", self.token_url)
        if not issuer_url.path.endswith("/"):
            raise ValueError("issuer must use its canonical trailing slash")
        issuer_origin = _url_origin(issuer_url)
        if _url_origin(jwks_url) != issuer_origin:
            raise ValueError("jwks_url must share the issuer origin")
        if _url_origin(authorize_url) != issuer_origin:
            raise ValueError("authorize_url must share the issuer origin")
        if _url_origin(token_url) != issuer_origin:
            raise ValueError("token_url must share the issuer origin")
        _validate_nonempty_exact_value("audience", self.audience)
        _validate_nonempty_exact_value("extension_client_id", self.extension_client_id)
        _validate_nonempty_exact_value("web_client_id", self.web_client_id)
        _validate_nonempty_exact_value("web_client_secret", self.web_client_secret)
        if self.web_client_id == self.extension_client_id:
            raise ValueError("web_client_id must differ from extension_client_id")
        _validate_web_origin(self.web_origin)
        _validate_web_callback_url(self.web_callback_url)
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
        if type(self.web_session_idle_seconds) is not int or not (
            1 <= self.web_session_idle_seconds <= 604_800
        ):
            raise ValueError("web_session_idle_seconds must be between 1 and 604800")
        if type(self.web_session_absolute_seconds) is not int or not (
            1 <= self.web_session_absolute_seconds <= 2_592_000
        ):
            raise ValueError("web_session_absolute_seconds must be between 1 and 2592000")
        if self.web_session_idle_seconds > self.web_session_absolute_seconds:
            raise ValueError(
                "web_session_idle_seconds must not exceed web_session_absolute_seconds"
            )


@dataclass(frozen=True)
class ApiSettings:
    environment: str
    cors_origins: tuple[str, ...]
    auth: AuthSettings | None = None
    database_url: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(f"Unsupported JOBPILOT_ENVIRONMENT: {self.environment}")
        if "*" in self.cors_origins:
            raise ValueError("Wildcard CORS origins are not allowed")
        if self.database_url is not None:
            _validate_nonempty_exact_value("database_url", self.database_url)
        if self.auth is not None:
            _validate_web_deployment(self.environment, self.cors_origins, self.auth)

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
            database_url=_load_database_url(values),
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
        web_session_idle_seconds = int(values["JOBPILOT_WEB_SESSION_IDLE_SECONDS"])
        web_session_absolute_seconds = int(values["JOBPILOT_WEB_SESSION_ABSOLUTE_SECONDS"])
    except ValueError:
        raise ValueError("Authentication timing configuration must be numeric") from None

    return AuthSettings(
        issuer=values["JOBPILOT_AUTH_ISSUER"],
        jwks_url=values["JOBPILOT_AUTH_JWKS_URL"],
        authorize_url=values["JOBPILOT_AUTH_AUTHORIZE_URL"],
        token_url=values["JOBPILOT_AUTH_TOKEN_URL"],
        audience=values["JOBPILOT_AUTH_AUDIENCE"],
        extension_client_id=values["JOBPILOT_AUTH_EXTENSION_CLIENT_ID"],
        web_client_id=values["JOBPILOT_AUTH_WEB_CLIENT_ID"],
        web_client_secret=values["JOBPILOT_AUTH_WEB_CLIENT_SECRET"],
        web_origin=values["JOBPILOT_WEB_ORIGIN"],
        web_callback_url=values["JOBPILOT_WEB_CALLBACK_URL"],
        access_token_email_claim=values["JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_CLAIM"],
        access_token_email_verified_claim=values["JOBPILOT_AUTH_ACCESS_TOKEN_EMAIL_VERIFIED_CLAIM"],
        clock_skew_seconds=clock_skew_seconds,
        jwks_cache_seconds=jwks_cache_seconds,
        jwks_timeout_seconds=jwks_timeout_seconds,
        web_session_idle_seconds=web_session_idle_seconds,
        web_session_absolute_seconds=web_session_absolute_seconds,
    )


def _load_database_url(values: Mapping[str, str]) -> str | None:
    configured_url = values.get("JOBPILOT_DATABASE_URL")
    if configured_url is None or not configured_url.strip():
        return None
    return configured_url.strip()


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


def _validate_web_origin(value: str) -> SplitResult:
    parsed = _validate_web_url("web_origin", value)
    if parsed.path or parsed.query or parsed.fragment:
        raise ValueError("web_origin must be an exact origin without a path or suffixes")
    return parsed


def _validate_web_callback_url(value: str) -> SplitResult:
    parsed = _validate_web_url("web_callback_url", value)
    if parsed.path != "/api/v1/auth/web/callback" or parsed.query or parsed.fragment:
        raise ValueError("web_callback_url must use the fixed Web callback path")
    return parsed


def _validate_web_url(field_name: str, value: str) -> SplitResult:
    _validate_nonempty_exact_value(field_name, value)
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError(f"{field_name} must be a valid HTTP or HTTPS URL") from None
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname is None
        or port == 0
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{field_name} must be a fixed HTTP or HTTPS URL")
    return parsed


def _validate_web_deployment(
    environment: str,
    cors_origins: tuple[str, ...],
    auth: AuthSettings,
) -> None:
    web_origin = _validate_web_origin(auth.web_origin)
    callback_url = _validate_web_callback_url(auth.web_callback_url)
    if web_origin.scheme != callback_url.scheme or web_origin.hostname != callback_url.hostname:
        raise ValueError("Web origin and callback must use the same scheme and hostname")

    if environment == "development" and web_origin.scheme == "http":
        if not (_is_loopback(web_origin.hostname) and _is_loopback(callback_url.hostname)):
            raise ValueError("HTTP Web authentication is allowed only on loopback development")
    elif web_origin.scheme != "https":
        raise ValueError("Web authentication requires HTTPS outside loopback development")

    if _url_origin(web_origin) != _url_origin(callback_url) and auth.web_origin not in cors_origins:
        raise ValueError("Cross-origin Web authentication requires the exact Web CORS origin")


def _is_loopback(hostname: str) -> bool:
    if hostname == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False
