from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import shutil
import subprocess
import sys
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RAG_REDACTION_TERMS_ENV = "DOCTRIAGE_RAG_REDACT_TERMS"
RAG_REDACTION_MAPPINGS_ENV = "DOCTRIAGE_RAG_REDACT_MAPPINGS"
RAG_REDACTION_PLACEHOLDER_ENV = "DOCTRIAGE_RAG_REDACT_PLACEHOLDER"
RAG_REDACTION_DROP_ENV = "DOCTRIAGE_RAG_REDACT_DROP_MATCHED_DOCUMENTS"

from config import DEFAULT_SUPPORTED_EXTENSIONS, Settings
from bundle_exporter import (
    BundleSelection,
    export_bundle,
    load_latest_decisions as load_bundle_decisions,
    select_documents,
)
from runtime_encoding import (
    configure_utf8_runtime,
    decode_process_output,
    utf8_subprocess_env,
)
from reading_tracker import (
    MARKABLE_STATUSES,
    ReadingPaths,
    append_reading_event,
    build_reading_rows,
    filter_rows,
    load_latest_decisions,
    load_latest_reading_events,
    materialized_target_path,
    parse_categories,
)
from ollama_runtime import models_are_same, resolve_ollama_runtime_endpoint
from rag_vector_store import inspect_qdrant_local_index, normalize_vector_store_type


@dataclass(slots=True)
class ManagedProcessTask:
    process: subprocess.Popen
    command: list[str] | None
    kind: str | None = None
    started_epoch: float | None = None
    cleanup_started: bool = False


@dataclass(slots=True)
class AppState:
    paths: ReadingPaths | None = None
    process: subprocess.Popen | None = None
    process_command: list[str] | None = None
    process_started_epoch: float | None = None
    relationship_process: subprocess.Popen | None = None
    relationship_process_kind: str | None = None
    relationship_process_command: list[str] | None = None
    rag_process: subprocess.Popen | None = None
    rag_process_kind: str | None = None
    rag_process_command: list[str] | None = None
    analysis_tasks: dict[str, ManagedProcessTask] = field(default_factory=dict)
    relationship_tasks: dict[str, ManagedProcessTask] = field(default_factory=dict)
    rag_tasks: dict[str, ManagedProcessTask] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


SOURCE_FILE_SCAN_CACHE_TTL_SECONDS = 2.0
_SOURCE_FILE_SCAN_CACHE: dict[Path, tuple[float, list[Path]]] = {}
_SOURCE_FILE_SCAN_CACHE_LOCK = threading.Lock()
DEFAULT_LLM_ENDPOINT = "http://localhost:11434/api/generate"
DEFAULT_EMBEDDING_ENDPOINT = "http://localhost:11434/api/embeddings"
DEFAULT_ANYDOCS_URL = "http://127.0.0.1:18766/"
ANYDOCS_GITHUB_URL = (
    "https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/AnyDocsToAgents"
)
ANYDOCS_PROBE_TIMEOUT_SECONDS = 2.0
HTTP_PROBE_TIMEOUT_SECONDS = 5.0
HTTP_PROBE_MAX_BYTES = 1024 * 1024
UPLOAD_WORKSPACE_ROOT = PROJECT_ROOT / ".doctriage_uploads"
UPLOAD_MANIFEST_NAME = "manifest.json"
SUBPROCESS_POPEN_TYPE = subprocess.Popen
COMPLETED_TASK_PROCESS_GRACE_SECONDS = 30.0
TASK_WATCH_POLL_SECONDS = 2.0

if os.name == "nt":
    MANAGED_PROCESS_CREATIONFLAGS = subprocess.CREATE_NO_WINDOW
else:
    MANAGED_PROCESS_CREATIONFLAGS = 0


UI_PACKAGE = "doctriage_ui"
UI_INDEX_ASSET = "index.html"
UI_STATIC_ASSETS: dict[str, tuple[str, str]] = {
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "application/javascript; charset=utf-8"),
}
UI_ASSET_NAMES = (UI_INDEX_ASSET, "app.css", "app.js")


def _load_ui_asset_bytes(asset_name: str) -> bytes:
    return resources.files(UI_PACKAGE).joinpath(asset_name).read_bytes()


_RAW_UI_ASSET_BYTES = {
    asset_name: _load_ui_asset_bytes(asset_name) for asset_name in UI_ASSET_NAMES
}
UI_ASSET_VERSION = hashlib.sha256(
    b"".join(_RAW_UI_ASSET_BYTES[asset_name] for asset_name in UI_ASSET_NAMES)
).hexdigest()[:12]


def _version_index_asset(content: bytes) -> bytes:
    version = f"?v={UI_ASSET_VERSION}".encode("ascii")
    return (
        content.replace(b'/assets/app.css"', b"/assets/app.css" + version + b'"')
        .replace(b'/assets/app.js"', b"/assets/app.js" + version + b'"')
    )


UI_ASSET_BYTES = dict(_RAW_UI_ASSET_BYTES)
UI_ASSET_BYTES[UI_INDEX_ASSET] = _version_index_asset(
    _RAW_UI_ASSET_BYTES[UI_INDEX_ASSET]
)
UI_ASSET_TEXT = {
    asset_name: content.decode("utf-8")
    for asset_name, content in UI_ASSET_BYTES.items()
}


def read_ui_asset_text(asset_name: str) -> str:
    return UI_ASSET_TEXT[asset_name]


HTML_PAGE = read_ui_asset_text(UI_INDEX_ASSET)
HTML_PAGE_BYTES = UI_ASSET_BYTES[UI_INDEX_ASSET]


def read_ui_frontend_source() -> str:
    return "\n".join(
        read_ui_asset_text(asset_name) for asset_name in UI_ASSET_NAMES
    )


def build_state_payload(paths: ReadingPaths, query: dict[str, str]) -> dict[str, Any]:
    scope = normalize_reading_scope(query.get("scope"))
    try:
        decisions = load_latest_decisions(paths.decisions_path)
    except FileNotFoundError:
        decisions = {}
    events = load_latest_reading_events(paths.reading_status_path)
    reading_rows = decorate_reading_rows(build_reading_rows(decisions, events))
    failure_rows = build_failure_rows(paths)
    if scope == "source":
        rows = build_source_file_rows(paths, decisions, events, reading_rows, failure_rows)
    else:
        rows = reading_rows + failure_rows
    status_counts = count_by(rows, "status")
    if scope == "source":
        filtered = filter_source_scope_rows(rows, status=query.get("status") or None)
    else:
        filtered = filter_rows(
            reading_rows,
            status=query.get("status") or None,
            min_quality=parse_int(query.get("min_quality"), 0),
            categories=parse_categories(query.get("categories")),
            max_sensitivity_risk=parse_optional_int(query.get("max_sensitivity_risk")),
            min_public_writing_suitability=parse_optional_int(
                query.get("min_public_writing_suitability")
            ),
        )
        if not query.get("status") or query.get("status") == "failed":
            filtered.extend(failure_rows)
    q = (query.get("q") or "").strip().lower()
    if q:
        filtered = [row for row in filtered if row_matches_query(row, q)]
    filtered = sort_rows(filtered, query.get("sort") or default_sort_for_scope(scope))

    filtered_count = len(filtered)
    page_size = parse_optional_int(query.get("page_size") or query.get("limit"))
    page = max(1, parse_int(query.get("page"), 1))
    limit = parse_optional_int(query.get("limit"))
    if limit is not None:
        filtered = filtered[:limit]

    return {
        "scope": scope,
        "total_count": len(rows),
        "filtered_count": filtered_count,
        "status_counts": status_counts,
        "available_categories": sorted(
            {str(row.get("category") or "") for row in rows if row.get("category")}
        ),
        "available_topic_tags": sorted(
            {
                str(tag)
                for row in rows
                for tag in (row.get("topic_tags") or [])
                if tag
            }
        ),
        "page": page,
        "page_size": page_size,
        "rows": filtered,
    }


def normalize_reading_scope(value: str | None) -> str:
    return "source" if value == "source" else "analysis"


def default_sort_for_scope(scope: str) -> str:
    return "source_path_asc" if scope == "source" else "quality_desc"


def decorate_reading_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [decorate_analysis_row(row) for row in rows]


def decorate_analysis_row(row: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(row)
    source_path = Path(str(decorated.get("source_path") or ""))
    metadata = source_metadata_for_row(source_path, decorated)
    decorated.update(metadata)
    decorated["analyzed"] = True
    decorated["source_only"] = False
    decorated["failure"] = False
    decorated["exists"] = bool(metadata.get("exists"))
    return decorated


def build_source_file_rows(
    paths: ReadingPaths,
    decisions: dict[str, dict[str, Any]],
    events: dict[str, dict[str, Any]],
    reading_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_relative: dict[str, dict[str, Any]] = {}
    reading_by_relative: dict[str, dict[str, Any]] = {
        str(row.get("relative_path") or ""): dict(row)
        for row in reading_rows
        if row.get("relative_path")
    }
    failures_by_relative = {
        str(row.get("relative_path") or ""): row
        for row in failure_rows
        if row.get("relative_path")
    }

    for source_path in iter_supported_source_files(paths.source_dir):
        relative_path = source_relative_path(paths, source_path)
        if not relative_path:
            continue
        row = reading_by_relative.get(relative_path)
        if row is None:
            row = build_source_only_row(paths, source_path, relative_path, events)
        else:
            row = dict(row)
            row.update(source_metadata_for_row(source_path, row))
        failure_row = failures_by_relative.pop(relative_path, None)
        if failure_row:
            row = merge_failure_into_source_row(row, failure_row)
        row["source_scope"] = True
        rows_by_relative[relative_path] = row

    for relative_path, row in failures_by_relative.items():
        source_text = str(row.get("source_path") or "")
        source_path = Path(source_text) if source_text else None
        if source_path is None or not source_path.exists():
            continue
        source_relative = source_relative_path(paths, source_path)
        if not source_relative:
            continue
        source_row = build_source_only_row(paths, source_path, source_relative, events)
        source_row = merge_failure_into_source_row(source_row, row)
        source_row["source_scope"] = True
        rows_by_relative[source_relative] = source_row

    return list(rows_by_relative.values())


def iter_supported_source_files(source_dir: Path) -> list[Path]:
    try:
        cache_key = source_dir.expanduser().resolve()
    except OSError:
        return []
    now = time.monotonic()
    with _SOURCE_FILE_SCAN_CACHE_LOCK:
        cached = _SOURCE_FILE_SCAN_CACHE.get(cache_key)
        if cached is not None:
            cached_at, cached_files = cached
            if now - cached_at <= SOURCE_FILE_SCAN_CACHE_TTL_SECONDS:
                return list(cached_files)

    extensions = {suffix.lower() for suffix in DEFAULT_SUPPORTED_EXTENSIONS}
    files: list[Path] = []
    try:
        if not cache_key.exists():
            return []
        iterator = cache_key.rglob("*")
        for path in iterator:
            try:
                if path.is_file() and path.suffix.lower() in extensions:
                    files.append(path)
            except OSError:
                continue
    except OSError:
        return files
    with _SOURCE_FILE_SCAN_CACHE_LOCK:
        _SOURCE_FILE_SCAN_CACHE[cache_key] = (now, list(files))
    return files


def clear_source_file_scan_cache(source_dir: Path | None = None) -> None:
    with _SOURCE_FILE_SCAN_CACHE_LOCK:
        if source_dir is None:
            _SOURCE_FILE_SCAN_CACHE.clear()
            return
        try:
            cache_key = source_dir.expanduser().resolve()
        except OSError:
            cache_key = source_dir
        _SOURCE_FILE_SCAN_CACHE.pop(cache_key, None)


def build_source_only_row(
    paths: ReadingPaths,
    source_path: Path,
    relative_path: str,
    events: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    event = events.get(relative_path)
    status = str(event.get("status") if event else "unread")
    if status not in MARKABLE_STATUSES:
        status = "unread"
    metadata = source_metadata_for_row(source_path, {})
    return {
        "relative_path": relative_path,
        "display_name": source_path.name,
        "source_path": str(source_path),
        "target_path": "",
        "status": status,
        "marked_status": status,
        "updated_at": str(event.get("updated_at") if event else ""),
        "quality": None,
        "category": "",
        "document_kind": "Unscored",
        "topic_tags": [],
        "sensitivity_risk": None,
        "public_writing_suitability": None,
        "summary": "",
        "note": str(event.get("note") if event else ""),
        "analyzed": False,
        "source_only": True,
        "failure": False,
        **metadata,
    }


def merge_failure_into_source_row(
    row: dict[str, Any], failure_row: dict[str, Any]
) -> dict[str, Any]:
    merged = dict(row)
    if not merged.get("updated_at"):
        merged["status"] = "failed"
        merged["marked_status"] = "failed"
    merged["failure"] = True
    merged["analysis_failure"] = True
    merged["source_only"] = bool(not merged.get("analyzed"))
    for key in (
        "failure_stage",
        "failure_reason",
        "failure_error",
        "attempts",
        "summary",
        "note",
    ):
        merged[key] = failure_row.get(key)
    merged["category"] = failure_row.get("category") or merged.get("category") or ""
    merged["document_kind"] = (
        failure_row.get("document_kind") or merged.get("document_kind") or ""
    )
    merged["topic_tags"] = failure_row.get("topic_tags") or merged.get("topic_tags") or []
    return merged


def filter_source_scope_rows(
    rows: list[dict[str, Any]], *, status: str | None
) -> list[dict[str, Any]]:
    if not status:
        return list(rows)
    return [row for row in rows if row.get("status") == status]


def source_relative_path(paths: ReadingPaths, source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(paths.source_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def source_metadata_for_row(source_path: Path, row: dict[str, Any]) -> dict[str, Any]:
    stat_payload = stat_source_file(source_path)
    source_size_bytes = first_present_int(
        row.get("source_size_bytes"),
        nested_fingerprint_value(row, "size_bytes"),
        stat_payload.get("source_size_bytes"),
    )
    source_mtime_ns = first_present_int(
        row.get("source_mtime_ns"),
        nested_fingerprint_value(row, "mtime_ns"),
        stat_payload.get("source_mtime_ns"),
    )
    source_ctime_ns = first_present_int(
        row.get("source_ctime_ns"),
        nested_fingerprint_value(row, "ctime_ns"),
        stat_payload.get("source_ctime_ns"),
    )
    metadata = {
        **stat_payload,
        "source_size_bytes": source_size_bytes,
        "source_size_label": format_size(source_size_bytes or 0),
        "source_mtime_ns": source_mtime_ns,
        "source_ctime_ns": source_ctime_ns,
        "source_mtime_epoch": ns_to_epoch(source_mtime_ns),
        "source_mtime": ns_to_iso(source_mtime_ns),
        "source_mtime_label": ns_to_local_label(source_mtime_ns),
    }
    if not stat_payload.get("exists") and row.get("source_mtime"):
        metadata["source_mtime"] = str(row.get("source_mtime") or "")
    return metadata


def stat_source_file(source_path: Path) -> dict[str, Any]:
    if not source_path.exists() or source_path.is_dir():
        return {
            "exists": False,
            "source_size_bytes": 0,
            "source_mtime_ns": None,
            "source_ctime_ns": None,
        }
    try:
        stat = source_path.stat()
    except OSError:
        return {
            "exists": False,
            "source_size_bytes": 0,
            "source_mtime_ns": None,
            "source_ctime_ns": None,
        }
    return {
        "exists": True,
        "source_size_bytes": stat.st_size,
        "source_mtime_ns": stat.st_mtime_ns,
        "source_ctime_ns": stat.st_ctime_ns,
    }


def nested_fingerprint_value(row: dict[str, Any], key: str) -> Any:
    fingerprint = row.get("fingerprint")
    if isinstance(fingerprint, dict):
        return fingerprint.get(key)
    return None


def first_present_int(*values: Any) -> int | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def ns_to_epoch(value: int | None) -> float | None:
    if value is None:
        return None
    return value / 1_000_000_000


def ns_to_iso(value: int | None) -> str:
    epoch = ns_to_epoch(value)
    if epoch is None:
        return ""
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def ns_to_local_label(value: int | None) -> str:
    epoch = ns_to_epoch(value)
    if epoch is None:
        return ""
    return datetime.fromtimestamp(epoch, timezone.utc).astimezone().strftime(
        "%Y-%m-%d %H:%M"
    )


def failed_files_path(paths: ReadingPaths) -> Path:
    return paths.output_root / "_state" / "failed_files.jsonl"


def processed_files_path(paths: ReadingPaths) -> Path:
    return paths.output_root / "_state" / "processed_files.jsonl"


def build_failure_rows(paths: ReadingPaths) -> list[dict[str, Any]]:
    path = failed_files_path(paths)
    if not path.exists():
        return []

    recovered_sources = load_processed_source_keys(processed_files_path(paths))
    rows_by_source: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            source_text = str(record.get("source_path") or "").strip()
            if not source_text:
                continue
            source_path = Path(source_text)
            source_key = source_path_key(source_path)
            if source_key in recovered_sources:
                continue

            row = rows_by_source.get(source_key)
            if row is None:
                row = build_failure_row_base(paths, source_path)
                rows_by_source[source_key] = row
            row["attempts"] = int(row.get("attempts") or 0) + 1
            row["failure_stage"] = str(record.get("stage") or "")
            row["failure_error"] = str(record.get("error") or "")
            row["failure_reason"] = failure_reason_category(row["failure_error"])
            row["category"] = row["failure_reason"]
            row["document_kind"] = row["failure_stage"] or "failure"
            row["topic_tags"] = [
                item
                for item in ("失败", row["failure_stage"], row["failure_reason"])
                if item
            ]
            row["summary"] = row["failure_error"]
            row["note"] = failure_note(row)

    return sorted(
        rows_by_source.values(),
        key=lambda row: (
            str(row.get("failure_reason") or ""),
            str(row.get("failure_stage") or ""),
            str(row.get("relative_path") or ""),
        ),
    )


def load_processed_source_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            source_text = str(record.get("source_path") or "").strip()
            if not source_text:
                continue
            path_obj = Path(source_text)
            keys.add(source_text)
            keys.add(source_path_key(path_obj))
    return keys


def source_path_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def build_failure_row_base(paths: ReadingPaths, source_path: Path) -> dict[str, Any]:
    relative_path = failure_relative_path(paths, source_path)
    exists = source_path.exists()
    is_dir = exists and source_path.is_dir()
    size_bytes = 0
    if exists and not is_dir:
        try:
            size_bytes = source_path.stat().st_size
        except OSError:
            size_bytes = 0
    metadata = source_metadata_for_row(source_path, {})
    return {
        **metadata,
        "relative_path": relative_path,
        "display_name": source_path.name or relative_path,
        "source_path": str(source_path),
        "target_path": "",
        "status": "failed",
        "marked_status": "failed",
        "updated_at": "",
        "quality": 0,
        "category": "失败文件",
        "document_kind": "failure",
        "topic_tags": ["失败"],
        "sensitivity_risk": 0,
        "public_writing_suitability": 0,
        "summary": "",
        "note": "",
        "failure": True,
        "failure_stage": "",
        "failure_reason": "其他",
        "failure_error": "",
        "attempts": 0,
        "exists": exists,
        "is_dir": is_dir,
        "size_bytes": size_bytes,
        "size_label": failure_size_label(exists, is_dir, size_bytes),
    }


def failure_relative_path(paths: ReadingPaths, source_path: Path) -> str:
    try:
        return source_path.resolve().relative_to(paths.source_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return source_path.name or str(source_path)


def failure_size_label(exists: bool, is_dir: bool, size_bytes: int) -> str:
    if not exists:
        return "不存在"
    if is_dir:
        return "目录"
    return format_size(size_bytes)


def format_size(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def failure_note(row: dict[str, Any]) -> str:
    parts = [
        f"阶段：{row.get('failure_stage') or 'unknown'}",
        f"原因：{row.get('failure_reason') or '其他'}",
        f"尝试：{row.get('attempts') or 0}",
        f"大小：{row.get('size_label') or ''}",
    ]
    error = str(row.get("failure_error") or "").strip()
    if error:
        parts.append(f"错误：{error}")
    return "；".join(parts)


def failure_reason_category(error: str) -> str:
    text = error.lower()
    if "legacy .ppt ingestion requires libreoffice" in text:
        return "旧 PPT 需 LibreOffice"
    if "pdf text fallback produced empty text" in text:
        return "PDF 无文本层/需 OCR"
    if "input document is empty" in text:
        return "空文件"
    if "file format not allowed" in text:
        return "格式不支持/文件异常"
    if "cryptography>=3.1 is required for aes algorithm" in text:
        return "加密 PDF 依赖缺失"
    if "not valid" in text:
        return "Office 文件无效"
    return "其他"


def relationship_dir(paths: ReadingPaths) -> Path:
    return paths.output_root / "_relationships"


def relationship_clusters_path(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "clusters.json"


def relationship_relations_path(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "relations.jsonl"


def relationship_embedding_progress_path(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "embedding_progress.json"


def relationship_progress_path(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "progress.json"


def relationship_outputs_complete_after(
    paths: ReadingPaths, started_epoch: float | None
) -> bool:
    if not started_epoch or started_epoch <= 0:
        return False
    relation_path = relationship_relations_path(paths)
    cluster_path = relationship_clusters_path(paths)
    return (
        file_modified_after(relation_path, started_epoch)
        and file_modified_after(cluster_path, started_epoch)
    )


def file_modified_after(path: Path, started_epoch: float) -> bool:
    try:
        return path.exists() and path.stat().st_mtime >= started_epoch - 1
    except OSError:
        return False


def rag_dir(paths: ReadingPaths) -> Path:
    return paths.output_root / "_rag"


def rag_documents_path(paths: ReadingPaths) -> Path:
    return rag_dir(paths) / "documents.jsonl"


def rag_chunks_path(paths: ReadingPaths) -> Path:
    return rag_dir(paths) / "chunks.jsonl"


def rag_vectors_path(paths: ReadingPaths) -> Path:
    return rag_dir(paths) / "vectors.jsonl"


def rag_manifest_path(paths: ReadingPaths) -> Path:
    return rag_dir(paths) / "manifest.json"


def rag_progress_path(paths: ReadingPaths) -> Path:
    return rag_dir(paths) / "progress.json"


def rag_log_path(paths: ReadingPaths) -> Path:
    return rag_dir(paths) / "rag.log"


def coerce_int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_string_list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def load_relationship_clusters(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return []
    clusters = payload.get("clusters")
    if not isinstance(clusters, list):
        return []
    return [cluster for cluster in clusters if isinstance(cluster, dict)]


def build_relationship_payload(
    app_state: AppState, paths: ReadingPaths, query: dict[str, str]
) -> dict[str, Any]:
    clusters = load_relationship_clusters(relationship_clusters_path(paths))
    summaries = [
        build_cluster_summary(index, cluster) for index, cluster in enumerate(clusters)
    ]
    cluster_id = parse_optional_int(query.get("cluster"))
    selected_cluster = None
    if cluster_id is not None and 0 <= cluster_id < len(clusters):
        selected_cluster = build_cluster_payload(paths, cluster_id, clusters[cluster_id])
    return {
        "available": bool(clusters),
        "decisions_exists": paths.decisions_path.exists(),
        "clusters_exists": relationship_clusters_path(paths).exists(),
        "relations_exists": relationship_relations_path(paths).exists(),
        "cluster_count": len(clusters),
        "clusters": summaries,
        "selected_cluster": selected_cluster,
        "task": relationship_task_status(app_state, paths),
        "progress": read_json_file(relationship_progress_path(paths)),
        "embedding_progress": read_json_file(relationship_embedding_progress_path(paths)),
        "log_tail": read_text_tail(paths.application_log_path, max_lines=80),
    }


def build_cluster_summary(cluster_id: int, cluster: dict[str, Any]) -> dict[str, Any]:
    files = [item for item in cluster.get("files") or [] if isinstance(item, dict)]
    preview_paths = [
        str(item.get("relative_path") or "")
        for item in files[:3]
        if str(item.get("relative_path") or "")
    ]
    return {
        "cluster_id": cluster_id,
        "size": coerce_int_value(cluster.get("size"), len(files)),
        "categories": sorted(
            {str(category) for category in cluster.get("categories") or [] if str(category)}
        ),
        "preview_paths": preview_paths,
    }


def build_cluster_payload(
    paths: ReadingPaths, cluster_id: int, cluster: dict[str, Any]
) -> dict[str, Any]:
    decisions = load_latest_decisions(paths.decisions_path)
    events = load_latest_reading_events(paths.reading_status_path)
    rows_by_path = {
        str(row.get("relative_path") or ""): row
        for row in build_reading_rows(decisions, events)
    }
    cluster_files = [item for item in cluster.get("files") or [] if isinstance(item, dict)]
    files: list[dict[str, Any]] = []
    member_paths: set[str] = set()
    for item in cluster_files:
        relative_path = str(item.get("relative_path") or "")
        if not relative_path:
            continue
        row = rows_by_path.get(relative_path, {})
        decision = decisions.get(relative_path, {})
        files.append(
            {
                "relative_path": relative_path,
                "status": str(row.get("status") or "unread"),
                "quality": coerce_int_value(
                    row.get("quality"), coerce_int_value(item.get("quality"), 0)
                ),
                "category": str(row.get("category") or item.get("category") or ""),
                "document_kind": str(
                    row.get("document_kind") or item.get("document_kind") or "Unknown"
                ),
                "topic_tags": coerce_string_list_value(
                    row.get("topic_tags") or item.get("topic_tags")
                ),
                "sensitivity_risk": coerce_int_value(row.get("sensitivity_risk"), 0),
                "public_writing_suitability": coerce_int_value(
                    row.get("public_writing_suitability"), 0
                ),
                "note": str(row.get("note") or ""),
                "source_path": str(row.get("source_path") or decision.get("source_path") or ""),
                "target_path": str(row.get("target_path") or materialized_target_path(decision)),
                "summary": str(decision.get("summary") or ""),
            }
        )
        member_paths.add(relative_path)

    edges = load_cluster_edges(relationship_relations_path(paths), member_paths)
    return {
        "cluster_id": cluster_id,
        "size": coerce_int_value(cluster.get("size"), len(files)),
        "categories": sorted(
            {str(category) for category in cluster.get("categories") or [] if str(category)}
        ),
        "files": files,
        "edge_count": len(edges),
        "edges": edges,
    }


def load_cluster_edges(path: Path, member_paths: set[str]) -> list[dict[str, Any]]:
    if not path.exists() or not member_paths:
        return []

    edges: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            left = payload.get("left")
            right = payload.get("right")
            if not isinstance(left, dict) or not isinstance(right, dict):
                continue
            left_path = str(left.get("relative_path") or "")
            right_path = str(right.get("relative_path") or "")
            if not left_path or not right_path:
                continue
            if left_path not in member_paths or right_path not in member_paths:
                continue
            edges.append(
                {
                    "left_path": left_path,
                    "right_path": right_path,
                    "relation_score": round(
                        coerce_float_value(payload.get("relation_score"), 0.0), 4
                    ),
                    "signals": coerce_string_list_value(payload.get("signals")),
                    "filename_similarity": round(
                        coerce_float_value(payload.get("filename_similarity"), 0.0), 4
                    ),
                    "time_proximity": round(
                        coerce_float_value(payload.get("time_proximity"), 0.0), 4
                    ),
                    "path_proximity": round(
                        coerce_float_value(payload.get("path_proximity"), 0.0), 4
                    ),
                    "embedding_similarity": round(
                        coerce_float_value(payload.get("embedding_similarity"), 0.0), 4
                    ),
                    "type_compatibility": round(
                        coerce_float_value(payload.get("type_compatibility"), 0.0), 4
                    ),
                    "citation_count": coerce_int_value(payload.get("citation_count"), 0),
                }
            )

    edges.sort(key=lambda edge: edge["relation_score"], reverse=True)
    return edges


def relationship_task_status(
    app_state: AppState, paths: ReadingPaths | None = None
) -> dict[str, Any]:
    with app_state.lock:
        task = relationship_task_for_paths(app_state, paths)
        process = task.process if task is not None else None
        kind = task.kind if task is not None else None
        command = task.command if task is not None else None
        return_code = None if process is None else process.poll()
        relationship_outputs_complete = (
            paths is not None
            and process is not None
            and return_code is None
            and relationship_outputs_complete_after(paths, task.started_epoch if task is not None else None)
        )
        running = (
            process is not None
            and return_code is None
            and not relationship_outputs_complete
        )
        pid = process.pid if process is not None and not relationship_outputs_complete else None
        if relationship_outputs_complete:
            return_code = 0
        if relationship_outputs_complete:
            reap_completed_managed_process(
                app_state, paths, task, clear_relationship_task
            )
        if process is not None and return_code is not None:
            clear_relationship_task(app_state, paths, task)

        analysis_task = analysis_task_for_paths(app_state, paths)
        analysis_process = analysis_task.process if analysis_task is not None else None
        analysis_command = analysis_task.command if analysis_task is not None else None
        analysis_started_epoch = (
            analysis_task.started_epoch if analysis_task is not None else None
        )
        analysis_matches_paths = paths is None or paths_match_command(
            analysis_command, paths
        )
        analysis_return_code = (
            None
            if analysis_process is None or not analysis_matches_paths
            else analysis_process.poll()
        )
        analysis_running = (
            analysis_process is not None
            and analysis_return_code is None
            and analysis_matches_paths
        )
        analysis_pid = (
            analysis_process.pid
            if analysis_process is not None and analysis_matches_paths
            else None
        )
        if (
            analysis_process is not None
            and analysis_process.poll() is not None
            and analysis_matches_paths
        ):
            clear_analysis_task(app_state, paths, analysis_task)
            analysis_started_epoch = None
    payload = {
        "running": running,
        "pid": pid,
        "kind": kind,
        "command": command,
        "return_code": return_code,
        "source_dir": "" if paths is None else str(paths.source_dir),
        "output_root": "" if paths is None else str(paths.output_root),
    }
    if running or return_code is not None or paths is None or relationship_outputs_complete:
        return payload
    recorded_task = relationship_task_from_record(paths)
    if recorded_task is not None:
        return recorded_task
    progress = read_json_file(paths.progress_path)
    embedding_progress = read_json_file(relationship_embedding_progress_path(paths))
    lock_info = read_run_lock(run_lock_path(paths.output_root))
    active_pid = None if analysis_running else active_run_pid_from_lock_info(lock_info)
    active_started_epoch = (
        analysis_started_epoch
        if analysis_running
        else coerce_float_value(lock_info.get("created_epoch"), 0.0)
    )
    if paths is not None and relationship_outputs_complete_after(paths, active_started_epoch):
        return payload
    if inline_relationship_mining_is_active(
        running=analysis_running or active_pid is not None,
        command=analysis_command,
        log_tail=read_text_tail(paths.application_log_path, max_lines=80),
        progress=progress,
        embedding_progress=embedding_progress,
        active_started_epoch=active_started_epoch,
    ):
        return inline_relationship_task_payload(
            analysis_pid or active_pid,
            analysis_command,
            embedding_progress,
            paths=paths,
        )
    return payload


def inline_relationship_mining_is_active(
    *,
    running: bool,
    command: list[str] | None,
    log_tail: str,
    progress: dict[str, Any] | None = None,
    embedding_progress: dict[str, Any] | None = None,
    active_started_epoch: float | None = None,
) -> bool:
    if not running:
        return False
    known_relationship_command = bool(command and "--mine-relationships" in command)
    if command and not known_relationship_command:
        return False
    if relationship_log_marker_is_active(log_tail, active_started_epoch):
        return True
    if relationship_embedding_progress_is_active(
        embedding_progress,
        active_started_epoch=active_started_epoch,
    ) and (
        known_relationship_command or analysis_progress_is_complete(progress)
    ):
        return True
    return known_relationship_command and analysis_progress_is_complete(progress)


def relationship_log_marker_is_active(
    log_tail: str, active_started_epoch: float | None = None
) -> bool:
    start_index = log_tail.rfind("Starting relationship mining")
    complete_index = log_tail.rfind("Relationship mining completed")
    if start_index <= complete_index:
        return False
    if active_started_epoch is None or active_started_epoch <= 0:
        return True
    start_epoch = log_line_epoch_for_index(log_tail, start_index)
    if start_epoch is None:
        return False
    return start_epoch >= active_started_epoch - 2


def log_line_epoch_for_index(log_tail: str, index: int) -> float | None:
    line_start = log_tail.rfind("\n", 0, index) + 1
    line = log_tail[line_start : log_tail.find("\n", index)]
    if not line:
        line = log_tail[line_start:]
    timestamp_text = line[:23]
    try:
        return datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S,%f").timestamp()
    except ValueError:
        return None


def analysis_progress_is_complete(progress: dict[str, Any] | None) -> bool:
    if not isinstance(progress, dict):
        return False
    total = coerce_int_value(progress.get("total"), 0)
    completed = coerce_int_value(progress.get("completed"), 0)
    remaining = coerce_int_value(progress.get("remaining"), 0)
    if total > 0:
        return remaining == 0 and completed >= total
    return completed > 0 and remaining == 0


def relationship_embedding_progress_is_active(
    progress: dict[str, Any] | None,
    *,
    active_started_epoch: float | None = None,
) -> bool:
    if not isinstance(progress, dict) or not bool(progress.get("enabled")):
        return False
    if active_started_epoch is not None and active_started_epoch > 0:
        updated_epoch = coerce_float_value(progress.get("updated_epoch"), 0.0)
        if updated_epoch and updated_epoch < active_started_epoch:
            return False
    phase = str(progress.get("phase") or "").strip().lower()
    return phase not in {"complete", "error"}


def inline_relationship_task_payload(
    pid: int | None,
    command: list[str] | None,
    embedding_progress: dict[str, Any] | None = None,
    paths: ReadingPaths | None = None,
) -> dict[str, Any]:
    task_command = list(command or [])
    if (
        "--relationship-use-embeddings" in task_command
        and "--use-embeddings" not in task_command
    ):
        task_command.append("--use-embeddings")
    if not task_command and (embedding_progress or {}).get("enabled"):
        task_command.append("--use-embeddings")
    return {
        "running": True,
        "pid": pid,
        "kind": "mine",
        "command": task_command,
        "return_code": None,
        "inline": True,
        "source_dir": "" if paths is None else str(paths.source_dir),
        "output_root": "" if paths is None else str(paths.output_root),
    }


def bundle_path_for_output(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "doctriage_bundle.json"


def build_anydocs_url(base_url: str, bundle_path: Path) -> str:
    url_text = str(base_url or DEFAULT_ANYDOCS_URL).strip() or DEFAULT_ANYDOCS_URL
    parsed = urllib.parse.urlparse(url_text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("AnyDocsToAgents URL must be an http(s) URL.")
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    query["doctriage_bundle_path"] = [str(bundle_path)]
    query.pop("autoplan", None)
    encoded_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path or "/",
            parsed.params,
            encoded_query,
            "view-planner",
        )
    )


def anydocs_probe_url(base_url: str) -> str:
    """Return the configured AnyDocsToAgents page without launch parameters."""
    parsed = urllib.parse.urlparse(str(base_url or DEFAULT_ANYDOCS_URL).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("AnyDocsToAgents URL must be an http(s) URL.")
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path or "/", parsed.params, "", "")
    )


def anydocs_service_available(base_url: str) -> bool:
    """Confirm that the configured endpoint serves the AnyDocsToAgents UI."""
    probe = http_json_request(
        anydocs_probe_url(base_url),
        timeout_seconds=ANYDOCS_PROBE_TIMEOUT_SECONDS,
    )
    status_code = probe.get("status_code")
    if not probe.get("reachable") or status_code is None:
        return False
    if not 200 <= int(status_code) < 400:
        return False
    return "anydocstoagents" in str(probe.get("text") or "").lower()


def export_bundle_for_anydocs(paths: ReadingPaths, payload: dict[str, Any]) -> Path:
    source_dir = paths.source_dir
    output_root = paths.output_root
    settings = Settings(
        LLM_ENDPOINT=str(payload.get("llm_endpoint") or DEFAULT_LLM_ENDPOINT),
        LLM_MODEL=str(payload.get("llm_model") or "") or None,
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    return export_bundle(
        settings,
        output_path=bundle_path_for_output(paths),
        selection=BundleSelection(
            min_quality=parse_quality_score(
                payload.get("bundle_min_quality", payload.get("min_quality")),
                default=0,
            ),
        ),
    )


def export_anydocs_bundle_request(
    app_state: AppState, payload: dict[str, Any]
) -> dict[str, Any]:
    paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
    bundle_path = export_bundle_for_anydocs(paths, payload)
    return {
        "exported": True,
        "bundle_path": str(bundle_path),
    }


def anydocs_bundle_quality_stats(
    app_state: AppState, query: dict[str, str]
) -> dict[str, Any]:
    paths = reading_paths_from_payload(app_state, query) or require_paths(app_state)
    decisions = load_bundle_decisions(paths.decisions_path)
    selection = BundleSelection(min_quality=0)
    documents = select_documents(
        decisions,
        selection,
    )
    histogram = [0] * 101
    for document in documents:
        scores = document.get("scores")
        quality = parse_quality_score(
            scores.get("quality") if isinstance(scores, dict) else 0,
            default=0,
        )
        histogram[quality] += 1
    return {
        "total": len(documents),
        "source_total": len(decisions),
        "excluded_category_count": sum(
            1
            for decision in decisions
            if str(decision.get("category") or "") in selection.exclude_categories
        ),
        "histogram": histogram,
        "excluded_categories": sorted(selection.exclude_categories),
    }


def open_anydocs_request(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
    bundle_path = bundle_path_for_output(paths)
    exported = False
    if bool(payload.get("export_bundle")):
        bundle_path = export_bundle_for_anydocs(paths, payload)
        exported = True
    base_url = str(payload.get("anydocs_url") or DEFAULT_ANYDOCS_URL)
    url = build_anydocs_url(base_url, bundle_path)
    if not anydocs_service_available(base_url):
        github_opened = bool(webbrowser.open_new_tab(ANYDOCS_GITHUB_URL))
        return {
            "opened": False,
            "service_available": False,
            "service_url": anydocs_probe_url(base_url),
            "github_opened": github_opened,
            "github_url": ANYDOCS_GITHUB_URL,
            "url": url,
            "bundle_path": str(bundle_path),
            "exported": exported,
        }
    if not bundle_path.exists():
        bundle_path = export_bundle_for_anydocs(paths, payload)
        exported = True
    url = build_anydocs_url(base_url, bundle_path)
    webbrowser.open(url)
    return {
        "opened": True,
        "service_available": True,
        "service_url": anydocs_probe_url(base_url),
        "url": url,
        "bundle_path": str(bundle_path),
        "exported": exported,
    }


def http_json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = HTTP_PROBE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    request_headers = dict(headers or {})
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read(HTTP_PROBE_MAX_BYTES)
            status_code = int(getattr(response, "status", response.getcode()))
            reachable = True
            error = ""
    except urllib.error.HTTPError as exc:
        raw = exc.read(HTTP_PROBE_MAX_BYTES)
        status_code = int(exc.code)
        reachable = True
        error = str(exc)
    except (OSError, TimeoutError, urllib.error.URLError, ValueError) as exc:
        return {
            "reachable": False,
            "status_code": None,
            "json": {},
            "text": "",
            "error": str(exc),
        }

    text = raw.decode("utf-8", errors="ignore")
    try:
        json_payload = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        json_payload = {}
    return {
        "reachable": reachable,
        "status_code": status_code,
        "json": json_payload,
        "text": text,
        "error": error,
    }


def endpoint_auth_headers(payload: dict[str, Any]) -> dict[str, str]:
    role = str(payload.get("role") or "").strip().lower()
    if role == "embedding":
        api_key = str(
            payload.get("embedding_api_key")
            or os.environ.get("EMBEDDING_API_KEY")
            or payload.get("api_key")
            or payload.get("llm_api_key")
            or os.environ.get("LLM_API_KEY")
            or ""
        ).strip()
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}
    api_key = str(
        payload.get("api_key")
        or payload.get("llm_api_key")
        or os.environ.get("LLM_API_KEY")
        or ""
    ).strip()
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def validate_http_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return None
    return "Endpoint must be an http(s) URL."


def infer_openai_models_url(endpoint: str) -> str | None:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path_parts = [part for part in parsed.path.split("/") if part]
    if "v1" not in [part.lower() for part in path_parts]:
        return None
    v1_index = [part.lower() for part in path_parts].index("v1")
    models_path = "/" + "/".join(path_parts[: v1_index + 1] + ["models"])
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, models_path, "", "", "")
    )


def infer_openai_operation_url(endpoint: str, operation: str) -> str | None:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path_parts = [part for part in parsed.path.split("/") if part]
    lower_parts = [part.lower() for part in path_parts]
    if "v1" not in lower_parts:
        return None
    v1_index = lower_parts.index("v1")
    operation_path = "/" + "/".join(
        path_parts[: v1_index + 1] + [operation.strip("/")]
    )
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, operation_path, "", "", "")
    )


def probe_openai_embedding_model(
    endpoint: str,
    model: str,
    headers: dict[str, str],
) -> dict[str, Any] | None:
    embeddings_url = infer_openai_operation_url(endpoint, "embeddings")
    if not embeddings_url:
        return None
    return http_json_request(
        embeddings_url,
        method="POST",
        payload={"model": model, "input": "DocTriage endpoint probe"},
        headers=headers,
    )


def extract_model_names(payload: Any) -> list[str]:
    raw_items: Any
    if isinstance(payload, dict):
        raw_items = payload.get("models")
        if raw_items is None:
            raw_items = payload.get("data")
    else:
        raw_items = payload
    if not isinstance(raw_items, list):
        return []

    names: list[str] = []
    for item in raw_items:
        if isinstance(item, str):
            names.append(item)
            continue
        if not isinstance(item, dict):
            continue
        for key in ("name", "model", "id"):
            name = str(item.get(key) or "").strip()
            if name:
                names.append(name)
    return sorted(set(names), key=str.lower)


def model_exists(model: str, names: list[str]) -> bool:
    return any(models_are_same(model, name) for name in names)


def llm_probe_endpoint_and_model(payload: dict[str, Any]) -> tuple[str, str, str]:
    role = str(payload.get("role") or "analysis").strip().lower()
    if role == "embedding":
        endpoint = str(
            payload.get("endpoint")
            or payload.get("embedding_endpoint")
            or DEFAULT_EMBEDDING_ENDPOINT
        ).strip()
        model = str(
            payload.get("model") or payload.get("embedding_model") or ""
        ).strip()
        return role, endpoint, model
    endpoint = str(
        payload.get("endpoint") or payload.get("llm_endpoint") or DEFAULT_LLM_ENDPOINT
    ).strip()
    model = str(payload.get("model") or payload.get("llm_model") or "").strip()
    return role or "analysis", endpoint, model


def test_llm_connection(payload: dict[str, Any]) -> dict[str, Any]:
    role, endpoint, model = llm_probe_endpoint_and_model(payload)
    if not endpoint:
        return {
            "ok": False,
            "reachable": False,
            "role": role,
            "endpoint": endpoint,
            "model": model,
            "model_checked": False,
            "model_exists": None,
            "message": "Endpoint is required.",
        }
    url_error = validate_http_url(endpoint)
    if url_error:
        return {
            "ok": False,
            "reachable": False,
            "role": role,
            "endpoint": endpoint,
            "model": model,
            "model_checked": False,
            "model_exists": None,
            "message": url_error,
        }

    headers = endpoint_auth_headers(payload)
    ollama_endpoint = resolve_ollama_runtime_endpoint(endpoint)
    if ollama_endpoint is not None:
        tags_url = f"{ollama_endpoint.base_url}/tags"
        probe = http_json_request(tags_url, headers=headers)
        status_code = probe.get("status_code")
        if not probe.get("reachable"):
            return {
                "ok": False,
                "reachable": False,
                "provider": "ollama",
                "role": role,
                "endpoint": endpoint,
                "model": model,
                "model_checked": False,
                "model_exists": None,
                "status_code": status_code,
                "message": f"Ollama endpoint is unreachable: {probe.get('error') or 'request failed'}",
            }
        if status_code != 200:
            return {
                "ok": False,
                "reachable": True,
                "provider": "ollama",
                "role": role,
                "endpoint": endpoint,
                "model": model,
                "model_checked": False,
                "model_exists": None,
                "status_code": status_code,
                "message": f"Ollama is reachable, but /api/tags returned HTTP {status_code}.",
            }
        names = extract_model_names(probe.get("json"))
        checked = bool(model)
        exists = model_exists(model, names) if checked else None
        return {
            "ok": not checked or bool(exists),
            "reachable": True,
            "provider": "ollama",
            "role": role,
            "endpoint": endpoint,
            "model": model,
            "model_checked": checked,
            "model_exists": exists,
            "status_code": status_code,
            "models": names[:50],
            "message": (
                f"Model '{model}' was found on Ollama."
                if checked and exists
                else f"Model '{model}' was not found on Ollama."
                if checked
                else "Ollama endpoint is reachable."
            ),
        }

    models_url = infer_openai_models_url(endpoint)
    if models_url:
        probe = http_json_request(models_url, headers=headers)
        status_code = probe.get("status_code")
        if probe.get("reachable") and status_code == 200:
            names = extract_model_names(probe.get("json"))
            checked = bool(model)
            exists = model in names if checked else None
            if role == "embedding" and checked and not exists:
                embedding_probe = probe_openai_embedding_model(
                    endpoint,
                    model,
                    headers,
                )
                if embedding_probe is not None:
                    embedding_status = embedding_probe.get("status_code")
                    embedding_ok = (
                        bool(embedding_probe.get("reachable"))
                        and embedding_status == 200
                    )
                    return {
                        "ok": embedding_ok,
                        "reachable": bool(embedding_probe.get("reachable")),
                        "provider": "openai-compatible",
                        "role": role,
                        "endpoint": endpoint,
                        "model": model,
                        "model_checked": True,
                        "model_exists": embedding_ok,
                        "status_code": embedding_status,
                        "models": names[:50],
                        "message": (
                            f"Model '{model}' accepted an embedding request even though it was not listed in /v1/models."
                            if embedding_ok
                            else f"Model '{model}' was not listed and the /v1/embeddings probe failed: "
                            f"{embedding_probe.get('error') or f'HTTP {embedding_status}'}"
                        ),
                    }
            return {
                "ok": not checked or bool(exists),
                "reachable": True,
                "provider": "openai-compatible",
                "role": role,
                "endpoint": endpoint,
                "model": model,
                "model_checked": checked,
                "model_exists": exists,
                "status_code": status_code,
                "models": names[:50],
                "message": (
                    f"Model '{model}' was found."
                    if checked and exists
                    else f"Model '{model}' was not found in /v1/models."
                    if checked
                    else "OpenAI-compatible endpoint is reachable."
                ),
            }
        if probe.get("reachable") and status_code in {401, 403}:
            return {
                "ok": False,
                "reachable": True,
                "provider": "openai-compatible",
                "role": role,
                "endpoint": endpoint,
                "model": model,
                "model_checked": False,
                "model_exists": None,
                "status_code": status_code,
                "message": f"/v1/models returned HTTP {status_code}; check API key or permissions.",
            }

    probe = http_json_request(endpoint, headers=headers)
    status_code = probe.get("status_code")
    reachable = bool(probe.get("reachable"))
    ok = reachable and (
        status_code is None
        or 200 <= int(status_code) < 400
        or int(status_code) in {400, 405}
    )
    return {
        "ok": ok,
        "reachable": reachable,
        "provider": "http",
        "role": role,
        "endpoint": endpoint,
        "model": model,
        "model_checked": False,
        "model_exists": None,
        "status_code": status_code,
        "message": (
            "Endpoint is reachable; model listing is not available."
            if ok
            else f"Endpoint check failed: {probe.get('error') or f'HTTP {status_code}'}"
        ),
    }


def joined_url(base_url: str, *segments: str) -> str:
    base = base_url.rstrip("/")
    encoded = "/".join(urllib.parse.quote(str(segment).strip("/"), safe="") for segment in segments)
    return f"{base}/{encoded}" if encoded else base


def test_local_vector_store(paths: ReadingPaths) -> dict[str, Any]:
    rag_root = rag_dir(paths)
    vectors = rag_vectors_path(paths)
    chunks = rag_chunks_path(paths)
    documents = rag_documents_path(paths)
    root_exists = paths.output_root.exists() and paths.output_root.is_dir()
    rag_exists = rag_root.exists() and rag_root.is_dir()
    vectors_exists = vectors.exists() and vectors.is_file()
    vector_count = count_nonempty_lines(vectors) if vectors_exists else 0
    return {
        "ok": root_exists and rag_exists,
        "reachable": root_exists,
        "store_type": "local_jsonl",
        "output_root": str(paths.output_root),
        "rag_dir": str(rag_root),
        "documents_exists": documents.exists(),
        "chunks_exists": chunks.exists(),
        "vectors_exists": vectors_exists,
        "vector_count": vector_count,
        "message": (
            f"Local RAG store is readable; vectors.jsonl has {vector_count} records."
            if root_exists and rag_exists and vectors_exists
            else "Local RAG store is readable, but vectors.jsonl has not been generated yet."
            if root_exists and rag_exists
            else "Output directory is reachable, but _rag does not exist yet."
            if root_exists
            else "Output directory is not reachable."
        ),
    }


def test_qdrant_local_vector_store(
    paths: ReadingPaths, path_value: str = "", collection: str = ""
) -> dict[str, Any]:
    qdrant_path = (
        Path(path_value).expanduser().resolve()
        if str(path_value or "").strip()
        else rag_dir(paths) / "qdrant"
    )
    try:
        return inspect_qdrant_local_index(
            qdrant_path,
            collection or "doctriage_rag",
        )
    except Exception as exc:
        return {
            "ok": False,
            "reachable": False,
            "store_type": "qdrant_local",
            "path": str(qdrant_path),
            "collection": collection or "doctriage_rag",
            "collection_checked": True,
            "collection_exists": None,
            "message": f"Qdrant Local check failed: {exc}",
        }


def test_qdrant_vector_store(url: str, collection: str) -> dict[str, Any]:
    collections_url = joined_url(url, "collections")
    probe = http_json_request(collections_url)
    status_code = probe.get("status_code")
    if not probe.get("reachable") or status_code != 200:
        return {
            "ok": False,
            "reachable": bool(probe.get("reachable")),
            "store_type": "qdrant",
            "url": url,
            "collection": collection,
            "collection_checked": False,
            "collection_exists": None,
            "status_code": status_code,
            "message": f"Qdrant /collections check failed: {probe.get('error') or f'HTTP {status_code}'}",
        }

    collection_exists: bool | None = None
    if collection:
        collection_probe = http_json_request(joined_url(url, "collections", collection))
        collection_exists = (
            bool(collection_probe.get("reachable"))
            and collection_probe.get("status_code") == 200
        )
        status_code = collection_probe.get("status_code")
    return {
        "ok": collection_exists if collection else True,
        "reachable": True,
        "store_type": "qdrant",
        "url": url,
        "collection": collection,
        "collection_checked": bool(collection),
        "collection_exists": collection_exists,
        "status_code": status_code,
        "message": (
            f"Qdrant is reachable; collection '{collection}' exists."
            if collection and collection_exists
            else f"Qdrant is reachable, but collection '{collection}' was not found."
            if collection
            else "Qdrant is reachable."
        ),
    }


def test_chroma_vector_store(url: str, collection: str) -> dict[str, Any]:
    heartbeat_urls = [
        joined_url(url, "api", "v2", "heartbeat"),
        joined_url(url, "api", "v1", "heartbeat"),
    ]
    heartbeat_probe: dict[str, Any] | None = None
    heartbeat_version = ""
    for candidate_url in heartbeat_urls:
        candidate = http_json_request(candidate_url)
        if candidate.get("reachable") and candidate.get("status_code") == 200:
            heartbeat_probe = candidate
            heartbeat_version = "v2" if "/v2/" in candidate_url else "v1"
            break
        if heartbeat_probe is None:
            heartbeat_probe = candidate

    status_code = None if heartbeat_probe is None else heartbeat_probe.get("status_code")
    if heartbeat_probe is None or not heartbeat_probe.get("reachable") or status_code != 200:
        return {
            "ok": False,
            "reachable": bool(heartbeat_probe and heartbeat_probe.get("reachable")),
            "store_type": "chroma",
            "url": url,
            "collection": collection,
            "collection_checked": False,
            "collection_exists": None,
            "status_code": status_code,
            "message": f"Chroma heartbeat check failed: {(heartbeat_probe or {}).get('error') or f'HTTP {status_code}'}",
        }

    collection_exists: bool | None = None
    if collection:
        if heartbeat_version == "v2":
            collection_url = joined_url(
                url,
                "api",
                "v2",
                "tenants",
                "default_tenant",
                "databases",
                "default_database",
                "collections",
                collection,
            )
        else:
            collection_url = joined_url(url, "api", "v1", "collections", collection)
        collection_probe = http_json_request(collection_url)
        collection_exists = (
            bool(collection_probe.get("reachable"))
            and collection_probe.get("status_code") == 200
        )
        status_code = collection_probe.get("status_code")

    return {
        "ok": collection_exists if collection else True,
        "reachable": True,
        "store_type": "chroma",
        "url": url,
        "collection": collection,
        "collection_checked": bool(collection),
        "collection_exists": collection_exists,
        "status_code": status_code,
        "message": (
            f"Chroma is reachable; collection '{collection}' exists."
            if collection and collection_exists
            else f"Chroma is reachable, but collection '{collection}' was not found."
            if collection
            else "Chroma is reachable."
        ),
    }


def test_generic_vector_store(url: str, collection: str) -> dict[str, Any]:
    probe = http_json_request(url)
    status_code = probe.get("status_code")
    reachable = bool(probe.get("reachable"))
    ok = reachable and status_code is not None and 200 <= int(status_code) < 400
    return {
        "ok": ok,
        "reachable": reachable,
        "store_type": "http",
        "url": url,
        "collection": collection,
        "collection_checked": False,
        "collection_exists": None,
        "status_code": status_code,
        "message": (
            "HTTP vector endpoint is reachable."
            if ok
            else f"HTTP vector endpoint check failed: {probe.get('error') or f'HTTP {status_code}'}"
        ),
    }


def test_vector_store_connection(
    app_state: AppState, payload: dict[str, Any]
) -> dict[str, Any]:
    store_type = str(
        payload.get("store_type") or payload.get("vector_store_type") or "local_jsonl"
    ).strip().lower()
    if store_type in {"local", "jsonl", "local-jsonl"}:
        store_type = "local_jsonl"
    if store_type == "local_jsonl":
        paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
        return test_local_vector_store(paths)
    if store_type in {"qdrant_local", "local_qdrant", "qdrant-local"}:
        paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
        return test_qdrant_local_vector_store(
            paths,
            str(payload.get("path") or payload.get("qdrant_path") or ""),
            str(
                payload.get("collection")
                or payload.get("qdrant_collection")
                or "doctriage_rag"
            ).strip(),
        )

    url = str(payload.get("url") or payload.get("vector_store_url") or "").strip()
    collection = str(
        payload.get("collection") or payload.get("vector_store_collection") or ""
    ).strip()
    if not url:
        return {
            "ok": False,
            "reachable": False,
            "store_type": store_type,
            "url": url,
            "collection": collection,
            "message": "Vector store URL is required.",
        }
    url_error = validate_http_url(url)
    if url_error:
        return {
            "ok": False,
            "reachable": False,
            "store_type": store_type,
            "url": url,
            "collection": collection,
            "message": url_error,
        }
    if store_type == "qdrant":
        return test_qdrant_vector_store(url, collection)
    if store_type == "chroma":
        return test_chroma_vector_store(url, collection)
    if store_type in {"http", "generic_http", "generic"}:
        return test_generic_vector_store(url, collection)
    return {
        "ok": False,
        "reachable": False,
        "store_type": store_type,
        "url": url,
        "collection": collection,
        "message": f"Unsupported vector store type: {store_type}",
    }


def relationship_task_command(
    task_name: str, payload: dict[str, Any], paths: ReadingPaths
) -> list[str]:
    llm_endpoint = str(payload.get("llm_endpoint") or "http://localhost:11434/api/generate")
    llm_model = str(payload.get("llm_model") or "").strip()
    embedding_endpoint = str(payload.get("embedding_endpoint") or "").strip()
    embedding_model = str(payload.get("embedding_model") or "").strip()
    command_map = {
        "mine": [sys.executable, str(PROJECT_ROOT / "relationship_miner.py")],
        "export_graph": [sys.executable, str(PROJECT_ROOT / "knowledge_graph.py")],
        "export_bundle": [sys.executable, str(PROJECT_ROOT / "bundle_exporter.py")],
    }
    command = command_map.get(task_name)
    if command is None:
        raise ValueError(f"Unsupported relationship task: {task_name}")
    command.extend(
        [
            "--source-dir",
            str(paths.source_dir),
            "--output-root",
            str(paths.output_root),
            "--llm-endpoint",
            llm_endpoint,
        ]
    )
    if llm_model:
        command.extend(["--llm-model", llm_model])
    if task_name == "mine":
        concurrency = str(payload.get("concurrency") or "").strip()
        if concurrency:
            command.extend(["--concurrency", concurrency])
        if bool(payload.get("relationship_use_text_citations", True)):
            command.append("--use-text-citations")
        relationship_use_embeddings = bool(payload.get("relationship_use_embeddings"))
        if relationship_use_embeddings:
            if not embedding_model:
                raise ValueError(
                    "Embedding model is required when embedding relationships are enabled."
                )
            command.append("--use-embeddings")
        if relationship_use_embeddings:
            if embedding_endpoint:
                command.extend(["--embedding-endpoint", embedding_endpoint])
            command.extend(["--embedding-model", embedding_model])
    return command


def model_api_key_env(payload: dict[str, Any]) -> dict[str, str]:
    env: dict[str, str] = {}
    llm_api_key = str(payload.get("llm_api_key") or "").strip()
    embedding_api_key = str(payload.get("embedding_api_key") or "").strip()
    if llm_api_key:
        env["LLM_API_KEY"] = llm_api_key
    if embedding_api_key:
        env["EMBEDDING_API_KEY"] = embedding_api_key
    return env


def subprocess_env_for_payload(payload: dict[str, Any]) -> dict[str, str]:
    env = utf8_subprocess_env()
    env.update(model_api_key_env(payload))
    return env


def managed_process_popen_options() -> dict[str, Any]:
    if os.name == "nt":
        return {"creationflags": MANAGED_PROCESS_CREATIONFLAGS}
    return {"start_new_session": True}


def stop_completed_managed_relationship_task(
    app_state: AppState,
    paths: ReadingPaths,
    task: ManagedProcessTask,
) -> bool:
    process = task.process
    if process.poll() is not None:
        clear_relationship_task(app_state, paths, task)
        return True
    if not relationship_outputs_complete_after(paths, task.started_epoch):
        return False

    terminate_process_tree(process, timeout_seconds=5.0)
    if process.poll() is not None:
        clear_relationship_task(app_state, paths, task)
        return True

    reap_completed_managed_process(app_state, paths, task, clear_relationship_task)
    return False


def start_relationship_task(
    app_state: AppState, payload: dict[str, Any], task_name: str
) -> dict[str, Any]:
    paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
    output_root = paths.output_root
    task_labels = {
        "mine": "图谱生成",
        "export_graph": "知识图谱导出",
        "export_bundle": "Bundle 导出",
    }
    label = task_labels.get(task_name, task_name)

    with app_state.lock:
        analysis_task = analysis_task_for_paths(app_state, paths)
        analysis_process = analysis_task.process if analysis_task is not None else None
        if analysis_process is not None and analysis_process.poll() is None:
            raise RuntimeError("Cannot start relationship task while analysis is running.")
        active_analysis_pid = find_active_run_pid(paths)
        if active_analysis_pid is not None:
            raise RuntimeError(
                f"Cannot start relationship task while analysis is running with PID {active_analysis_pid}."
            )
        relationship_task = relationship_task_for_paths(app_state, paths)
        if (
            relationship_task is not None
            and relationship_task.process.poll() is None
        ):
            if stop_completed_managed_relationship_task(
                app_state, paths, relationship_task
            ):
                relationship_task = None
            else:
                raise RuntimeError(
                    "Another relationship task is already running for this output."
                )
        active_relationship_pid = find_active_relationship_task_pid(paths)
        if active_relationship_pid is not None:
            raise RuntimeError(
                f"Relationship task is already running for this output with PID {active_relationship_pid}."
            )
        if task_name != "mine" and not relationship_relations_path(paths).exists():
            raise RuntimeError("No relationship results found. Generate relations first.")
        output_root.mkdir(parents=True, exist_ok=True)
        paths.log_dir.mkdir(parents=True, exist_ok=True)
        command = relationship_task_command(task_name, payload, paths)
        process_env = subprocess_env_for_payload(payload)
        with paths.application_log_path.open("a", encoding="utf-8", errors="ignore") as log_handle:
            task_process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=process_env,
                **managed_process_popen_options(),
            )
        register_relationship_task(app_state, paths, task_process, command, task_name)
    return {
        "started": True,
        "task": task_name,
        "label": label,
        "pid": task_process.pid,
        "command": command,
    }


def stop_relationship_task(
    app_state: AppState, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    requested_paths = reading_paths_from_payload(app_state, payload or {})
    relationship_result: dict[str, Any] | None = None
    with app_state.lock:
        task = relationship_task_for_paths(app_state, requested_paths)
        process = task.process if task is not None else None
        command = task.command if task is not None else None
        kind = task.kind if task is not None else None
        if process is not None:
            if process.poll() is None:
                stopped = terminate_process_tree(process, timeout_seconds=5.0)
                running = process.poll() is None
                if not running:
                    clear_relationship_task(app_state, requested_paths, task)
                return {
                    "stopped": stopped,
                    "running": running,
                    "pid": process.pid,
                    "kind": kind,
                }
            clear_relationship_task(app_state, requested_paths, task)
            relationship_result = {
                "stopped": False,
                "running": False,
                "pid": process.pid,
                "kind": kind,
                "return_code": process.poll(),
            }
    if requested_paths is not None:
        recorded_task = relationship_task_from_record(requested_paths)
        if recorded_task is not None:
            pid = coerce_pid(recorded_task.get("pid"))
            if pid is not None:
                stopped = terminate_process_id(pid)
                running = is_process_alive(pid)
                if not running:
                    remove_relationship_task_record(
                        relationship_task_record_path(requested_paths)
                    )
                return {
                    "stopped": stopped,
                    "running": running,
                    "pid": pid,
                    "kind": recorded_task.get("kind"),
                }
    inline_stop = stop_inline_relationship_task(app_state, requested_paths)
    if inline_stop is not None:
        return inline_stop
    return relationship_result or {"stopped": False, "running": False}


def stop_inline_relationship_task(
    app_state: AppState, requested_paths: ReadingPaths | None = None
) -> dict[str, Any] | None:
    with app_state.lock:
        paths = requested_paths or app_state.paths
        if paths is None:
            return None
        task = analysis_task_for_paths(app_state, paths)
        process = task.process if task is not None else None
        command = task.command if task is not None else None
        local_running = (
            process is not None
            and process.poll() is None
            and paths_match_command(command, paths)
        )

    active_pid = None if local_running else find_active_run_pid(paths)
    if not inline_relationship_mining_is_active(
        running=local_running or active_pid is not None,
        command=command,
        log_tail=read_text_tail(paths.application_log_path, max_lines=80),
    ):
        return None

    stop_result = stop_analysis(
        app_state,
        {"source_dir": str(paths.source_dir), "output_root": str(paths.output_root)},
    )
    return {
        **stop_result,
        "kind": "mine",
        "inline": True,
    }


def build_rag_payload(app_state: AppState, paths: ReadingPaths) -> dict[str, Any]:
    return {
        "available": rag_manifest_path(paths).exists(),
        "documents_exists": rag_documents_path(paths).exists(),
        "chunks_exists": rag_chunks_path(paths).exists(),
        "vectors_exists": rag_vectors_path(paths).exists(),
        "manifest": read_json_file(rag_manifest_path(paths)),
        "progress": read_json_file(rag_progress_path(paths)),
        "task": rag_task_status(app_state, paths),
        "log_tail": read_text_tail(rag_log_path(paths), max_lines=80),
    }


def rag_task_status(
    app_state: AppState, paths: ReadingPaths | None = None
) -> dict[str, Any]:
    with app_state.lock:
        task = rag_managed_task_for_paths(app_state, paths)
        process = task.process if task is not None else None
        kind = task.kind if task is not None else None
        command = task.command if task is not None else None
        return_code = None if process is None else process.poll()
        if process is not None and return_code is not None:
            clear_rag_task(app_state, paths, task)
        running = process is not None and return_code is None
        pid = process.pid if process is not None else None
    return {
        "running": running,
        "pid": pid,
        "kind": kind,
        "command": command,
        "return_code": return_code,
    }


def rag_task_command(payload: dict[str, Any], paths: ReadingPaths) -> list[str]:
    llm_endpoint = str(payload.get("llm_endpoint") or "http://localhost:11434/api/generate")
    llm_model = str(payload.get("llm_model") or "").strip()
    embedding_endpoint = str(payload.get("embedding_endpoint") or "").strip()
    embedding_model = str(payload.get("embedding_model") or "").strip()
    command = [
        sys.executable,
        str(PROJECT_ROOT / "rag_indexer.py"),
        "build",
        "--source-dir",
        str(paths.source_dir),
        "--output-root",
        str(paths.output_root),
        "--llm-endpoint",
        llm_endpoint,
    ]
    if llm_model:
        command.extend(["--llm-model", llm_model])
    if embedding_endpoint:
        command.extend(["--embedding-endpoint", embedding_endpoint])
    if embedding_model:
        command.extend(["--embedding-model", embedding_model])

    vector_store = normalize_vector_store_type(
        str(payload.get("rag_vector_store_type") or "local_jsonl")
    )
    command.extend(["--vector-store", vector_store])
    if vector_store == "qdrant_local":
        qdrant_path = str(payload.get("rag_qdrant_path") or "").strip()
        if qdrant_path:
            command.extend(["--qdrant-path", qdrant_path])
        qdrant_collection = str(
            payload.get("rag_qdrant_collection") or "doctriage_rag"
        ).strip()
        if qdrant_collection:
            command.extend(["--qdrant-collection", qdrant_collection])

    option_map = {
        "rag_min_quality": "--min-quality",
        "rag_limit": "--limit",
        "rag_chunk_max_chars": "--chunk-max-chars",
        "rag_chunk_overlap_chars": "--chunk-overlap-chars",
    }
    for payload_key, option_name in option_map.items():
        value = str(payload.get(payload_key) or "").strip()
        if value:
            command.extend([option_name, value])

    categories = str(payload.get("rag_categories") or "").strip()
    if categories:
        command.extend(["--categories", categories])
    if bool(payload.get("rag_prefer_target_path")):
        command.append("--prefer-target-path")
    if not embedding_model:
        command.append("--no-embeddings")
    return command


def rag_redaction_env(payload: dict[str, Any]) -> dict[str, str]:
    if not bool(payload.get("rag_redaction_enabled")):
        return {}
    redact_terms = str(payload.get("rag_redact_terms") or "").strip()
    redact_mappings = str(payload.get("rag_redact_mappings") or "").strip()
    if not redact_terms and not redact_mappings:
        raise ValueError(
            "Sensitive firewall is enabled, but no redaction rules were provided."
        )
    env: dict[str, str] = {}
    if redact_terms:
        env[RAG_REDACTION_TERMS_ENV] = redact_terms
    if redact_mappings:
        env[RAG_REDACTION_MAPPINGS_ENV] = redact_mappings
    redact_placeholder = str(payload.get("rag_redact_placeholder") or "").strip()
    if redact_placeholder:
        env[RAG_REDACTION_PLACEHOLDER_ENV] = redact_placeholder
    if bool(payload.get("rag_redact_drop_matched_documents")):
        env[RAG_REDACTION_DROP_ENV] = "1"
    return env


def start_rag_task(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
    vector_store = normalize_vector_store_type(
        str(payload.get("rag_vector_store_type") or "local_jsonl")
    )
    embedding_model = str(payload.get("embedding_model") or "").strip()
    if vector_store == "qdrant_local" and not embedding_model:
        raise ValueError(
            "Qdrant Local requires an embedding model before indexing can start."
        )

    with app_state.lock:
        analysis_task = analysis_task_for_paths(app_state, paths)
        analysis_process = analysis_task.process if analysis_task is not None else None
        if analysis_process is not None and analysis_process.poll() is None:
            raise RuntimeError("Cannot start RAG indexing while analysis is running.")
        active_analysis_pid = find_active_run_pid(paths)
        if active_analysis_pid is not None:
            raise RuntimeError(
                f"Cannot start RAG indexing while analysis is running with PID {active_analysis_pid}."
            )
        relationship_task = relationship_task_for_paths(app_state, paths)
        relationship_process = (
            relationship_task.process if relationship_task is not None else None
        )
        if relationship_process is not None and relationship_process.poll() is None:
            raise RuntimeError(
                "Cannot start RAG indexing while a relationship task is running."
            )
        active_relationship_pid = find_active_relationship_task_pid(paths)
        if active_relationship_pid is not None:
            raise RuntimeError(
                f"Cannot start RAG indexing while a relationship task is running with PID {active_relationship_pid}."
            )
        rag_task = rag_managed_task_for_paths(app_state, paths)
        if rag_task is not None and rag_task.process.poll() is None:
            raise RuntimeError("RAG indexing is already running.")

        paths.output_root.mkdir(parents=True, exist_ok=True)
        rag_dir(paths).mkdir(parents=True, exist_ok=True)
        command = rag_task_command(payload, paths)
        process_env = subprocess_env_for_payload(payload)
        process_env.update(rag_redaction_env(payload))
        with rag_log_path(paths).open("a", encoding="utf-8", errors="ignore") as log_handle:
            task_process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=process_env,
                **managed_process_popen_options(),
            )
        register_rag_task(app_state, paths, task_process, command, "build")
    return {
        "started": True,
        "task": "build",
        "pid": task_process.pid,
        "command": command,
    }


def stop_rag_task(
    app_state: AppState, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    requested_paths = reading_paths_from_payload(app_state, payload or {})
    with app_state.lock:
        task = rag_managed_task_for_paths(app_state, requested_paths)
        process = task.process if task is not None else None
        kind = task.kind if task is not None else None
        if process is None:
            return {"stopped": False, "running": False}
        if process.poll() is None:
            stopped = terminate_process_tree(process, timeout_seconds=5.0)
            running = process.poll() is None
            if not running:
                clear_rag_task(app_state, requested_paths, task)
            return {
                "stopped": stopped,
                "running": running,
                "pid": process.pid,
                "kind": kind,
            }
        clear_rag_task(app_state, requested_paths, task)
        return {
            "stopped": False,
            "running": False,
            "pid": process.pid,
            "kind": kind,
            "return_code": process.poll(),
        }


def search_rag_request(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    from rag_indexer import search_rag_index

    paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
    query = str(payload.get("query") or "").strip()
    if not query:
        raise ValueError("Search query is required.")
    settings = Settings(
        LLM_ENDPOINT=str(payload.get("llm_endpoint") or "http://localhost:11434/api/generate"),
        LLM_API_KEY=str(payload.get("llm_api_key") or "").strip() or None,
        SOURCE_DIR=paths.source_dir,
        OUTPUT_ROOT=paths.output_root,
        EMBEDDING_ENDPOINT=str(
            payload.get("embedding_endpoint") or "http://localhost:11434/api/embeddings"
        ),
        EMBEDDING_MODEL=str(payload.get("embedding_model") or "").strip() or None,
        EMBEDDING_API_KEY=str(payload.get("embedding_api_key") or "").strip() or None,
        RAG_MAX_SEARCH_RESULTS=coerce_int_value(payload.get("top_k"), 10),
        RAG_VECTOR_STORE_TYPE=normalize_vector_store_type(
            str(payload.get("rag_vector_store_type") or "local_jsonl")
        ),
        RAG_QDRANT_PATH=(
            Path(str(payload.get("rag_qdrant_path")).strip()).expanduser().resolve()
            if str(payload.get("rag_qdrant_path") or "").strip()
            else None
        ),
        RAG_QDRANT_COLLECTION=str(
            payload.get("rag_qdrant_collection") or "doctriage_rag"
        ).strip(),
    )
    return search_rag_index(
        settings,
        query,
        top_k=coerce_int_value(payload.get("top_k"), 10),
        lexical_only=bool(payload.get("lexical_only")),
    )


def row_matches_query(row: dict[str, Any], q: str) -> bool:
    haystack = " ".join(
        [
            str(row.get("relative_path") or ""),
            str(row.get("source_path") or ""),
            str(row.get("category") or ""),
            str(row.get("document_kind") or ""),
            str(row.get("summary") or ""),
            str(row.get("reason") or ""),
            str(row.get("failure_stage") or ""),
            str(row.get("failure_reason") or ""),
            str(row.get("failure_error") or ""),
            " ".join(str(tag) for tag in row.get("topic_tags") or []),
            str(row.get("note") or ""),
        ]
    ).lower()
    return q in haystack


def sort_rows(rows: list[dict[str, Any]], sort_key: str) -> list[dict[str, Any]]:
    key_map = {
        "quality_desc": lambda row: (-int(row.get("quality") or 0), row.get("relative_path") or ""),
        "quality_asc": lambda row: (int(row.get("quality") or 0), row.get("relative_path") or ""),
        "path_asc": lambda row: (source_sort_path(row),),
        "path_desc": lambda row: (source_sort_path(row),),
        "source_path_asc": lambda row: (source_sort_path(row),),
        "source_path_desc": lambda row: (source_sort_path(row),),
        "source_mtime_desc": lambda row: (-source_mtime_sort_value(row), source_sort_path(row)),
        "source_mtime_asc": lambda row: (source_mtime_sort_value(row), source_sort_path(row)),
        "category_asc": lambda row: (str(row.get("category") or ""), -int(row.get("quality") or 0)),
        "category_desc": lambda row: (str(row.get("category") or ""), int(row.get("quality") or 0)),
        "status_asc": lambda row: (str(row.get("status") or ""), -int(row.get("quality") or 0)),
        "status_desc": lambda row: (str(row.get("status") or ""), int(row.get("quality") or 0)),
        "kind_asc": lambda row: (str(row.get("document_kind") or ""), -int(row.get("quality") or 0)),
        "kind_desc": lambda row: (str(row.get("document_kind") or ""), int(row.get("quality") or 0)),
        "updated_desc": lambda row: (str(row.get("updated_at") or ""),),
        "sensitivity_asc": lambda row: (int(row.get("sensitivity_risk") or 0), -int(row.get("quality") or 0)),
        "sensitivity_desc": lambda row: (int(row.get("sensitivity_risk") or 0), int(row.get("quality") or 0)),
        "public_desc": lambda row: (-int(row.get("public_writing_suitability") or 0), -int(row.get("quality") or 0)),
        "public_asc": lambda row: (int(row.get("public_writing_suitability") or 0), -int(row.get("quality") or 0)),
    }
    key_func = key_map.get(sort_key, key_map["quality_desc"])
    reverse = sort_key in {
        "updated_desc",
        "path_desc",
        "source_path_desc",
        "category_desc",
        "status_desc",
        "kind_desc",
        "sensitivity_desc",
    }
    return sorted(rows, key=key_func, reverse=reverse)


def source_sort_path(row: dict[str, Any]) -> str:
    return str(row.get("source_path") or row.get("relative_path") or "").lower()


def source_mtime_sort_value(row: dict[str, Any]) -> float:
    value = row.get("source_mtime_epoch")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def config_payload(paths: ReadingPaths | None) -> dict[str, Any]:
    return {
        "source_dir": "" if paths is None else str(paths.source_dir),
        "output_root": "" if paths is None else str(paths.output_root),
        "embedding_endpoint": configured_embedding_endpoint(),
        "capabilities": environment_capabilities(),
    }


def configured_embedding_endpoint() -> str:
    endpoint = str(os.environ.get("EMBEDDING_ENDPOINT") or "").strip()
    if endpoint:
        return endpoint
    env_path = PROJECT_ROOT / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return DEFAULT_EMBEDDING_ENDPOINT
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != "EMBEDDING_ENDPOINT":
            continue
        endpoint = value.strip().strip("\"'")
        return endpoint or DEFAULT_EMBEDDING_ENDPOINT
    return DEFAULT_EMBEDDING_ENDPOINT


def environment_capabilities() -> dict[str, Any]:
    return {
        "platform": sys.platform,
        "os_name": os.name,
        "folder_picker": can_use_folder_picker(),
        "open_file": can_open_file(),
        "reveal_file": can_reveal_file(),
        "headless_hint": (
            "Folder picker and system default file opening may be unavailable on headless servers. "
            "Manual path input and analysis execution still work."
            if is_probably_headless()
            else ""
        ),
    }


def is_probably_headless() -> bool:
    if os.name == "nt":
        return False
    if sys.platform == "darwin":
        return False
    return not bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def can_use_folder_picker() -> bool:
    if is_probably_headless():
        return False
    if os.name == "nt":
        return windows_folder_picker_command() is not None
    if sys.platform == "darwin" and macos_folder_picker_command() is not None:
        return True
    if sys.platform.startswith("linux") and linux_folder_picker_command() is not None:
        return True
    return tkinter_folder_picker_available()


def tkinter_folder_picker_available() -> bool:
    try:
        import tkinter  # noqa: F401
        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
    except Exception:
        return False
    return True


def can_open_file() -> bool:
    if os.name == "nt":
        return True
    if sys.platform == "darwin":
        return macos_open_command_available()
    if is_probably_headless():
        return False
    return linux_open_command_available()


def can_reveal_file() -> bool:
    if os.name == "nt":
        return True
    if sys.platform == "darwin":
        return macos_open_command_available()
    return can_open_file()


def start_analysis(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(payload)
    source_dir, output_root, additional_source_dirs = resolve_analysis_paths(payload)
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    preempt_relationships = bool(payload.get("preempt_relationships"))
    relationship_stop_result: dict[str, Any] | None = None
    relationship_command: list[str] | None = None

    with app_state.lock:
        analysis_task = analysis_task_for_paths(app_state, paths)
        process = analysis_task.process if analysis_task is not None else None
        if process is not None and process.poll() is None:
            raise RuntimeError(
                f"Analysis is already running for this output with PID {process.pid}"
            )

        relationship_task = relationship_task_for_paths(app_state, paths)
        relationship_process = (
            relationship_task.process if relationship_task is not None else None
        )
        if relationship_process is not None and relationship_process.poll() is not None:
            clear_relationship_task(app_state, paths, relationship_task)
            relationship_task = None
            relationship_process = None
        relationship_running = (
            relationship_process is not None and relationship_process.poll() is None
        )
        if relationship_running:
            relationship_command = relationship_task.command

    external_relationship_pid = (
        None if relationship_running else find_active_relationship_task_pid(paths)
    )
    if external_relationship_pid is not None:
        if not preempt_relationships:
            raise RuntimeError(
                f"Cannot start analysis while a relationship task is running for this output with PID {external_relationship_pid}."
            )
        relationship_stop_result = stop_relationship_task(
            app_state,
            {"source_dir": str(source_dir), "output_root": str(output_root)},
        )
        if relationship_stop_result.get("running"):
            raise RuntimeError(
                "Relationship task did not stop; analysis was not started."
            )

    if relationship_running:
        if not preempt_relationships:
            raise RuntimeError(
                "Cannot start analysis while a relationship task is running for this output."
            )
        else:
            if not str(payload.get("embedding_model") or "").strip() and relationship_command:
                embedding_model = command_option_value(relationship_command, "--embedding-model")
                if embedding_model:
                    payload["embedding_model"] = embedding_model
            relationship_stop_result = stop_relationship_task(
                app_state,
                {"source_dir": str(source_dir), "output_root": str(output_root)},
            )
            if relationship_stop_result.get("running"):
                raise RuntimeError(
                    "Relationship task did not stop; analysis was not started."
                )

    with app_state.lock:
        analysis_task = analysis_task_for_paths(app_state, paths)
        process = analysis_task.process if analysis_task is not None else None
        if process is not None and process.poll() is None:
            raise RuntimeError(
                f"Analysis is already running for this output with PID {process.pid}"
            )
        relationship_task = relationship_task_for_paths(app_state, paths)
        relationship_process = (
            relationship_task.process if relationship_task is not None else None
        )
        if relationship_process is not None and relationship_process.poll() is not None:
            clear_relationship_task(app_state, paths, relationship_task)
            relationship_task = None
            relationship_process = None
        if (
            relationship_process is not None
            and relationship_process.poll() is None
        ):
            raise RuntimeError(
                "Cannot start analysis while a relationship task is running for this output."
            )
        clear_source_file_scan_cache(source_dir)
        app_state.paths = paths
        active_pid = find_active_run_pid(app_state.paths)
        if active_pid is not None:
            raise RuntimeError(f"Analysis is already running with PID {active_pid}")
        command = build_analysis_command(
            payload,
            source_dir,
            output_root,
            additional_source_dirs=additional_source_dirs,
        )
        process_env = subprocess_env_for_payload(payload)
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "_state").mkdir(parents=True, exist_ok=True)
        (output_root / "_logs").mkdir(parents=True, exist_ok=True)
        with app_state.paths.application_log_path.open(
            "a", encoding="utf-8", errors="ignore"
        ) as log_handle:
            process = subprocess.Popen(
                command,
                cwd=str(PROJECT_ROOT),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                env=process_env,
                **managed_process_popen_options(),
            )
        started_epoch = time.time()
        register_analysis_task(app_state, paths, process, command, started_epoch)
        return {
            "started": True,
            "pid": process.pid,
            "command": command,
            "plan_only": is_plan_only_command(command),
            "source_dir": str(source_dir),
            "source_dirs": [
                str(path) for path in (source_dir, *additional_source_dirs)
            ],
            "output_root": str(output_root),
            "relationship_stop": relationship_stop_result,
        }


def set_active_paths(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    source_dir, output_root = resolve_payload_paths(payload)
    with app_state.lock:
        clear_source_file_scan_cache(source_dir)
        app_state.paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    return {"source_dir": str(source_dir), "output_root": str(output_root)}


def set_reading_output(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    output_text = str(payload.get("output_root") or "").strip()
    if not output_text:
        raise ValueError("Output directory is required.")
    output_root = Path(output_text).expanduser().resolve()
    if not output_root.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_root}")
    source_dir = infer_source_dir_for_output(app_state, output_root)
    clear_source_file_scan_cache(source_dir)
    return {"source_dir": str(source_dir), "output_root": str(output_root)}


def create_upload_workspace(app_state: AppState) -> dict[str, Any]:
    upload_id = uuid.uuid4().hex
    workspace = upload_workspace_path(upload_id)
    source_dir = upload_source_dir(upload_id)
    output_root = upload_output_root(upload_id)
    source_dir.mkdir(parents=True, exist_ok=False)
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "upload_id": upload_id,
        "created_epoch": time.time(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_dir),
        "output_root": str(output_root),
        "file_count": 0,
        "total_bytes": 0,
        "files": [],
        "complete": False,
    }
    write_upload_manifest(upload_id, manifest)
    return upload_workspace_payload(upload_id, manifest)


def upload_workspace_path(upload_id: str) -> Path:
    safe_id = validate_upload_id(upload_id)
    return (UPLOAD_WORKSPACE_ROOT / safe_id).resolve()


def upload_source_dir(upload_id: str) -> Path:
    return upload_workspace_path(upload_id) / "source"


def upload_output_root(upload_id: str) -> Path:
    return upload_workspace_path(upload_id) / "output"


def upload_manifest_path(upload_id: str) -> Path:
    return upload_workspace_path(upload_id) / UPLOAD_MANIFEST_NAME


def validate_upload_id(upload_id: str) -> str:
    text = str(upload_id or "").strip()
    if not text or any(ch not in "0123456789abcdef" for ch in text.lower()) or len(text) != 32:
        raise ValueError("Invalid upload id.")
    return text.lower()


def normalize_upload_relative_path(relative_path: str) -> Path:
    text = str(relative_path or "").replace("\\", "/").strip("/")
    if not text:
        raise ValueError("Upload relative path is required.")
    path = Path(text)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("Invalid upload relative path.")
    return path


def resolve_upload_file_path(upload_id: str, relative_path: str) -> tuple[Path, str]:
    source_dir = upload_source_dir(upload_id)
    relative = normalize_upload_relative_path(relative_path)
    target = (source_dir / relative).resolve()
    try:
        target.relative_to(source_dir.resolve())
    except ValueError as exc:
        raise ValueError("Invalid upload relative path.") from exc
    return target, relative.as_posix()


def read_upload_manifest(upload_id: str) -> dict[str, Any]:
    path = upload_manifest_path(upload_id)
    if not path.exists():
        raise FileNotFoundError(f"Upload workspace does not exist: {upload_id}")
    payload = read_json_file(path)
    return payload if isinstance(payload, dict) else {}


def write_upload_manifest(upload_id: str, manifest: dict[str, Any]) -> None:
    path = upload_manifest_path(upload_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def upload_workspace_payload(upload_id: str, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = manifest or read_upload_manifest(upload_id)
    source_dir = upload_source_dir(upload_id)
    output_root = upload_output_root(upload_id)
    roots = upload_manifest_roots(manifest)
    return {
        "upload_id": validate_upload_id(upload_id),
        "source_dir": str(source_dir),
        "output_root": str(output_root),
        "file_count": int(manifest.get("file_count") or 0),
        "total_bytes": int(manifest.get("total_bytes") or 0),
        "root_count": len(roots),
        "roots": roots,
        "complete": bool(manifest.get("complete")),
        "workspace": str(upload_workspace_path(upload_id)),
    }


def upload_manifest_roots(manifest: dict[str, Any]) -> list[str]:
    roots: set[str] = set()
    files = manifest.get("files")
    if not isinstance(files, list):
        return []
    for item in files:
        if not isinstance(item, dict):
            continue
        try:
            relative_path = normalize_upload_relative_path(
                str(item.get("relative_path") or "")
            )
        except ValueError:
            continue
        if len(relative_path.parts) > 1:
            roots.add(relative_path.parts[0])
    return sorted(roots, key=str.casefold)


def save_upload_file(
    app_state: AppState,
    upload_id: str,
    relative_path: str,
    content: bytes,
) -> dict[str, Any]:
    target_path, normalized_relative = resolve_upload_file_path(upload_id, relative_path)
    manifest = read_upload_manifest(upload_id)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    previous_size = target_path.stat().st_size if target_path.exists() else 0
    target_path.write_bytes(content)
    size = len(content)
    manifest_files = manifest.get("files")
    files = [
        item
        for item in manifest_files
        if isinstance(item, dict)
        and str(item.get("relative_path") or "") != normalized_relative
    ] if isinstance(manifest_files, list) else []
    files.append(
        {
            "relative_path": normalized_relative,
            "size": size,
            "uploaded_epoch": time.time(),
        }
    )
    manifest["files"] = files
    manifest["file_count"] = len(files)
    manifest["total_bytes"] = max(0, int(manifest.get("total_bytes") or 0) - previous_size + size)
    manifest["complete"] = False
    write_upload_manifest(upload_id, manifest)
    payload = upload_workspace_payload(upload_id, manifest)
    payload.update({"relative_path": normalized_relative, "size": size})
    return payload


def complete_upload_workspace(app_state: AppState, upload_id: str) -> dict[str, Any]:
    manifest = read_upload_manifest(upload_id)
    if int(manifest.get("file_count") or 0) <= 0:
        raise ValueError("Upload workspace has no files.")
    source_dir = upload_source_dir(upload_id)
    output_root = upload_output_root(upload_id)
    manifest["complete"] = True
    manifest["completed_epoch"] = time.time()
    write_upload_manifest(upload_id, manifest)
    clear_source_file_scan_cache(source_dir)
    return upload_workspace_payload(upload_id, manifest)


def delete_upload_workspace(app_state: AppState, upload_id: str) -> dict[str, Any]:
    workspace = upload_workspace_path(upload_id)
    source_dir = upload_source_dir(upload_id)
    output_root = upload_output_root(upload_id)
    clear_source_file_scan_cache(source_dir)
    if workspace.exists():
        shutil.rmtree(workspace)
    return {
        "deleted": True,
        "upload_id": validate_upload_id(upload_id),
        "source_dir": str(source_dir),
        "output_root": str(output_root),
    }


def infer_source_dir_for_output(app_state: AppState, output_root: Path) -> Path:
    with app_state.lock:
        active_paths = app_state.paths
    if active_paths is not None and active_paths.output_root.resolve() == output_root:
        return active_paths.source_dir

    probe_paths = ReadingPaths(source_dir=output_root, output_root=output_root)
    with app_state.lock:
        tasks = [
            analysis_task_for_paths(app_state, probe_paths),
            relationship_task_for_paths(app_state, probe_paths),
            rag_managed_task_for_paths(app_state, probe_paths),
        ]
    for task in tasks:
        if task is None:
            continue
        source_dir = command_option_path(task.command or [], "--source-dir")
        if source_dir is not None:
            return source_dir.resolve()

    run_lock = read_run_lock(run_lock_path(output_root))
    lock_source = str(run_lock.get("source_dir") or "").strip()
    if lock_source:
        return Path(lock_source).expanduser().resolve()

    relationship_record = read_json_file(output_root / "_relationships" / "task.json")
    relationship_pid = coerce_pid(relationship_record.get("pid"))
    if relationship_pid is not None and is_process_alive(relationship_pid):
        relationship_source = str(relationship_record.get("source_dir") or "").strip()
        if relationship_source:
            return Path(relationship_source).expanduser().resolve()

    decision_source = infer_source_dir_from_decisions(output_root)
    if decision_source is not None:
        return decision_source
    return output_root


def infer_source_dir_from_decisions(output_root: Path) -> Path | None:
    decisions_path = output_root / "_state" / "decisions.jsonl"
    if not decisions_path.exists():
        return None
    try:
        with decisions_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                source_path = str(payload.get("source_path") or "")
                relative_path = str(payload.get("relative_path") or "")
                if not source_path:
                    continue
                path = Path(source_path).expanduser().resolve()
                if relative_path:
                    relative = Path(relative_path)
                    parts = relative.parts
                    if parts:
                        for _ in parts:
                            path = path.parent
                        return path
                return path.parent
    except OSError:
        return None
    return None


def resolve_payload_paths(payload: dict[str, Any]) -> tuple[Path, Path]:
    source_text = str(payload.get("source_dir") or "").strip()
    output_text = str(payload.get("output_root") or "").strip()
    if not source_text:
        raise ValueError("Source directory is required.")
    if not output_text:
        raise ValueError("Output directory is required.")
    source_dir = Path(source_text).expanduser().resolve()
    output_root = Path(output_text).expanduser().resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
    return source_dir, output_root


def resolve_analysis_paths(
    payload: dict[str, Any],
) -> tuple[Path, Path, tuple[Path, ...]]:
    source_text = str(payload.get("source_dir") or "").strip()
    output_text = str(payload.get("output_root") or "").strip()
    upload_id = str(payload.get("upload_id") or "").strip()
    if not output_text:
        raise ValueError("Output directory is required.")

    source_dir: Path | None = None
    if source_text:
        source_dir = Path(source_text).expanduser().resolve()
        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
        if not source_dir.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    upload_source: Path | None = None
    if upload_id:
        manifest = read_upload_manifest(upload_id)
        if not bool(manifest.get("complete")):
            raise ValueError("Upload workspace is not complete.")
        if int(manifest.get("file_count") or 0) <= 0:
            raise ValueError("Upload workspace has no files.")
        upload_source = upload_source_dir(upload_id).resolve()
        if not upload_source.is_dir():
            raise FileNotFoundError(f"Upload source directory does not exist: {upload_source}")

    if source_dir is None and upload_source is None:
        raise ValueError("A source directory or completed upload is required.")

    output_root = Path(output_text).expanduser().resolve()
    if source_dir is None:
        return upload_source, output_root, ()
    additional = (upload_source,) if upload_source is not None else ()
    return source_dir, output_root, additional


def paths_from_payload(payload: dict[str, Any]) -> ReadingPaths | None:
    source_text = str(payload.get("source_dir") or "").strip()
    output_text = str(payload.get("output_root") or "").strip()
    if not source_text and not output_text:
        return None
    source_dir, output_root = resolve_payload_paths(payload)
    return ReadingPaths(source_dir=source_dir, output_root=output_root)


def reading_paths_from_payload(
    app_state: AppState, payload: dict[str, Any]
) -> ReadingPaths | None:
    source_text = str(payload.get("source_dir") or "").strip()
    output_text = str(payload.get("output_root") or "").strip()
    if not source_text and not output_text:
        return None
    if source_text:
        source_dir, output_root = resolve_payload_paths(payload)
        return ReadingPaths(source_dir=source_dir, output_root=output_root)
    output_root = Path(output_text).expanduser().resolve()
    if not output_root.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_root}")
    return ReadingPaths(
        source_dir=infer_source_dir_for_output(app_state, output_root),
        output_root=output_root,
    )


def reading_request_paths(app_state: AppState, payload: dict[str, Any]) -> ReadingPaths:
    return reading_paths_from_payload(app_state, payload) or require_paths(app_state)


def task_key_for_output_root(output_root: Path) -> str:
    return os.path.normcase(str(output_root.expanduser().resolve()))


def task_key_for_paths(paths: ReadingPaths) -> str:
    return task_key_for_output_root(paths.output_root)


def managed_task_from_legacy(
    process: subprocess.Popen | None,
    command: list[str] | None,
    *,
    kind: str | None = None,
    started_epoch: float | None = None,
) -> ManagedProcessTask | None:
    if process is None:
        return None
    return ManagedProcessTask(
        process=process,
        command=command,
        kind=kind,
        started_epoch=started_epoch,
    )


def managed_task_for_paths(
    tasks: dict[str, ManagedProcessTask],
    paths: ReadingPaths | None,
    legacy_task: ManagedProcessTask | None = None,
) -> ManagedProcessTask | None:
    if paths is not None:
        key = task_key_for_paths(paths)
        task = tasks.get(key)
        if task is not None:
            return task
        for candidate in tasks.values():
            if paths_match_command(candidate.command, paths):
                return candidate
        if legacy_task is not None and paths_match_command(legacy_task.command, paths):
            return legacy_task
        return None

    for candidate in tasks.values():
        if candidate.process.poll() is None:
            return candidate
    if tasks:
        return next(iter(tasks.values()))
    return legacy_task


def analysis_task_for_paths(
    app_state: AppState, paths: ReadingPaths | None
) -> ManagedProcessTask | None:
    return managed_task_for_paths(
        app_state.analysis_tasks,
        paths,
        managed_task_from_legacy(
            app_state.process,
            app_state.process_command,
            started_epoch=app_state.process_started_epoch,
        ),
    )


def relationship_task_for_paths(
    app_state: AppState, paths: ReadingPaths | None
) -> ManagedProcessTask | None:
    return managed_task_for_paths(
        app_state.relationship_tasks,
        paths,
        managed_task_from_legacy(
            app_state.relationship_process,
            app_state.relationship_process_command,
            kind=app_state.relationship_process_kind,
        ),
    )


def rag_managed_task_for_paths(
    app_state: AppState, paths: ReadingPaths | None
) -> ManagedProcessTask | None:
    return managed_task_for_paths(
        app_state.rag_tasks,
        paths,
        managed_task_from_legacy(
            app_state.rag_process,
            app_state.rag_process_command,
            kind=app_state.rag_process_kind,
        ),
    )


def register_analysis_task(
    app_state: AppState,
    paths: ReadingPaths,
    process: subprocess.Popen,
    command: list[str],
    started_epoch: float,
) -> None:
    task = ManagedProcessTask(
        process=process,
        command=command,
        started_epoch=started_epoch,
    )
    app_state.analysis_tasks[task_key_for_paths(paths)] = task
    app_state.process = process
    app_state.process_command = command
    app_state.process_started_epoch = started_epoch
    completion_predicate = (
        (lambda: relationship_outputs_complete_after(paths, started_epoch))
        if command and "--mine-relationships" in command
        else None
    )
    watch_managed_process(
        app_state,
        paths,
        task,
        clear_analysis_task,
        completion_predicate=completion_predicate,
    )


def register_relationship_task(
    app_state: AppState,
    paths: ReadingPaths,
    process: subprocess.Popen,
    command: list[str],
    kind: str,
) -> None:
    started_epoch = time.time()
    task = ManagedProcessTask(
        process=process,
        command=command,
        kind=kind,
        started_epoch=started_epoch,
    )
    app_state.relationship_tasks[task_key_for_paths(paths)] = task
    app_state.relationship_process = process
    app_state.relationship_process_kind = kind
    app_state.relationship_process_command = command
    watch_managed_process(
        app_state,
        paths,
        task,
        clear_relationship_task,
        completion_predicate=lambda: relationship_outputs_complete_after(
            paths, started_epoch
        ),
    )


def register_rag_task(
    app_state: AppState,
    paths: ReadingPaths,
    process: subprocess.Popen,
    command: list[str],
    kind: str,
) -> None:
    task = ManagedProcessTask(
        process=process,
        command=command,
        kind=kind,
    )
    app_state.rag_tasks[task_key_for_paths(paths)] = task
    app_state.rag_process = process
    app_state.rag_process_kind = kind
    app_state.rag_process_command = command
    watch_managed_process(app_state, paths, task, clear_rag_task)


def clear_analysis_task(
    app_state: AppState, paths: ReadingPaths | None, task: ManagedProcessTask | None
) -> None:
    if paths is not None:
        app_state.analysis_tasks.pop(task_key_for_paths(paths), None)
    elif task is not None:
        for key, candidate in list(app_state.analysis_tasks.items()):
            if candidate.process is task.process:
                app_state.analysis_tasks.pop(key, None)
    if task is not None and app_state.process is task.process:
        app_state.process = None
        app_state.process_command = None
        app_state.process_started_epoch = None


def clear_relationship_task(
    app_state: AppState, paths: ReadingPaths | None, task: ManagedProcessTask | None
) -> None:
    if paths is not None:
        app_state.relationship_tasks.pop(task_key_for_paths(paths), None)
    elif task is not None:
        for key, candidate in list(app_state.relationship_tasks.items()):
            if candidate.process is task.process:
                app_state.relationship_tasks.pop(key, None)
    if task is not None and app_state.relationship_process is task.process:
        app_state.relationship_process = None
        app_state.relationship_process_kind = None
        app_state.relationship_process_command = None


def watch_managed_process(
    app_state: AppState,
    paths: ReadingPaths | None,
    task: ManagedProcessTask,
    clear_callback: Callable[[AppState, ReadingPaths | None, ManagedProcessTask | None], None],
    *,
    completion_predicate: Callable[[], bool] | None = None,
) -> None:
    threading.Thread(
        target=_watch_managed_process_worker,
        args=(app_state, paths, task, clear_callback, completion_predicate),
        name="doctriage-task-watch",
        daemon=True,
    ).start()


def _watch_managed_process_worker(
    app_state: AppState,
    paths: ReadingPaths | None,
    task: ManagedProcessTask,
    clear_callback: Callable[[AppState, ReadingPaths | None, ManagedProcessTask | None], None],
    completion_predicate: Callable[[], bool] | None,
) -> None:
    process = task.process
    while process.poll() is None:
        if completion_predicate is not None:
            try:
                completed = bool(completion_predicate())
            except OSError:
                completed = False
            if completed:
                if task.cleanup_started:
                    return
                task.cleanup_started = True
                _reap_completed_managed_process_worker(
                    app_state,
                    paths,
                    task,
                    clear_callback,
                    COMPLETED_TASK_PROCESS_GRACE_SECONDS,
                )
                return
        time.sleep(TASK_WATCH_POLL_SECONDS)

    with app_state.lock:
        clear_callback(app_state, paths, task)


def reap_completed_managed_process(
    app_state: AppState,
    paths: ReadingPaths | None,
    task: ManagedProcessTask | None,
    clear_callback: Callable[[AppState, ReadingPaths | None, ManagedProcessTask | None], None],
    *,
    timeout_seconds: float | None = None,
) -> None:
    if task is None or task.cleanup_started:
        return
    task.cleanup_started = True
    effective_timeout = (
        COMPLETED_TASK_PROCESS_GRACE_SECONDS
        if timeout_seconds is None
        else timeout_seconds
    )
    threading.Thread(
        target=_reap_completed_managed_process_worker,
        args=(app_state, paths, task, clear_callback, effective_timeout),
        name="doctriage-task-reaper",
        daemon=True,
    ).start()


def _reap_completed_managed_process_worker(
    app_state: AppState,
    paths: ReadingPaths | None,
    task: ManagedProcessTask,
    clear_callback: Callable[[AppState, ReadingPaths | None, ManagedProcessTask | None], None],
    timeout_seconds: float,
) -> None:
    process = task.process
    if process.poll() is None:
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            terminate_process_tree(process, timeout_seconds=5.0)
        except (OSError, subprocess.SubprocessError, AttributeError):
            pass
    with app_state.lock:
        if process.poll() is not None:
            clear_callback(app_state, paths, task)


def clear_rag_task(
    app_state: AppState, paths: ReadingPaths | None, task: ManagedProcessTask | None
) -> None:
    if paths is not None:
        app_state.rag_tasks.pop(task_key_for_paths(paths), None)
    elif task is not None:
        for key, candidate in list(app_state.rag_tasks.items()):
            if candidate.process is task.process:
                app_state.rag_tasks.pop(key, None)
    if task is not None and app_state.rag_process is task.process:
        app_state.rag_process = None
        app_state.rag_process_kind = None
        app_state.rag_process_command = None


def paths_match_command(command: list[str] | None, paths: ReadingPaths) -> bool:
    if not command:
        return False
    command_output = command_option_path(command, "--output-root")
    if command_output is None:
        return False
    try:
        return command_output.resolve() == paths.output_root.resolve()
    except OSError:
        return False


def command_option_path(command: list[str], option: str) -> Path | None:
    value = command_option_value(command, option)
    return Path(value).expanduser() if value else None


def command_option_value(command: list[str], option: str) -> str | None:
    try:
        index = command.index(option)
    except ValueError:
        return None
    if index + 1 >= len(command):
        return None
    return command[index + 1]


def build_analysis_command(
    payload: dict[str, Any],
    source_dir: Path,
    output_root: Path,
    *,
    additional_source_dirs: tuple[Path, ...] = (),
) -> list[str]:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "main.py"),
        "--source-dir",
        str(source_dir),
    ]
    for additional_source_dir in additional_source_dirs:
        command.extend(["--source-dir", str(additional_source_dir)])
    command.extend(
        [
            "--output-root",
            str(output_root),
            "--llm-endpoint",
            str(payload.get("llm_endpoint") or "http://localhost:11434/api/generate"),
        ]
    )
    llm_model = str(payload.get("llm_model") or "").strip()
    if llm_model:
        command.extend(["--llm-model", llm_model])
    output_language = str(payload.get("output_language") or "auto").strip()
    if output_language:
        command.extend(["--output-language", output_language])
    relationship_use_embeddings = bool(payload.get("relationship_use_embeddings"))
    embedding_model = str(payload.get("embedding_model") or "").strip()
    if relationship_use_embeddings and not embedding_model:
        raise ValueError(
            "Embedding model is required when embedding relationships are enabled."
        )
    if relationship_use_embeddings:
        embedding_endpoint = str(payload.get("embedding_endpoint") or "").strip()
        if embedding_endpoint:
            command.extend(["--embedding-endpoint", embedding_endpoint])
        command.extend(["--embedding-model", embedding_model])

    option_map = {
        "concurrency": "--concurrency",
        "limit": "--limit",
        "max_file_size_mb": "--max-file-size-mb",
        "quality_threshold": "--quality-threshold",
        "timeout_seconds": "--timeout-seconds",
    }
    for payload_key, option_name in option_map.items():
        value = str(payload.get(payload_key) or "").strip()
        if value:
            command.extend([option_name, value])

    if "ocr_enabled" in payload:
        command.append("--ocr" if bool(payload.get("ocr_enabled")) else "--no-ocr")
    elif bool(payload.get("no_ocr")):
        command.append("--no-ocr")
    if "manifest_analysis" in payload:
        command.append(
            "--manifest-analysis"
            if bool(payload.get("manifest_analysis"))
            else "--skip-manifest-analysis"
        )
    elif bool(payload.get("skip_manifest_analysis")):
        command.append("--skip-manifest-analysis")

    flag_map = {
        "plan_only": "--plan-only",
        "force_reprocess": "--force-reprocess",
        "content_hash": "--content-hash",
        "mine_relationships": "--mine-relationships",
        "relationship_use_text_citations": "--relationship-use-text-citations",
        "relationship_use_embeddings": "--relationship-use-embeddings",
    }
    for payload_key, option_name in flag_map.items():
        if bool(payload.get(payload_key)):
            command.append(option_name)
    return command


def is_plan_only_command(command: list[str] | None) -> bool:
    return bool(command and "--plan-only" in command)


def run_lock_path(output_root: Path) -> Path:
    return output_root / "_state" / "run.lock"


def relationship_task_record_path(paths: ReadingPaths) -> Path:
    return relationship_dir(paths) / "task.json"


def relationship_task_from_record(paths: ReadingPaths) -> dict[str, Any] | None:
    record_path = relationship_task_record_path(paths)
    info = read_json_file(record_path)
    pid = coerce_pid(info.get("pid"))
    if pid is None:
        return None
    created_epoch = coerce_float_value(info.get("created_epoch"), 0.0)
    if not is_process_alive(pid):
        remove_relationship_task_record(record_path)
        return None
    if relationship_outputs_complete_after(paths, created_epoch):
        remove_relationship_task_record(record_path)
        return None
    command_payload = info.get("command")
    command = command_payload if isinstance(command_payload, list) else None
    kind = str(info.get("kind") or "mine")
    return {
        "running": True,
        "pid": pid,
        "kind": kind,
        "command": command,
        "return_code": None,
        "source_dir": str(info.get("source_dir") or paths.source_dir),
        "output_root": str(info.get("output_root") or paths.output_root),
        "task_record": str(record_path),
    }


def remove_relationship_task_record(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def find_active_relationship_task_pid(paths: ReadingPaths) -> int | None:
    payload = relationship_task_from_record(paths)
    if payload is None:
        return None
    return coerce_pid(payload.get("pid"))


def read_run_lock(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return {}


def coerce_pid(value: Any) -> int | None:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return True
        output = decode_process_output(result.stdout)
        return str(pid) in output
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def find_active_run_pid(paths: ReadingPaths) -> int | None:
    lock_info = read_run_lock(run_lock_path(paths.output_root))
    return active_run_pid_from_lock_info(lock_info)


def active_run_pid_from_lock_info(lock_info: dict[str, Any]) -> int | None:
    pid = coerce_pid(lock_info.get("pid"))
    if pid is None or not is_process_alive(pid):
        return None
    return pid


def run_lock_status(paths: ReadingPaths) -> dict[str, Any]:
    path = run_lock_path(paths.output_root)
    info = read_run_lock(path)
    pid = coerce_pid(info.get("pid"))
    active = pid is not None and is_process_alive(pid)
    return {
        "exists": path.exists(),
        "pid": pid,
        "active": active,
        "source_dir": str(info.get("source_dir") or ""),
        "output_root": str(info.get("output_root") or ""),
        "created_epoch": info.get("created_epoch"),
    }


def terminate_process_id(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0 or not is_process_alive(pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


def path_contains(parent: Path, child: Path) -> bool:
    return parent == child or parent in child.parents


def validate_reset_output_root(source_dir: Path, output_root: Path) -> None:
    if output_root == output_root.parent:
        raise ValueError(f"Refusing to reset filesystem root: {output_root}")
    if source_dir == output_root:
        raise ValueError(
            "Refusing to reset because source directory and output directory are the same."
        )
    if path_contains(source_dir, output_root):
        raise ValueError(
            "Refusing to reset because output directory is inside the source directory."
        )
    if path_contains(output_root, source_dir):
        raise ValueError(
            "Refusing to reset because output directory contains the source directory."
        )


def clear_output_root_contents(output_root: Path) -> None:
    if not output_root.exists():
        return
    for child in output_root.iterdir():
        if child.is_symlink() or child.is_file():
            child.unlink()
            continue
        if child.is_dir():
            shutil.rmtree(child)
            continue
        child.unlink()


def reset_analysis_output(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    source_dir, output_root = resolve_payload_paths(payload)
    validate_reset_output_root(source_dir, output_root)
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    clear_source_file_scan_cache(source_dir)

    with app_state.lock:
        analysis_task = analysis_task_for_paths(app_state, paths)
        process = analysis_task.process if analysis_task is not None else None
        if process is not None and process.poll() is None:
            raise RuntimeError("Cannot reset output while analysis is running.")
        relationship_task = relationship_task_for_paths(app_state, paths)
        relationship_process = (
            relationship_task.process if relationship_task is not None else None
        )
        if (
            relationship_process is not None
            and relationship_process.poll() is None
        ):
            raise RuntimeError(
                "Cannot reset output while a relationship task is running for this output."
            )
        rag_task = rag_managed_task_for_paths(app_state, paths)
        rag_process = rag_task.process if rag_task is not None else None
        if (
            rag_process is not None
            and rag_process.poll() is None
        ):
            raise RuntimeError(
                "Cannot reset output while a RAG indexing task is running for this output."
            )
        active_pid = find_active_run_pid(paths)
        if active_pid is not None:
            raise RuntimeError(
                f"Cannot reset output while analysis is running with PID {active_pid}."
            )
        active_relationship_pid = find_active_relationship_task_pid(paths)
        if active_relationship_pid is not None:
            raise RuntimeError(
                f"Cannot reset output while a relationship task is running with PID {active_relationship_pid}."
            )

        clear_output_root_contents(output_root)
        output_root.mkdir(parents=True, exist_ok=True)
        (output_root / "_state").mkdir(parents=True, exist_ok=True)
        (output_root / "_logs").mkdir(parents=True, exist_ok=True)
        app_state.paths = paths
        clear_analysis_task(app_state, paths, analysis_task)

    return {
        "reset": True,
        "source_dir": str(source_dir),
        "output_root": str(output_root),
    }


def reset_relationship_output(app_state: AppState, payload: dict[str, Any]) -> dict[str, Any]:
    source_dir, output_root = resolve_payload_paths(payload)
    validate_reset_output_root(source_dir, output_root)
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    target_dir = relationship_dir(paths)

    with app_state.lock:
        analysis_task = analysis_task_for_paths(app_state, paths)
        process = analysis_task.process if analysis_task is not None else None
        if process is not None and process.poll() is None:
            raise RuntimeError("Cannot reset relationships while analysis is running.")
        relationship_task = relationship_task_for_paths(app_state, paths)
        relationship_process = (
            relationship_task.process if relationship_task is not None else None
        )
        if (
            relationship_process is not None
            and relationship_process.poll() is None
        ):
            raise RuntimeError(
                "Cannot reset relationships while a relationship task is running for this output."
            )
        rag_task = rag_managed_task_for_paths(app_state, paths)
        rag_process = rag_task.process if rag_task is not None else None
        if (
            rag_process is not None
            and rag_process.poll() is None
        ):
            raise RuntimeError(
                "Cannot reset relationships while a RAG indexing task is running for this output."
            )
        active_pid = find_active_run_pid(paths)
        if active_pid is not None:
            raise RuntimeError(
                f"Cannot reset relationships while analysis is running with PID {active_pid}."
            )
        active_relationship_pid = find_active_relationship_task_pid(paths)
        if active_relationship_pid is not None:
            raise RuntimeError(
                f"Cannot reset relationships while a relationship task is running with PID {active_relationship_pid}."
            )

        if target_dir.exists():
            if target_dir.is_symlink() or target_dir.is_file():
                target_dir.unlink()
            else:
                shutil.rmtree(target_dir)
        relationship_progress = relationship_progress_path(paths)
        if relationship_progress.exists():
            relationship_progress.unlink()
        app_state.paths = paths
        if relationship_process is not None and relationship_process.poll() is not None:
            clear_relationship_task(app_state, paths, relationship_task)

    return {
        "reset": True,
        "source_dir": str(source_dir),
        "output_root": str(output_root),
        "relationship_dir": str(target_dir),
    }


def stop_analysis(app_state: AppState, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    requested_paths = paths_from_payload(payload or {})
    with app_state.lock:
        paths = requested_paths or app_state.paths
        if paths is not None:
            clear_source_file_scan_cache(paths.source_dir)
        task = analysis_task_for_paths(app_state, paths)
        process = task.process if task is not None else None
        if process is not None and process.poll() is None:
            stopped = terminate_process_tree(process, timeout_seconds=5.0)
            running = process.poll() is None
            if not running:
                clear_analysis_task(app_state, paths, task)
            return {
                "stopped": stopped,
                "running": running,
                "pid": process.pid,
            }
        if process is not None:
            clear_analysis_task(app_state, paths, task)
        if paths is None:
            return {"stopped": False, "running": False}
        pid = find_active_run_pid(paths)
        if pid is None:
            return {"stopped": False, "running": False}
        stopped = terminate_process_id(pid)
        return {"stopped": stopped, "running": is_process_alive(pid), "pid": pid}


def start_early_relationships(
    app_state: AppState, payload: dict[str, Any]
) -> dict[str, Any]:
    paths = reading_paths_from_payload(app_state, payload) or require_paths(app_state)
    relationship_payload = {
        **payload,
        "source_dir": str(paths.source_dir),
        "output_root": str(paths.output_root),
        "mine_relationships": True,
        "relationship_use_text_citations": True,
        "relationship_use_embeddings": bool(payload.get("relationship_use_embeddings")),
    }
    relationship_task_command("mine", relationship_payload, paths)

    with app_state.lock:
        relationship_task = relationship_task_for_paths(app_state, paths)
        relationship_process = (
            relationship_task.process if relationship_task is not None else None
        )
        if relationship_process is not None and relationship_process.poll() is None:
            raise RuntimeError(
                "Another relationship task is already running for this output."
            )
        active_relationship_pid = find_active_relationship_task_pid(paths)
        if active_relationship_pid is not None:
            raise RuntimeError(
                f"Relationship task is already running for this output with PID {active_relationship_pid}."
            )

    stop_result = stop_analysis(app_state, relationship_payload)
    if stop_result.get("running"):
        raise RuntimeError("Analysis did not stop; relationship mining was not started.")
    if not paths.decisions_path.exists() or count_nonempty_lines(paths.decisions_path) == 0:
        raise RuntimeError(
            "No scored decision records found yet. Wait until at least one document is scored."
        )

    task_result = start_relationship_task(app_state, relationship_payload, "mine")
    return {
        "started": True,
        "stopped": bool(stop_result.get("stopped")),
        "stop": stop_result,
        "relationship": task_result,
        "source_dir": str(paths.source_dir),
        "output_root": str(paths.output_root),
    }


def wait_for_process_exit(process: subprocess.Popen, timeout_seconds: float) -> bool:
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return False
    return True


def terminate_process_tree(
    process: subprocess.Popen, timeout_seconds: float = 5.0
) -> bool:
    if os.name == "nt" and isinstance(process, SUBPROCESS_POPEN_TYPE):
        stopped = terminate_process_id(process.pid)
        try:
            process.wait(timeout=timeout_seconds)
        except (OSError, subprocess.SubprocessError):
            pass
        return stopped or process.poll() is not None
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        except (OSError, PermissionError):
            try:
                process.terminate()
            except (OSError, subprocess.SubprocessError):
                return False
        stopped = wait_for_process_exit(process, timeout_seconds=timeout_seconds)
        if not stopped:
            stopped = kill_process(process)
        return stopped
    try:
        process.terminate()
    except (OSError, subprocess.SubprocessError):
        return False
    stopped = wait_for_process_exit(process, timeout_seconds=timeout_seconds)
    if not stopped:
        stopped = kill_process(process)
    return stopped


def kill_process(process: subprocess.Popen) -> bool:
    if os.name == "nt" and isinstance(process, SUBPROCESS_POPEN_TYPE):
        stopped = terminate_process_id(process.pid)
        try:
            process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
        return stopped or process.poll() is not None
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return True
        except (OSError, PermissionError):
            try:
                process.kill()
            except (OSError, subprocess.SubprocessError):
                return False
        try:
            process.wait(timeout=5)
        except (OSError, subprocess.SubprocessError):
            return False
        return process.poll() is not None
    try:
        process.kill()
        process.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return process.poll() is not None


def infer_analysis_phase(
    *,
    running: bool,
    progress: dict[str, Any],
    log_tail: str,
    decisions_exists: bool,
    command: list[str] | None = None,
    embedding_progress: dict[str, Any] | None = None,
    active_started_epoch: float | None = None,
    relations_exists: bool = False,
    clusters_exists: bool = False,
    relationship_outputs_current: bool = False,
    run_summary: dict[str, Any] | None = None,
) -> str:
    completed = coerce_int_value(progress.get("completed"), 0)
    remaining = coerce_int_value(progress.get("remaining"), 0)
    total = coerce_int_value(progress.get("total"), 0)
    submitted = coerce_int_value(progress.get("submitted"), 0)
    planned = coerce_int_value(progress.get("planned"), 0)
    succeeded = coerce_int_value(progress.get("succeeded"), 0)
    skipped_resumed = coerce_int_value(progress.get("skipped_resumed"), 0)

    if relationship_outputs_current or (not running and relations_exists and clusters_exists):
        if unresolved_failures_from_summary_or_progress(run_summary, progress) > 0:
            return "分析完成，仍有失败"
        return "分析完成，关系已生成"

    if running:
        if inline_relationship_mining_is_active(
            running=True,
            command=command,
            log_tail=log_tail,
            progress=progress,
            embedding_progress=embedding_progress,
            active_started_epoch=active_started_epoch,
        ):
            return "关系挖掘中"
        if decisions_exists and completed == 0 and submitted == 0 and skipped_resumed == 0:
            return "续传准备中"
        if skipped_resumed > 0 and submitted == 0:
            return "续传跳过中"
        if submitted > 0 or planned > 0 or succeeded > 0:
            return "文档评分中"
        return "扫描准备中"

    summary = run_summary or {}
    unresolved_failures = unresolved_failures_from_summary_or_progress(
        run_summary, progress
    )
    if total > 0 and remaining == 0:
        if unresolved_failures > 0:
            return "分析完成，仍有失败"
        if relations_exists and clusters_exists:
            return "分析完成，关系已生成"
        if decisions_exists:
            return "分析完成，关系未生成"
        return "分析完成"
    if completed > 0 or decisions_exists:
        return "已停止，可续传"
    return "未启动"


def unresolved_failures_from_summary_or_progress(
    run_summary: dict[str, Any] | None,
    progress: dict[str, Any],
) -> int:
    summary = run_summary or {}
    return coerce_int_value(
        summary.get("unresolved_failures"), coerce_int_value(progress.get("failed"), 0)
    )


def analysis_status(
    app_state: AppState, paths: ReadingPaths | None = None
) -> dict[str, Any]:
    with app_state.lock:
        active_paths = app_state.paths
        paths = paths or active_paths
        task = analysis_task_for_paths(app_state, paths)
        process = task.process if task is not None else None
        command = task.command if task is not None else None
        process_started_epoch = task.started_epoch if task is not None else None
        local_running = (
            process is not None
            and process.poll() is None
            and (paths is None or paths_match_command(command, paths))
        )
        local_pid = (
            process.pid
            if process is not None
            and (paths is None or paths_match_command(command, paths))
            else None
        )
        return_code = None if process is None else process.poll()
        if process is not None and process.poll() is not None:
            clear_analysis_task(app_state, paths, task)
            process_started_epoch = None

    if paths is None:
        return {
            "running": local_running,
            "plan_only": False,
            "phase": "未启动",
            "pid": local_pid,
            "return_code": return_code,
            "command": command,
            "source_dir": "",
            "output_root": "",
            "progress": {},
            "log_tail": "",
            "decisions_exists": False,
            "run_lock": {"exists": False, "pid": None, "active": False},
            "activity": {
                "state_counts": {},
                "state_files": {},
                "latest_activity": {"label": "", "detail": "", "line": ""},
            },
            "run_summary": {},
            "relationship_task": {"running": False, "pid": None, "kind": None},
            "rag_task": {"running": False, "pid": None, "kind": None},
            "embedding_progress": {},
        }

    effective_concurrency = infer_effective_concurrency(command)
    progress = read_json_file(paths.progress_path)
    run_summary = read_json_file(paths.output_root / "_state" / "run_summary.json")
    log_tail = read_text_tail(paths.application_log_path, max_lines=80)
    embedding_progress = read_json_file(relationship_embedding_progress_path(paths))
    plan_only = infer_plan_only_mode(command, progress, run_summary)
    decisions_exists = paths.decisions_path.exists()
    lock_status = run_lock_status(paths)
    active_started_epoch = (
        process_started_epoch
        if local_running
        else coerce_float_value(lock_status.get("created_epoch"), 0.0)
    )
    relationship_outputs_current = relationship_outputs_complete_after(
        paths, active_started_epoch
    )
    active_pid = find_active_run_pid(paths)
    running = (local_running or active_pid is not None) and not relationship_outputs_current
    pid = local_pid if local_running else active_pid
    if relationship_outputs_current:
        if task is not None:
            reap_completed_managed_process(app_state, paths, task, clear_analysis_task)
        pid = None
        return_code = 0 if return_code is None else return_code
    elif running and not local_running:
        return_code = None

    return {
        "running": running,
        "plan_only": plan_only,
        "phase": infer_analysis_phase(
            running=running,
            progress=progress,
            log_tail=log_tail,
            decisions_exists=decisions_exists,
            command=command,
            embedding_progress=embedding_progress,
            active_started_epoch=active_started_epoch,
            relations_exists=relationship_relations_path(paths).exists(),
            clusters_exists=relationship_clusters_path(paths).exists(),
            relationship_outputs_current=relationship_outputs_current,
            run_summary=run_summary,
        ),
        "pid": pid,
        "return_code": return_code,
        "command": command,
        "effective_concurrency": effective_concurrency,
        "source_dir": str(paths.source_dir),
        "output_root": str(paths.output_root),
        "progress": progress,
        "log_tail": log_tail,
        "decisions_exists": decisions_exists,
        "run_lock": lock_status,
        "activity": build_analysis_activity(paths, log_tail),
        "run_summary": run_summary,
        "relationship_task": relationship_task_status(app_state, paths),
        "rag_task": rag_task_status(app_state, paths),
        "embedding_progress": embedding_progress,
    }


def infer_plan_only_mode(
    command: list[str] | None,
    progress: dict[str, Any] | None = None,
    run_summary: dict[str, Any] | None = None,
) -> bool:
    if is_plan_only_command(command):
        return True
    for payload in (progress, run_summary):
        if isinstance(payload, dict) and isinstance(payload.get("plan_only"), bool):
            return bool(payload["plan_only"])
    return False


def infer_effective_concurrency(command: list[str] | None) -> str:
    if command:
        value = command_option_value(command, "--concurrency")
        if value:
            return value
    return ""


def require_paths(app_state: AppState) -> ReadingPaths:
    paths = app_state.paths
    if paths is None:
        raise ValueError("Please select and apply source/output directories first.")
    return paths


def pick_folder() -> dict[str, str]:
    if not can_use_folder_picker():
        raise RuntimeError(
            "Folder picker is unavailable in this environment. "
            "Please type the folder path manually."
        )
    if os.name == "nt":
        return {"path": pick_folder_windows()}
    if sys.platform == "darwin" and macos_folder_picker_command() is not None:
        return {"path": pick_folder_macos()}
    if sys.platform.startswith("linux") and linux_folder_picker_command() is not None:
        return {"path": pick_folder_linux()}
    return {"path": pick_folder_tkinter()}


def pick_folder_tkinter() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise RuntimeError(f"Folder picker is unavailable: {exc}") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory()
    finally:
        root.destroy()
    return selected or ""


def macos_folder_picker_command() -> str | None:
    return shutil.which("osascript")


def pick_folder_macos() -> str:
    command = macos_folder_picker_command()
    if command is None:
        raise RuntimeError("macOS folder picker requires osascript.")
    return run_folder_picker_command(
        [
            command,
            "-e",
            'POSIX path of (choose folder with prompt "Select DocTriage folder")',
        ],
        label="macOS",
        cancel_codes={1},
    )


def linux_folder_picker_command() -> tuple[str, str] | None:
    zenity = shutil.which("zenity")
    if zenity:
        return "zenity", zenity
    kdialog = shutil.which("kdialog")
    if kdialog:
        return "kdialog", kdialog
    return None


def pick_folder_linux() -> str:
    picker = linux_folder_picker_command()
    if picker is None:
        raise RuntimeError("Linux folder picker requires zenity or kdialog.")
    kind, command = picker
    arguments = (
        [command, "--file-selection", "--directory", "--title=Select DocTriage folder"]
        if kind == "zenity"
        else [command, "--getexistingdirectory", ".", "--title", "Select DocTriage folder"]
    )
    return run_folder_picker_command(
        arguments,
        label="Linux",
        cancel_codes={1},
    )


def run_folder_picker_command(
    command: list[str],
    *,
    label: str,
    cancel_codes: set[int],
) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=False,
            timeout=None,
        )
    except OSError as exc:
        raise RuntimeError(f"{label} folder picker failed to start: {exc}") from exc
    stdout = decode_process_output(result.stdout).strip()
    stderr = decode_process_output(result.stderr).strip()
    if result.returncode in cancel_codes and not stdout:
        return ""
    if result.returncode != 0:
        raise RuntimeError(f"{label} folder picker failed: {stderr or stdout}")
    return stdout


def windows_folder_picker_command() -> str | None:
    return shutil.which("powershell") or shutil.which("pwsh")


def pick_folder_windows() -> str:
    command = windows_folder_picker_command()
    if command is None:
        raise RuntimeError(
            "Windows folder picker requires PowerShell. "
            "Please type the folder path manually."
        )
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$dialog.Description = 'Select DocTriage folder'; "
        "$dialog.ShowNewFolderButton = $true; "
        "$result = $dialog.ShowDialog(); "
        "if ($result -eq [System.Windows.Forms.DialogResult]::OK) { "
        "Write-Output $dialog.SelectedPath }"
    )
    try:
        result = subprocess.run(
            [command, "-NoProfile", "-STA", "-Command", script],
            capture_output=True,
            text=False,
            timeout=None,
        )
    except OSError as exc:
        raise RuntimeError(f"Windows folder picker failed to start: {exc}") from exc
    stdout = decode_process_output(result.stdout)
    stderr = decode_process_output(result.stderr)
    if result.returncode != 0:
        error = (stderr or stdout).strip()
        raise RuntimeError(f"Windows folder picker failed: {error}")
    return stdout.strip()


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_text_tail(path: Path, max_lines: int) -> str:
    if not path.exists():
        return ""
    try:
        data = read_tail_bytes(path)
    except OSError:
        return ""
    lines = data.splitlines(keepends=True)
    return "".join(decode_log_line(line) for line in lines[-max_lines:])


def read_tail_bytes(path: Path, max_bytes: int = 1024 * 1024) -> bytes:
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > max_bytes:
            handle.seek(size - max_bytes)
            handle.readline()
        return handle.read()


def decode_log_line(line: bytes) -> str:
    return decode_process_output(line)


def file_activity(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "size": 0, "updated_at": "", "age_seconds": None}
    try:
        stat = path.stat()
    except OSError:
        return {"exists": False, "size": 0, "updated_at": "", "age_seconds": None}
    updated_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc).astimezone()
    age_seconds = max(0.0, datetime.now(timezone.utc).timestamp() - stat.st_mtime)
    return {
        "exists": True,
        "size": stat.st_size,
        "updated_at": updated_at.isoformat(),
        "age_seconds": round(age_seconds, 1),
    }


def count_nonempty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for line in handle if line.strip())
    except OSError:
        return 0


def latest_log_activity(log_tail: str) -> dict[str, str]:
    lines = [line.strip() for line in log_tail.splitlines() if line.strip()]
    if not lines:
        return {"label": "", "detail": "", "line": ""}

    selected = ""
    for line in reversed(lines):
        if " doctriage - " in line:
            selected = line
            break
    if not selected:
        selected = lines[-1]

    return {"label": "", "detail": "", "line": selected}


def build_analysis_activity(paths: ReadingPaths, log_tail: str) -> dict[str, Any]:
    return {
        "state_counts": {
            "decisions": count_nonempty_lines(paths.decisions_path),
            "processed": count_nonempty_lines(paths.output_root / "_state" / "processed_files.jsonl"),
            "failed": count_nonempty_lines(paths.output_root / "_state" / "failed_files.jsonl"),
        },
        "state_files": {
            "decisions": file_activity(paths.decisions_path),
            "processed": file_activity(paths.output_root / "_state" / "processed_files.jsonl"),
            "failed": file_activity(paths.output_root / "_state" / "failed_files.jsonl"),
            "progress": file_activity(paths.progress_path),
            "log": file_activity(paths.application_log_path),
        },
        "latest_activity": latest_log_activity(log_tail),
    }


def mark_document(paths: ReadingPaths, payload: dict[str, Any]) -> dict[str, Any]:
    decisions = safe_load_decisions(paths)
    relative_path = str(payload.get("relative_path") or payload.get("path") or "")
    status = str(payload.get("status") or "")
    note = str(payload.get("note") or "")
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"Unsupported reading status: {status}")
    if resolves_to_decision(relative_path, paths, decisions):
        return append_reading_event(
            paths,
            decisions,
            requested_path=relative_path,
            status=status,
            note=note,
        )
    source_path, source_relative_path = resolve_source_document(paths, payload, decisions)
    return append_source_reading_event(
        paths,
        source_path=source_path,
        relative_path=source_relative_path,
        status=status,
        note=note,
    )


def mark_document_request(
    app_state: AppState, payload: dict[str, Any]
) -> dict[str, Any]:
    return mark_document(reading_request_paths(app_state, payload), payload)


def safe_load_decisions(paths: ReadingPaths) -> dict[str, dict[str, Any]]:
    try:
        return load_latest_decisions(paths.decisions_path)
    except FileNotFoundError:
        return {}


def resolves_to_decision(
    requested_path: str,
    paths: ReadingPaths,
    decisions: dict[str, dict[str, Any]],
) -> bool:
    try:
        append_relative_path = resolve_relative_path_for_decisions(
            requested_path, paths, decisions
        )
    except ValueError:
        return False
    return append_relative_path in decisions


def resolve_relative_path_for_decisions(
    requested_path: str,
    paths: ReadingPaths,
    decisions: dict[str, dict[str, Any]],
) -> str:
    from reading_tracker import resolve_relative_path

    return resolve_relative_path(requested_path, paths.source_dir, decisions)


def append_source_reading_event(
    paths: ReadingPaths,
    *,
    source_path: Path,
    relative_path: str,
    status: str,
    note: str = "",
) -> dict[str, Any]:
    stat_payload = stat_source_file(source_path)
    fingerprint = {
        "size_bytes": stat_payload.get("source_size_bytes"),
        "mtime_ns": stat_payload.get("source_mtime_ns"),
        "ctime_ns": stat_payload.get("source_ctime_ns"),
    }
    event = {
        "relative_path": relative_path,
        "source_path": str(source_path),
        "status": status,
        "note": note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint,
        "quality": None,
        "category": None,
    }
    paths.reading_status_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.reading_status_path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def resolve_source_document(
    paths: ReadingPaths,
    payload: dict[str, Any],
    decisions: dict[str, dict[str, Any]] | None = None,
) -> tuple[Path, str]:
    if decisions is None:
        decisions = safe_load_decisions(paths)
    relative_path = str(payload.get("relative_path") or payload.get("path") or "").strip()
    source_text = str(payload.get("source_path") or "").strip()
    requested = source_text or relative_path
    if not requested:
        raise ValueError("Missing document path")

    if relative_path:
        decision = decisions.get(relative_path)
        if decision and decision.get("source_path"):
            source_path = Path(str(decision["source_path"]))
            return source_path, relative_path

    source_dir = paths.source_dir.resolve()
    candidates: list[Path] = []
    raw_path = Path(requested)
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.append(source_dir / requested)
        normalized = requested.replace("\\", "/")
        if normalized != requested:
            candidates.append(source_dir / normalized)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(source_dir)
        except (OSError, ValueError):
            continue
        if resolved.exists() and resolved.is_file():
            return resolved, resolved.relative_to(source_dir).as_posix()

    normalized_requested = requested.replace("\\", "/")
    matches: list[Path] = []
    for path in iter_supported_source_files(source_dir):
        relative = source_relative_path(paths, path)
        if relative == normalized_requested or relative.endswith(normalized_requested) or path.name == requested:
            matches.append(path)
    if len(matches) == 1:
        resolved = matches[0].resolve()
        return resolved, resolved.relative_to(source_dir).as_posix()
    if len(matches) > 1:
        raise ValueError(f"Ambiguous source document path: {requested}")
    raise ValueError(f"Unknown source document: {requested}")


def mark_documents(paths: ReadingPaths, payload: dict[str, Any]) -> dict[str, Any]:
    decisions = safe_load_decisions(paths)
    raw_paths = payload.get("relative_paths") or []
    if not isinstance(raw_paths, list):
        raise ValueError("relative_paths must be a list")
    status = str(payload.get("status") or "")
    note = str(payload.get("note") or "")
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"Unsupported reading status: {status}")

    events = []
    for relative_path in raw_paths:
        text = str(relative_path)
        if resolves_to_decision(text, paths, decisions):
            events.append(
                append_reading_event(
                    paths,
                    decisions,
                    requested_path=text,
                    status=status,
                    note=note,
                )
            )
            continue
        source_path, source_relative_path = resolve_source_document(
            paths, {"relative_path": text}, decisions
        )
        events.append(
            append_source_reading_event(
                paths,
                source_path=source_path,
                relative_path=source_relative_path,
                status=status,
                note=note,
            )
        )
    return {"count": len(events), "events": events}


def mark_documents_request(
    app_state: AppState, payload: dict[str, Any]
) -> dict[str, Any]:
    return mark_documents(reading_request_paths(app_state, payload), payload)


def open_document(paths: ReadingPaths, payload: dict[str, Any], *, reveal: bool) -> dict[str, Any]:
    source_path, _relative_path = resolve_source_document(paths, payload)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    if reveal:
        reveal_path(source_path)
    else:
        open_path(source_path)
    return {"ok": True, "source_path": str(source_path)}


def open_document_request(
    app_state: AppState, payload: dict[str, Any], *, reveal: bool
) -> dict[str, Any]:
    return open_document(reading_request_paths(app_state, payload), payload, reveal=reveal)


def open_failure_document(
    paths: ReadingPaths, payload: dict[str, Any], *, reveal: bool
) -> dict[str, Any]:
    source_path = resolve_failure_source(paths, payload)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file does not exist: {source_path}")

    if reveal:
        reveal_path(source_path)
    else:
        open_path(source_path)
    return {"ok": True, "source_path": str(source_path)}


def open_failure_document_request(
    app_state: AppState, payload: dict[str, Any], *, reveal: bool
) -> dict[str, Any]:
    return open_failure_document(
        reading_request_paths(app_state, payload),
        payload,
        reveal=reveal,
    )


def resolve_decision(paths: ReadingPaths, relative_path: str) -> dict[str, Any]:
    decisions = load_latest_decisions(paths.decisions_path)
    decision = decisions.get(relative_path)
    if decision:
        return decision
    raise ValueError(f"Unknown relative_path: {relative_path}")


def resolve_failure_source(paths: ReadingPaths, payload: dict[str, Any]) -> Path:
    source_text = str(payload.get("source_path") or "").strip()
    relative_path = str(payload.get("relative_path") or "").strip()
    source_key = source_path_key(Path(source_text)) if source_text else ""
    relative_matches: list[Path] = []
    for row in build_failure_rows(paths):
        row_source_text = str(row.get("source_path") or "")
        row_source_path = Path(row_source_text)
        if source_text and (
            row_source_text == source_text or source_path_key(row_source_path) == source_key
        ):
            return row_source_path
        if relative_path and str(row.get("relative_path") or "") == relative_path:
            relative_matches.append(row_source_path)

    if len(relative_matches) == 1:
        return relative_matches[0]
    if len(relative_matches) > 1:
        raise ValueError(f"Ambiguous failed document path: {relative_path}")
    requested = source_text or relative_path
    raise ValueError(f"Unknown failed document: {requested}")


def open_path(path: Path) -> None:
    if os.name == "nt":
        shell_execute(str(path))
        return
    if sys.platform == "darwin":
        command = macos_open_command(path, reveal=False)
        if command is None:
            raise RuntimeError("macOS opener 'open' was not found.")
        launch_desktop_command(command)
        return
    if is_probably_headless():
        raise RuntimeError(
            "System default file opening is unavailable on this headless server. "
            f"Use this source path manually: {path}"
        )
    command = linux_open_command(path)
    if command is None:
        raise RuntimeError(
            "No supported Linux desktop opener was found. "
            "Install xdg-utils, gio, KDE open, or GNOME open."
        )
    launch_desktop_command(command)


def reveal_path(path: Path) -> None:
    if os.name == "nt":
        subprocess.Popen(
            ["explorer.exe", f"/select,{path}"],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return
    if sys.platform == "darwin":
        command = macos_open_command(path, reveal=True)
        if command is None:
            raise RuntimeError("macOS opener 'open' was not found.")
        launch_desktop_command(command)
        return
    open_path(path.parent)


def macos_open_command_available() -> bool:
    return find_macos_open() is not None


def macos_open_command(path: Path, *, reveal: bool) -> list[str] | None:
    opener = find_macos_open()
    if opener is None:
        return None
    if reveal:
        return [opener, "-R", str(path)]
    return [opener, str(path)]


def find_macos_open() -> str | None:
    return shutil.which("open") or ("/usr/bin/open" if Path("/usr/bin/open").exists() else None)


def linux_open_command_available() -> bool:
    return linux_open_command(Path(".")) is not None


def linux_open_command(path: Path) -> list[str] | None:
    opener = shutil.which("xdg-open")
    if opener:
        return [opener, str(path)]
    gio = shutil.which("gio")
    if gio:
        return [gio, "open", str(path)]
    for command_name in ("kde-open6", "kde-open5", "kde-open", "gnome-open"):
        opener = shutil.which(command_name)
        if opener:
            return [opener, str(path)]
    return None


def launch_desktop_command(command: list[str]) -> None:
    subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def shell_execute(path: str) -> None:
    import ctypes

    result = ctypes.windll.shell32.ShellExecuteW(  # type: ignore[attr-defined]
        None,
        "open",
        path,
        None,
        None,
        1,
    )
    if result <= 32:
        raise OSError(f"ShellExecute failed with code {result}: {path}")


def count_by(rows: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field_name) or "")
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def parse_int(value: str | None, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def parse_quality_score(value: Any, *, default: int = 0) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("Quality score must be an integer between 0 and 100.") from exc
    if not 0 <= parsed <= 100:
        raise ValueError("Quality score must be between 0 and 100.")
    return parsed


def parse_optional_int(value: str | None) -> int | None:
    if value in {None, ""}:
        return None
    return parse_int(value, 0)


_CLIENT_DISCONNECT_ERRORS = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)


class ReadingRequestHandler(BaseHTTPRequestHandler):
    state: AppState

    def handle(self) -> None:
        try:
            super().handle()
        except _CLIENT_DISCONNECT_ERRORS:
            return

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = self.parse_query(parsed.query)
        if parsed.path == "/":
            self.send_html(HTML_PAGE_BYTES)
            return
        if parsed.path in UI_STATIC_ASSETS:
            self.send_ui_asset(parsed.path)
            return
        if parsed.path == "/api/config":
            self.send_json(lambda: config_payload(self.state.paths))
            return
        upload_status_id = self.match_upload_route(parsed.path)
        if upload_status_id is not None:
            self.send_json(lambda: upload_workspace_payload(upload_status_id))
            return
        if parsed.path == "/api/analysis/status":
            self.send_json(
                lambda: analysis_status(
                    self.state,
                    paths_from_payload(query) or self.state.paths,
                )
            )
            return
        if parsed.path == "/api/relationships":
            self.send_json(
                lambda: build_relationship_payload(
                    self.state,
                    reading_paths_from_payload(self.state, query)
                    or require_paths(self.state),
                    query,
                )
            )
            return
        if parsed.path == "/api/rag":
            self.send_json(
                lambda: build_rag_payload(
                    self.state,
                    reading_paths_from_payload(self.state, query)
                    or require_paths(self.state),
                )
            )
            return
        if parsed.path == "/api/state":
            self.send_json(
                lambda: build_state_payload(
                    reading_paths_from_payload(self.state, query)
                    or require_paths(self.state),
                    query,
                )
            )
            return
        if parsed.path == "/api/integrations/anydocs/quality-stats":
            self.send_json(lambda: anydocs_bundle_quality_stats(self.state, query))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/uploads":
            self.send_json(lambda: create_upload_workspace(self.state))
            return
        upload_file_id = self.match_upload_route(parsed.path, suffix="/files")
        if upload_file_id is not None:
            query = self.parse_query(parsed.query)
            self.send_json(
                lambda: save_upload_file(
                    self.state,
                    upload_file_id,
                    query.get("relative_path") or "",
                    self.read_bytes(),
                )
            )
            return
        upload_complete_id = self.match_upload_route(parsed.path, suffix="/complete")
        if upload_complete_id is not None:
            self.send_json(lambda: complete_upload_workspace(self.state, upload_complete_id))
            return
        if self.path == "/api/pick-folder":
            self.send_json(pick_folder)
            return
        if self.path == "/api/paths":
            self.send_json(lambda: set_active_paths(self.state, self.read_json()))
            return
        if self.path == "/api/reading-output":
            self.send_json(lambda: set_reading_output(self.state, self.read_json()))
            return
        if self.path == "/api/graph-output":
            self.send_json(lambda: set_reading_output(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/start":
            self.send_json(lambda: start_analysis(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/stop":
            self.send_json(lambda: stop_analysis(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/early-relationships":
            self.send_json(lambda: start_early_relationships(self.state, self.read_json()))
            return
        if self.path == "/api/analysis/reset":
            self.send_json(lambda: reset_analysis_output(self.state, self.read_json()))
            return
        if self.path == "/api/test/llm":
            self.send_json(lambda: test_llm_connection(self.read_json()))
            return
        if self.path == "/api/test/vector-store":
            self.send_json(lambda: test_vector_store_connection(self.state, self.read_json()))
            return
        if self.path == "/api/relationships/mine":
            self.send_json(
                lambda: start_relationship_task(self.state, self.read_json(), "mine")
            )
            return
        if self.path == "/api/relationships/stop":
            self.send_json(lambda: stop_relationship_task(self.state, self.read_json()))
            return
        if self.path == "/api/relationships/reset":
            self.send_json(lambda: reset_relationship_output(self.state, self.read_json()))
            return
        if self.path == "/api/relationships/export-graph":
            self.send_json(
                lambda: start_relationship_task(
                    self.state, self.read_json(), "export_graph"
                )
            )
            return
        if self.path == "/api/relationships/export-bundle":
            self.send_json(
                lambda: start_relationship_task(
                    self.state, self.read_json(), "export_bundle"
                )
            )
            return
        if self.path == "/api/integrations/anydocs/open":
            self.send_json(lambda: open_anydocs_request(self.state, self.read_json()))
            return
        if self.path == "/api/integrations/anydocs/export-bundle":
            self.send_json(
                lambda: export_anydocs_bundle_request(self.state, self.read_json())
            )
            return
        if self.path == "/api/rag/build":
            self.send_json(lambda: start_rag_task(self.state, self.read_json()))
            return
        if self.path == "/api/rag/stop":
            self.send_json(lambda: stop_rag_task(self.state, self.read_json()))
            return
        if self.path == "/api/rag/search":
            self.send_json(lambda: search_rag_request(self.state, self.read_json()))
            return
        if self.path == "/api/mark":
            self.send_json(lambda: mark_document_request(self.state, self.read_json()))
            return
        if self.path == "/api/mark-batch":
            self.send_json(lambda: mark_documents_request(self.state, self.read_json()))
            return
        if self.path == "/api/open":
            self.send_json(lambda: open_document_request(self.state, self.read_json(), reveal=False))
            return
        if self.path == "/api/reveal":
            self.send_json(lambda: open_document_request(self.state, self.read_json(), reveal=True))
            return
        if self.path == "/api/open-failure":
            self.send_json(lambda: open_failure_document_request(self.state, self.read_json(), reveal=False))
            return
        if self.path == "/api/reveal-failure":
            self.send_json(lambda: open_failure_document_request(self.state, self.read_json(), reveal=True))
            return
        self.send_error(404)

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        upload_id = self.match_upload_route(parsed.path)
        if upload_id is not None:
            self.send_json(lambda: delete_upload_workspace(self.state, upload_id))
            return
        self.send_error(404)

    @staticmethod
    def parse_query(query: str) -> dict[str, str]:
        return {
            key: values[-1]
            for key, values in urllib.parse.parse_qs(query).items()
            if values
        }

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8", errors="ignore")
        payload = json.loads(body or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JSON body must be an object")
        return payload

    def read_bytes(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length)

    @staticmethod
    def match_upload_route(path: str, suffix: str = "") -> str | None:
        prefix = "/api/uploads/"
        if not path.startswith(prefix):
            return None
        remainder = path[len(prefix):]
        if suffix:
            if not remainder.endswith(suffix):
                return None
            upload_id = remainder[: -len(suffix)]
        else:
            if "/" in remainder:
                return None
            upload_id = remainder
        return validate_upload_id(upload_id)

    def send_html(self, html: str | bytes) -> None:
        encoded = html if isinstance(html, bytes) else html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_ui_asset(self, request_path: str) -> None:
        asset_name, content_type = UI_STATIC_ASSETS[request_path]
        encoded = UI_ASSET_BYTES[asset_name]
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_json(self, builder) -> None:
        try:
            payload = builder()
            status = 200
        except Exception as exc:
            payload = {"error": str(exc)}
            status = 400
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


class DocTriageHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


def build_handler(app_state: AppState):
    class BoundReadingRequestHandler(ReadingRequestHandler):
        pass

    BoundReadingRequestHandler.state = app_state
    return BoundReadingRequestHandler


def serve(paths: ReadingPaths | None, host: str, port: int, *, open_browser: bool) -> None:
    app_state = AppState(paths=paths)
    server = DocTriageHTTPServer((host, port), build_handler(app_state))
    url = f"http://{host}:{server.server_port}/"
    print(f"DocTriage Console: {url}")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-reading-ui",
        description="Open a local browser UI for DocTriage reading status.",
    )
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument("--no-open-browser", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_utf8_runtime()
    args = build_parser().parse_args(argv)
    paths = None
    if args.source_dir is not None or args.output_root is not None:
        if args.source_dir is None or args.output_root is None:
            raise SystemExit("--source-dir and --output-root must be provided together.")
        paths = ReadingPaths(
            source_dir=args.source_dir.expanduser().resolve(),
            output_root=args.output_root.expanduser().resolve(),
        )
    serve(paths, args.host, args.port, open_browser=not args.no_open_browser)


if __name__ == "__main__":
    main()
