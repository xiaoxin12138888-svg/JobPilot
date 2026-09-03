from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import urlsplit

DEFAULT_API_BIND_HOST = "127.0.0.1"
DEFAULT_CORS_ORIGINS = ("http://127.0.0.1:5173",)
ALLOWED_CORS_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True, slots=True)
class ApiSettings:
    bind_host: str
    cors_origins: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_loopback_bind_host(self.bind_host)
        seen: set[str] = set()
        for origin in self.cors_origins:
            _validate_cors_origin(origin)
            if origin in seen:
                raise ValueError("CORS origins must not contain duplicate values")
            seen.add(origin)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> ApiSettings:
        values = os.environ if environment is None else environment
        configured_origins = values.get("JOBPILOT_CORS_ORIGINS")
        if configured_origins is None:
            cors_origins = DEFAULT_CORS_ORIGINS
        else:
            cors_origins = tuple(
                origin.strip() for origin in configured_origins.split(",") if origin.strip()
            )
        return cls(
            bind_host=values.get("JOBPILOT_API_BIND_HOST", DEFAULT_API_BIND_HOST),
            cors_origins=cors_origins,
        )


def _validate_loopback_bind_host(host: str) -> None:
    if not host or host != host.strip():
        raise ValueError("API bind host must be an exact IP-literal loopback address")
    try:
        address = ip_address(host)
    except ValueError:
        raise ValueError("API bind host must be an IP-literal loopback address") from None
    if not address.is_loopback:
        raise ValueError("API bind host must be a loopback address")


def _validate_cors_origin(origin: str) -> None:
    if not origin or origin != origin.strip() or "*" in origin:
        raise ValueError("CORS origin must be one exact origin without wildcards")
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError:
        raise ValueError("CORS origin must be one exact valid origin") from None
    if (
        parsed.scheme not in ALLOWED_CORS_SCHEMES
        or parsed.hostname is None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
        or port == 0
    ):
        raise ValueError("CORS origin must be one exact origin without credentials or suffixes")
    if not _is_loopback_cors_host(parsed.hostname):
        raise ValueError("CORS origin must use a loopback Web host")


def _is_loopback_cors_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False
