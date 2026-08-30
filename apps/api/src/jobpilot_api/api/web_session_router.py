from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from jobpilot_api.application.web_session_service import (
    WebSessionCsrfRejectedError,
    WebSessionStoreUnavailableError,
)

from .auth_dependencies import (
    AuthRuntimeDependency,
    CurrentWebSessionDependency,
    require_empty_body,
    require_web_origin_and_fetch,
    resolve_web_logout_credentials,
)
from .auth_router import WEB_SESSION_COOKIE
from .errors import ApiError, ErrorResponse


class CsrfTokenView(BaseModel):
    csrf_token: str = Field(serialization_alias="csrfToken")


class CsrfTokenResponse(BaseModel):
    data: CsrfTokenView


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.get(
    "/csrf",
    response_model=CsrfTokenResponse,
    dependencies=[Depends(WEB_SESSION_COOKIE)],
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
def get_csrf_token(current_session: CurrentWebSessionDependency) -> CsrfTokenResponse:
    return CsrfTokenResponse(data=CsrfTokenView(csrf_token=current_session.csrf_token))


@router.post(
    "/logout",
    status_code=204,
    dependencies=[Depends(require_web_origin_and_fetch), Depends(require_empty_body)],
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    openapi_extra={"security": [{}, {"WebSessionCookie": []}]},
)
def logout_web_session(
    request: Request,
    runtime: AuthRuntimeDependency,
) -> Response:
    session_secret, csrf_token = resolve_web_logout_credentials(request, runtime)
    try:
        runtime.web.session_service.logout(session_secret, csrf_token)
    except WebSessionCsrfRejectedError:
        raise ApiError(403, "FORBIDDEN", "Request is not permitted") from None
    except WebSessionStoreUnavailableError:
        raise ApiError(
            503,
            "DEPENDENCY_UNAVAILABLE",
            "A required dependency is temporarily unavailable",
        ) from None

    response = Response(status_code=204)
    response.delete_cookie(
        key=runtime.web.session_cookie_name,
        path="/",
        secure=runtime.web.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    return response
