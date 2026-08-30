from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from zoneinfo import available_timezones

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

from jobpilot_api.application.identity_service import (
    AuthenticationRequiredError,
    IdentityConflictError,
    IdentityStoreUnavailableError,
    InvalidProfileUpdateError,
    InvalidVerifiedIdentityError,
)
from jobpilot_api.domain.identity import LocalUser

from .auth_dependencies import (
    AuthRuntimeDependency,
    CurrentUserDependency,
    VerifiedIdentityDependency,
    map_identity_service_error,
    require_empty_body,
)
from .errors import ApiError, ErrorResponse


class UserView(BaseModel):
    id: str
    email: str
    display_name: str | None = Field(serialization_alias="displayName")
    locale: str | None
    time_zone: str | None = Field(serialization_alias="timeZone")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class UserResponse(BaseModel):
    data: UserView


SUPPORTED_TIME_ZONES = frozenset(available_timezones())


class UpdateCurrentUserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"minProperties": 1})

    display_name: str | None = Field(
        default_factory=lambda: None,
        alias="displayName",
        max_length=100,
    )
    locale: Literal["zh-CN"] | SkipJsonSchema[None] = Field(
        default_factory=lambda: None,
    )
    time_zone: Annotated[str, Field(max_length=100)] | SkipJsonSchema[None] = Field(
        default_factory=lambda: None,
        alias="timeZone",
        json_schema_extra={"format": "iana-time-zone"},
    )

    @model_validator(mode="after")
    def validate_profile_changes(self) -> UpdateCurrentUserRequest:
        if not self.model_fields_set:
            raise ValueError("at least one profile field must be provided")
        if "locale" in self.model_fields_set and self.locale is None:
            raise ValueError("locale is not supported")
        if "time_zone" in self.model_fields_set:
            if self.time_zone is None or self.time_zone not in SUPPORTED_TIME_ZONES:
                raise ValueError("timeZone is not supported")
        return self


EXTENSION_BEARER = HTTPBearer(auto_error=False, scheme_name="ExtensionBearer")
COMMON_AUTH_ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["authentication"],
    dependencies=[Depends(EXTENSION_BEARER)],
    responses=COMMON_AUTH_ERROR_RESPONSES,
)


@router.post(
    "/session",
    response_model=UserResponse,
    dependencies=[Depends(require_empty_body)],
    responses={
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def establish_extension_identity(
    identity: VerifiedIdentityDependency,
    runtime: AuthRuntimeDependency,
) -> UserResponse:
    try:
        user = runtime.identity_service.provision(identity)
    except IdentityConflictError:
        raise ApiError(
            409, "IDENTITY_CONFLICT", "Identity cannot be linked automatically"
        ) from None
    except (
        AuthenticationRequiredError,
        IdentityStoreUnavailableError,
        InvalidVerifiedIdentityError,
    ) as error:
        raise map_identity_service_error(error) from None
    return _user_response(user)


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: CurrentUserDependency,
    runtime: AuthRuntimeDependency,
) -> UserResponse:
    try:
        user = runtime.identity_service.get_active_user(current_user)
    except (AuthenticationRequiredError, IdentityStoreUnavailableError) as error:
        raise map_identity_service_error(error) from None
    return _user_response(user)


@router.patch(
    "/me",
    response_model=UserResponse,
    responses={422: {"model": ErrorResponse}},
)
def update_current_user_profile(
    update: UpdateCurrentUserRequest,
    current_user: CurrentUserDependency,
    runtime: AuthRuntimeDependency,
) -> UserResponse:
    try:
        user = runtime.identity_service.update_profile(
            current_user,
            **update.model_dump(exclude_unset=True),
        )
    except (
        AuthenticationRequiredError,
        IdentityStoreUnavailableError,
        InvalidProfileUpdateError,
    ) as error:
        raise map_identity_service_error(error) from None
    return _user_response(user)


def _user_response(user: LocalUser) -> UserResponse:
    return UserResponse(
        data=UserView(
            id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            locale=user.locale,
            time_zone=user.time_zone,
            created_at=user.created_at.astimezone(UTC),
            updated_at=user.updated_at.astimezone(UTC),
        )
    )
