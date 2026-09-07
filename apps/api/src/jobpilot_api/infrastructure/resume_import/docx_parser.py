from __future__ import annotations

from io import BytesIO
from pathlib import PurePosixPath
from time import monotonic
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from jobpilot_api.domain.resume_imports import (
    MAX_EXTRACTED_TEXT_LENGTH,
    RESUME_PARSE_TIMEOUT_SECONDS,
    DocumentBlock,
    DocumentBlockKind,
    ParsedResumeDocument,
    ResumeFileType,
    ResumeImportError,
    ResumeImportWarning,
)

MAX_ZIP_ENTRIES = 1_000
MAX_ZIP_ENTRY_BYTES = 20 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 50 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 200
_XML_MARKERS = (b"<!doctype", b"<!entity")


def parse_docx(data: bytes) -> ParsedResumeDocument:
    started_at = monotonic()
    warnings = _validate_package(data, started_at)
    try:
        document = Document(BytesIO(data))
        blocks = _body_blocks(document, started_at)
    except ResumeImportError:
        raise
    except Exception as error:
        raise ResumeImportError("RESUME_DOCX_INVALID", "DOCX 文件无法解析") from error
    raw_text = "\n".join(block.text for block in blocks).strip()
    if not raw_text:
        raise ResumeImportError("RESUME_DOCX_INVALID", "DOCX 中没有可导入的文本")
    if len(raw_text) > MAX_EXTRACTED_TEXT_LENGTH:
        raise ResumeImportError(
            "RESUME_TEXT_TOO_LARGE",
            "简历提取文本超过 100,000 字符限制",
        )
    if any(block.kind == DocumentBlockKind.TABLE_ROW for block in blocks):
        warnings = (
            *warnings,
            ResumeImportWarning(
                "TABLE_ORDER_REVIEW",
                "检测到表格内容，请在导入前检查阅读顺序。",
            ),
        )
    return ParsedResumeDocument(
        file_type=ResumeFileType.DOCX,
        raw_text=raw_text,
        blocks=tuple(blocks),
        warnings=warnings,
    )


def _validate_package(data: bytes, started_at: float) -> tuple[ResumeImportWarning, ...]:
    external_relationship = False
    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise _invalid_docx()
            names = {entry.filename for entry in entries}
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                raise _invalid_docx()
            total_size = 0
            for entry in entries:
                _check_timeout(started_at)
                path = PurePosixPath(entry.filename.replace("\\", "/"))
                if path.is_absolute() or ".." in path.parts:
                    raise _invalid_docx()
                total_size += entry.file_size
                if entry.file_size > MAX_ZIP_ENTRY_BYTES or total_size > MAX_ZIP_TOTAL_BYTES:
                    raise _invalid_docx()
                if entry.file_size and entry.compress_size == 0:
                    raise _invalid_docx()
                if (
                    entry.compress_size
                    and entry.file_size / entry.compress_size > MAX_ZIP_COMPRESSION_RATIO
                ):
                    raise _invalid_docx()
                lowered_name = entry.filename.casefold()
                if "vbaproject" in lowered_name or lowered_name.endswith(".bin"):
                    raise _invalid_docx()
                if lowered_name.endswith((".xml", ".rels")):
                    content = archive.read(entry)
                    lowered_content = content.lower()
                    if any(marker in lowered_content for marker in _XML_MARKERS):
                        raise _invalid_docx()
                    if (
                        lowered_name.endswith(".rels")
                        and b'targetmode="external"' in lowered_content
                    ):
                        external_relationship = True
            content_types = archive.read("[Content_Types].xml").lower()
            if b"macroenabled" in content_types or b"vbaproject" in content_types:
                raise _invalid_docx()
    except ResumeImportError:
        raise
    except (BadZipFile, KeyError, OSError, ValueError) as error:
        raise _invalid_docx() from error
    return (
        (ResumeImportWarning("EXTERNAL_RELATIONSHIP_IGNORED", "已忽略 DOCX 外部关系"),)
        if external_relationship
        else ()
    )


def _body_blocks(document, started_at: float) -> list[DocumentBlock]:
    blocks: list[DocumentBlock] = []
    for child in document.element.body.iterchildren():
        _check_timeout(started_at)
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            blocks.extend(
                DocumentBlock(DocumentBlockKind.TEXT, line.strip())
                for line in paragraph.text.splitlines()
                if line.strip()
            )
        elif child.tag == qn("w:tbl"):
            table = Table(child, document)
            for row in table.rows:
                cells = [" ".join(cell.text.split()) for cell in row.cells if cell.text.strip()]
                if cells:
                    blocks.append(DocumentBlock(DocumentBlockKind.TABLE_ROW, " | ".join(cells)))
    return blocks


def _check_timeout(started_at: float) -> None:
    if monotonic() - started_at > RESUME_PARSE_TIMEOUT_SECONDS:
        raise ResumeImportError(
            "RESUME_PARSE_TIMEOUT", "本机解析耗时超过安全限制，请换用更简单的文件"
        )


def _invalid_docx() -> ResumeImportError:
    return ResumeImportError("RESUME_DOCX_INVALID", "DOCX 文件无效或超出安全解析限制")
