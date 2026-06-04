from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import normalize_citation_text, normalize_pair, tokenize


def build_citation_text(record: Any) -> str:
    path_text = read_plain_citation_text(record.source_path)
    parts = [
        record.relative_path,
        Path(record.relative_path).stem,
        record.reason,
        record.summary,
        path_text,
    ]
    return normalize_citation_text(" ".join(part for part in parts if part))


def read_plain_citation_text(path: Path, max_chars: int = 12000) -> str:
    if path.suffix.lower() not in {".md", ".txt", ".csv", ".html", ".htm"}:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except OSError:
        return ""


def collect_citation_pairs(records: list[Any]) -> dict[tuple[int, int], int]:
    alias_index = build_alias_index(records)
    citation_pairs: dict[tuple[int, int], int] = defaultdict(int)
    if not alias_index:
        return citation_pairs

    for source_index, record in enumerate(records):
        if not record.citation_text:
            continue
        for alias, target_index in alias_index.items():
            if source_index == target_index:
                continue
            if alias in record.citation_text:
                citation_pairs[normalize_pair(source_index, target_index)] += 1
    return dict(citation_pairs)


def build_alias_index(records: list[Any]) -> dict[str, int]:
    alias_index: dict[str, int] = {}
    ambiguous: set[str] = set()
    for index, record in enumerate(records):
        for alias in build_aliases(record):
            existing = alias_index.get(alias)
            if existing is not None and existing != index:
                ambiguous.add(alias)
                continue
            alias_index[alias] = index
    for alias in ambiguous:
        alias_index.pop(alias, None)
    return alias_index


def build_aliases(record: Any) -> set[str]:
    stem = Path(record.relative_path).stem
    normalized_name = str(getattr(record, "normalized_name", "")) or stem
    candidates = {
        stem,
        normalized_name,
        record.relative_path,
    }
    aliases: set[str] = set()
    for candidate in candidates:
        normalized = normalize_citation_text(candidate)
        if is_usable_alias(normalized):
            aliases.add(normalized)
    return aliases


def is_usable_alias(value: str) -> bool:
    if len(value) < 6:
        return False
    tokens = tokenize(value)
    if len(tokens) == 1 and len(tokens[0]) < 8:
        return False
    return value not in {"untitled", "document", "notes", "summary"}
