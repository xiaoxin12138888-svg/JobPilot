from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from jobpilot_api.api.dependencies import (
    get_analysis_service,
    get_application_service,
    get_job_service,
    get_resume_version_service,
)
from jobpilot_api.api.schemas import (
    AnalysisCreateRequest,
    ApplicationCreateRequest,
    ApplicationListItem,
    ApplicationListResponse,
    ApplicationResponse,
    ApplicationUpdateRequest,
    JobAnalysisResponse,
    JobCreateRequest,
    JobListItem,
    JobListResponse,
    JobResponse,
    JobUpdateRequest,
    ResumeVersionCreateRequest,
    ResumeVersionDuplicateRequest,
    ResumeVersionListResponse,
    ResumeVersionResponse,
    ResumeVersionUpdateRequest,
)
from jobpilot_api.application.jd_analysis import JDAnalysisService
from jobpilot_api.application.services import ApplicationService, JobService, ResumeVersionService
from jobpilot_api.domain.applications import ApplicationStatus
from jobpilot_api.domain.jobs import JobDraft
from jobpilot_api.domain.resume_versions import ResumeVersionDraft

router = APIRouter(prefix="/api/v1")
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]


@router.post("/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    request: JobCreateRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    job = service.create(JobDraft.create(**request.model_dump()))
    return JobResponse.from_domain(job)


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    service: Annotated[JobService, Depends(get_job_service)],
    keyword: Annotated[str | None, Query(max_length=200)] = None,
    source: Literal["manual", "boss", "nowcoder"] | None = None,
    application_status: Annotated[
        ApplicationStatus | None, Query(alias="applicationStatus")
    ] = None,
    limit: PageLimit = 50,
    offset: PageOffset = 0,
) -> JobListResponse:
    items, total = service.list(
        keyword=keyword,
        source=source,
        application_status=application_status,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(
        items=[JobListItem.from_entry(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    return JobResponse.from_domain(service.get(job_id))


@router.patch("/jobs/{job_id}", response_model=JobResponse)
def update_job(
    job_id: str,
    request: JobUpdateRequest,
    service: Annotated[JobService, Depends(get_job_service)],
) -> JobResponse:
    changes = request.model_dump(exclude_unset=True)
    return JobResponse.from_domain(service.update(job_id, changes))


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: str,
    service: Annotated[JobService, Depends(get_job_service)],
) -> Response:
    service.delete(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs/{job_id}/analysis", response_model=JobAnalysisResponse)
def get_job_analysis(
    job_id: str,
    service: Annotated[JDAnalysisService, Depends(get_analysis_service)],
) -> JobAnalysisResponse:
    return JobAnalysisResponse.from_state(service.get(job_id))


@router.post("/jobs/{job_id}/analysis", response_model=JobAnalysisResponse)
def analyze_job(
    job_id: str,
    _request: AnalysisCreateRequest,
    service: Annotated[JDAnalysisService, Depends(get_analysis_service)],
) -> JobAnalysisResponse:
    return JobAnalysisResponse.from_state(service.analyze(job_id))


@router.post(
    "/jobs/{job_id}/application",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    job_id: str,
    _request: ApplicationCreateRequest,
    service: Annotated[ApplicationService, Depends(get_application_service)],
) -> ApplicationResponse:
    return ApplicationResponse.from_domain(service.create(job_id))


@router.get("/applications", response_model=ApplicationListResponse)
def list_applications(
    service: Annotated[ApplicationService, Depends(get_application_service)],
    job_id: Annotated[str | None, Query(alias="jobId", max_length=36)] = None,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    limit: PageLimit = 50,
    offset: PageOffset = 0,
) -> ApplicationListResponse:
    items, total = service.list(
        job_id=job_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ApplicationListResponse(
        items=[ApplicationListItem.from_entry(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
def get_application(
    application_id: str,
    service: Annotated[ApplicationService, Depends(get_application_service)],
) -> ApplicationResponse:
    return ApplicationResponse.from_domain(service.get(application_id))


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
def update_application(
    application_id: str,
    request: ApplicationUpdateRequest,
    service: Annotated[ApplicationService, Depends(get_application_service)],
) -> ApplicationResponse:
    application = service.update(
        application_id,
        status=request.status,
        confirm_applied=request.confirm_applied,
        resume_version_id=request.resume_version_id,
        update_resume_version="resume_version_id" in request.model_fields_set,
    )
    return ApplicationResponse.from_domain(application)


@router.get("/resume-versions", response_model=ResumeVersionListResponse)
def list_resume_versions(
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
    limit: PageLimit = 50,
    offset: PageOffset = 0,
) -> ResumeVersionListResponse:
    items, total = service.list(limit=limit, offset=offset)
    return ResumeVersionListResponse(
        items=[ResumeVersionResponse.from_domain(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/resume-versions",
    response_model=ResumeVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resume_version(
    request: ResumeVersionCreateRequest,
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
) -> ResumeVersionResponse:
    resume = service.create(ResumeVersionDraft.create(**request.model_dump()))
    return ResumeVersionResponse.from_domain(resume)


@router.get("/resume-versions/{resume_version_id}", response_model=ResumeVersionResponse)
def get_resume_version(
    resume_version_id: str,
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
) -> ResumeVersionResponse:
    return ResumeVersionResponse.from_domain(service.get(resume_version_id))


@router.patch("/resume-versions/{resume_version_id}", response_model=ResumeVersionResponse)
def update_resume_version(
    resume_version_id: str,
    request: ResumeVersionUpdateRequest,
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
) -> ResumeVersionResponse:
    resume = service.update(resume_version_id, request.model_dump(exclude_unset=True))
    return ResumeVersionResponse.from_domain(resume)


@router.post(
    "/resume-versions/{resume_version_id}/duplicate",
    response_model=ResumeVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def duplicate_resume_version(
    resume_version_id: str,
    request: ResumeVersionDuplicateRequest,
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
) -> ResumeVersionResponse:
    return ResumeVersionResponse.from_domain(
        service.duplicate(resume_version_id, name=request.name)
    )


@router.delete("/resume-versions/{resume_version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume_version(
    resume_version_id: str,
    service: Annotated[ResumeVersionService, Depends(get_resume_version_service)],
) -> Response:
    service.delete(resume_version_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
