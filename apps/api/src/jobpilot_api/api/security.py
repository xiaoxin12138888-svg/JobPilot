from __future__ import annotations

from ipaddress import ip_address

from fastapi import FastAPI, Request

from jobpilot_api.api.errors import public_error_response
from jobpilot_api.config import ApiSettings
from jobpilot_api.domain.resume_imports import MAX_RESUME_MULTIPART_BODY_BYTES

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
JOBPILOT_EXTENSION_ORIGIN = "chrome-extension://lgchonbleblfegkckndaaandoaekmgjf"
AUTOFILL_PROFILE_PATH = "/api/v1/autofill-profile"
RESUME_IMPORT_PARSE_PATH = "/api/v1/resume-imports/parse"


def install_local_write_middleware(application: FastAPI, settings: ApiSettings) -> None:
    @application.middleware("http")
    async def enforce_local_writes(request: Request, call_next):
        if request.method == "GET" and request.url.path == AUTOFILL_PROFILE_PATH:
            return await _enforce_autofill_profile_read(request, call_next, settings)
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        if not _is_loopback_host(request.url.hostname):
            return public_error_response(
                request, 403, "LOCAL_WRITE_FORBIDDEN", "Write requests must target loopback"
            )
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site", "").lower()
        is_resume_parse = request.method == "POST" and request.url.path == RESUME_IMPORT_PARSE_PATH
        if is_resume_parse:
            if origin not in settings.cors_origins or fetch_site == "cross-site":
                return public_error_response(
                    request,
                    403,
                    "LOCAL_WRITE_FORBIDDEN",
                    "Resume import is only available to the local Web app",
                )
            if not _has_safe_resume_import_content_length(request):
                return public_error_response(
                    request,
                    413,
                    "RESUME_FILE_TOO_LARGE",
                    "简历上传请求超过安全限制",
                )
            media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if media_type != "multipart/form-data":
                return public_error_response(
                    request,
                    415,
                    "MULTIPART_REQUIRED",
                    "Resume parsing requires multipart/form-data",
                )
            return await call_next(request)
        is_jobpilot_extension = (
            origin == JOBPILOT_EXTENSION_ORIGIN
            and fetch_site == "none"
            and request.method == "POST"
            and request.url.path == "/api/v1/jobs"
        )
        if (
            origin is not None and origin not in settings.cors_origins and not is_jobpilot_extension
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


async def _enforce_autofill_profile_read(request: Request, call_next, settings: ApiSettings):
    if not _is_loopback_host(request.url.hostname):
        return public_error_response(
            request, 403, "LOCAL_READ_FORBIDDEN", "Profile reads must target loopback"
        )
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site", "").lower()
    is_jobpilot_extension = origin == JOBPILOT_EXTENSION_ORIGIN and fetch_site == "none"
    is_allowed_web = origin in settings.cors_origins and fetch_site != "cross-site"
    if origin is not None and not (is_jobpilot_extension or is_allowed_web):
        return public_error_response(
            request, 403, "LOCAL_READ_FORBIDDEN", "Cross-site profile reads are not allowed"
        )
    if fetch_site == "cross-site":
        return public_error_response(
            request, 403, "LOCAL_READ_FORBIDDEN", "Cross-site profile reads are not allowed"
        )
    response = await call_next(request)
    if is_jobpilot_extension:
        response.headers["Access-Control-Allow-Origin"] = JOBPILOT_EXTENSION_ORIGIN
        response.headers.add_vary_header("Origin")
    return response


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _has_safe_resume_import_content_length(request: Request) -> bool:
    value = request.headers.get("content-length")
    if value is None:
        return False
    try:
        return 0 <= int(value) <= MAX_RESUME_MULTIPART_BODY_BYTES
    except ValueError:
        return False
