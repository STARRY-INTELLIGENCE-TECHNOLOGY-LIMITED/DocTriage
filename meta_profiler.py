from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from config import Settings

CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")
HEADER_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s", re.MULTILINE)
WORD_PATTERN = re.compile(r"\w+")


@dataclass(slots=True)
class DocumentProfile:
    file_name: str
    file_suffix: str
    file_size_bytes: int
    created_at: str
    modified_at: str
    ctime_mtime_span_seconds: float
    header_density: float
    header_count: int
    non_empty_lines: int
    code_to_text_ratio: float
    code_block_count: int
    pdf_author: str | None = None
    pdf_producer: str | None = None
    extraction_notes: list[str] = field(default_factory=list)

    def to_llm_payload(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "file_suffix": self.file_suffix,
            "file_size_bytes": self.file_size_bytes,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "ctime_mtime_span_days": round(
                self.ctime_mtime_span_seconds / 86400, 2
            ),
            "header_density": self.header_density,
            "header_count": self.header_count,
            "non_empty_lines": self.non_empty_lines,
            "code_to_text_ratio": self.code_to_text_ratio,
            "code_block_count": self.code_block_count,
            "pdf_author": self.pdf_author,
            "pdf_producer": self.pdf_producer,
            "extraction_notes": self.extraction_notes,
        }


class MetadataProfiler:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    def profile_document(
        self, file_path: str | Path, clean_markdown: str
    ) -> DocumentProfile:
        path = Path(file_path).expanduser().resolve()
        stat = path.stat()
        non_empty_lines = [line for line in clean_markdown.splitlines() if line.strip()]
        header_count = len(HEADER_PATTERN.findall(clean_markdown))

        code_segments = CODE_BLOCK_PATTERN.findall(clean_markdown)
        code_chars = sum(len(segment) for segment in code_segments)
        code_chars += sum(
            len(match.group(0)) for match in INLINE_CODE_PATTERN.finditer(clean_markdown)
        )

        markdown_without_code = CODE_BLOCK_PATTERN.sub(" ", clean_markdown)
        text_chars = sum(len(word) for word in WORD_PATTERN.findall(markdown_without_code))
        code_to_text_ratio = round(code_chars / max(text_chars, 1), 4)

        extraction_notes: list[str] = []
        pdf_author: str | None = None
        pdf_producer: str | None = None

        if path.suffix.lower() == ".pdf" and self._pdf_metadata_enabled:
            try:
                reader = PdfReader(str(path))
                metadata = reader.metadata or {}
                pdf_author = self._normalize_pdf_value(
                    metadata.get("/Author") or getattr(metadata, "author", None)
                )
                pdf_producer = self._normalize_pdf_value(
                    metadata.get("/Producer") or getattr(metadata, "producer", None)
                )
            except Exception as exc:
                extraction_notes.append(
                    f"pdf_metadata_unavailable:{exc.__class__.__name__}"
                )

        profile = DocumentProfile(
            file_name=path.name,
            file_suffix=path.suffix.lower(),
            file_size_bytes=stat.st_size,
            created_at=self._to_iso(stat.st_ctime),
            modified_at=self._to_iso(stat.st_mtime),
            ctime_mtime_span_seconds=max(0.0, stat.st_mtime - stat.st_ctime),
            header_density=round(header_count / max(len(non_empty_lines), 1), 4),
            header_count=header_count,
            non_empty_lines=len(non_empty_lines),
            code_to_text_ratio=code_to_text_ratio,
            code_block_count=len(code_segments),
            pdf_author=pdf_author,
            pdf_producer=pdf_producer,
            extraction_notes=extraction_notes,
        )
        return profile

    @property
    def _pdf_metadata_enabled(self) -> bool:
        if self.settings is None:
            return True
        return self.settings.PDF_METADATA_ENABLED

    @staticmethod
    def _to_iso(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()

    @staticmethod
    def _normalize_pdf_value(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
