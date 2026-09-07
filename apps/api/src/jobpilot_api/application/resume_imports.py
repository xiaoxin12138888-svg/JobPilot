from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath
from time import monotonic

from jobpilot_api.application.repositories import ResumeImportRepository
from jobpilot_api.domain.resume_imports import (
    MAX_RESUME_FILE_BYTES,
    ResumeFileType,
    ResumeImportConfirmation,
    ResumeImportError,
    ResumeImportPreview,
    ResumeProfileImportPatch,
    build_resume_import_preview,
)
from jobpilot_api.domain.resume_versions import ResumeVersionDraft
from jobpilot_api.infrastructure.resume_import.docx_parser import parse_docx
from jobpilot_api.infrastructure.resume_import.pdf_parser import parse_pdf

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True, slots=True)
class ResumeImportMetrics:
    size_bytes: int
    page_count: int | None
    parse_latency_ms: int
    character_count: int


@dataclass(frozen=True, slots=True)
class ResumeImportParseResult:
    preview: ResumeImportPreview
    metrics: ResumeImportMetrics


class ResumeImportService:
    def __init__(
        self,
        repository: ResumeImportRepository,
    ) -> None:
        self._repository = repository

    def parse(
        self, *, filename: str | None, content_type: str | None, data: bytes
    ) -> ResumeImportParseResult:
        started_at = monotonic()
        if len(data) > MAX_RESUME_FILE_BYTES:
            raise ResumeImportError(
                "RESUME_FILE_TOO_LARGE", "简历文件不能超过 10 MiB", status_code=413
            )
        file_type = _validated_file_type(filename, content_type, data)
        document = parse_pdf(data) if file_type == ResumeFileType.PDF else parse_docx(data)
        preview = build_resume_import_preview(document)
        elapsed_ms = max(0, round((monotonic() - started_at) * 1_000))
        return ResumeImportParseResult(
            preview=preview,
            metrics=ResumeImportMetrics(
                size_bytes=len(data),
                page_count=document.page_count,
                parse_latency_ms=elapsed_ms,
                character_count=len(document.raw_text),
            ),
        )

    def confirm(
        self,
        resume_version: ResumeVersionDraft | None,
        profile_import: ResumeProfileImportPatch | None,
    ) -> ResumeImportConfirmation:
        if resume_version is None and profile_import is None:
            raise ResumeImportError("VALIDATION_ERROR", "至少选择一个导入目标")
        return self._repository.confirm(resume_version, profile_import)


def _validated_file_type(
    filename: str | None, content_type: str | None, data: bytes
) -> ResumeFileType:
    extension = PurePath(filename or "").suffix.casefold()
    normalized_mime = (content_type or "").partition(";")[0].strip().casefold()
    if extension not in {".pdf", ".docx"}:
        raise ResumeImportError(
            "UNSUPPORTED_RESUME_FILE_TYPE",
            "当前支持 PDF 和 DOCX 简历",
            status_code=415,
        )
    expected_mime = PDF_MIME if extension == ".pdf" else DOCX_MIME
    expected_magic = b"%PDF-" if extension == ".pdf" else b"PK\x03\x04"
    if normalized_mime != expected_mime or not data.startswith(expected_magic):
        raise ResumeImportError(
            "RESUME_FILE_SIGNATURE_MISMATCH",
            "文件扩展名、类型与内容不一致",
            status_code=422,
        )
    return ResumeFileType.PDF if extension == ".pdf" else ResumeFileType.DOCX
