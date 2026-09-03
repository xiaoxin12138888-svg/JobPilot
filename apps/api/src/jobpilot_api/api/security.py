from __future__ import annotations

from ipaddress import ip_address

from fastapi import FastAPI, Request

from jobpilot_api.api.errors import public_error_response
from jobpilot_api.config import ApiSettings

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def install_local_write_middleware(application: FastAPI, settings: ApiSettings) -> None:
    @application.middleware("http")
    async def enforce_local_writes(request: Request, call_next):
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        if not _is_loopback_host(request.url.hostname):
            return public_error_response(
                request, 403, "LOCAL_WRITE_FORBIDDEN", "Write requests must target loopback"
            )
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        if (
            origin is not None and origin not in settings.cors_origins
        ) or fetch_site == "cross-site":
            return public_error_response(
                request, 403, "LOCAL_WRITE_FORBIDDEN", "Cross-site writes are not allowed"
            )
        if request.method in {"POST", "PUT", "PATCH"}:
            media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type != "application/json":
                return public_error_response(
                    request, 415, "JSON_REQUIRED", "Write requests must use application/json"
                )
        return await call_next(request)


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False
