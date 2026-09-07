from __future__ import annotations

from io import BytesIO
from time import monotonic

from pypdf import PdfReader

from jobpilot_api.domain.resume_imports import (
    MAX_EXTRACTED_TEXT_LENGTH,
    MAX_PDF_PAGES,
    MIN_PDF_NON_WHITESPACE_CHARACTERS,
    RESUME_PARSE_TIMEOUT_SECONDS,
    DocumentBlock,
    DocumentBlockKind,
    ParsedResumeDocument,
    ResumeFileType,
    ResumeImportError,
    ResumeImportWarning,
)


def parse_pdf(data: bytes) -> ParsedResumeDocument:
    started_at = monotonic()
    try:
        reader = PdfReader(BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ResumeImportError("RESUME_PDF_ENCRYPTED", "请上传未加密的 PDF 简历")
        page_count = len(reader.pages)
        if page_count > MAX_PDF_PAGES:
            raise ResumeImportError("RESUME_PDF_INVALID", "PDF 页数超过 100 页限制")
        page_texts: list[str] = []
        blocks: list[DocumentBlock] = []
        total_characters = 0
        for page in reader.pages:
            _check_timeout(started_at)
            text = _normalize_text(page.extract_text() or "")
            total_characters += len(text)
            if total_characters > MAX_EXTRACTED_TEXT_LENGTH:
                raise ResumeImportError(
                    "RESUME_TEXT_TOO_LARGE",
                    "简历提取文本超过 100,000 字符限制",
                )
            page_texts.append(text)
            blocks.extend(
                DocumentBlock(DocumentBlockKind.TEXT, line.strip())
                for line in text.splitlines()
                if line.strip()
            )
        _check_timeout(started_at)
    except ResumeImportError:
        raise
    except Exception as error:
        raise ResumeImportError("RESUME_PDF_INVALID", "PDF 文件无法解析") from error

    raw_text = "\n".join(text for text in page_texts if text).strip()
    if len("".join(raw_text.split())) < MIN_PDF_NON_WHITESPACE_CHARACTERS:
        raise ResumeImportError(
            "RESUME_PDF_NO_TEXT",
            "该 PDF 可能是扫描件或图片型简历，当前版本暂不支持 OCR",
        )
    non_whitespace_characters = len("".join(raw_text.split()))
    warnings = (
        (
            ResumeImportWarning(
                "PDF_TEXT_SHORT",
                "该 PDF 提取文本较少，请检查是否存在漏段。",
            ),
        )
        if non_whitespace_characters < 200
        else ()
    )
    return ParsedResumeDocument(
        file_type=ResumeFileType.PDF,
        raw_text=raw_text,
        blocks=tuple(blocks),
        warnings=warnings,
        page_count=page_count,
    )


def _normalize_text(value: str) -> str:
    lines = [line.rstrip() for line in value.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def _check_timeout(started_at: float) -> None:
    if monotonic() - started_at > RESUME_PARSE_TIMEOUT_SECONDS:
        raise ResumeImportError(
            "RESUME_PARSE_TIMEOUT", "本机解析耗时超过安全限制，请换用更简单的文件"
        )
