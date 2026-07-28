from __future__ import annotations

import argparse
import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from datetime import datetime, timezone
from dataclasses import dataclass
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, as_completed, wait
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cleaner import DocumentWashError, DocumentWasher
from config import Settings, get_settings
from meta_profiler import DocumentProfile, MetadataProfiler
from ollama_runtime import prepare_scoring_model_for_analysis
from ranker_engine import LLMClient, ManifestAnalysis, ManifestResult, SemanticScore, SemanticScoring
from runtime_encoding import configure_utf8_runtime, decode_process_output

LOGGER = logging.getLogger("doctriage")
DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 18765


@dataclass(slots=True)
class PendingScoreContext:
    source_path: Path
    relative_path: Path
    manifest: ManifestResult
    fingerprint: dict[str, Any]
    settings_signature: str
    reprocess_reason: str
    previous_target_path: Path | None = None
    summary: str = ""
    retry_of_failed: bool = False


@dataclass(slots=True)
class PrepareDocumentContext:
    source_path: Path
    resolved_source_path: Path
    relative_path: Path
    manifest: ManifestResult
    fingerprint: dict[str, Any]
    settings_signature: str
    reprocess_reason: str
    previous_target_path: Path | None


@dataclass(slots=True)
class PreparedDocument:
    clean_markdown: str
    profile: DocumentProfile
    summary: str


@dataclass(slots=True)
class RunStats:
    discovered_directories: int = 0
    discovered_files: int = 0
    selected_files: int = 0
    skipped_existing: int = 0
    skipped_resumed: int = 0
    skipped_failed: int = 0
    skipped_too_large: int = 0
    reprocess_changed: int = 0
    reprocess_config_changed: int = 0
    submitted: int = 0
    succeeded: int = 0
    failed: int = 0
    failed_attempts: int = 0
    planned: int = 0
    retry_attempted: int = 0
    retry_succeeded: int = 0
    retry_still_failed: int = 0
    retry_skipped: int = 0

    def record_failure_attempt(self, *, retry: bool = False) -> None:
        self.failed_attempts += 1
        if retry:
            self.retry_still_failed += 1
            return
        self.failed += 1

    def record_retry_attempt(self) -> None:
        self.retry_attempted += 1

    def record_retry_success(self) -> None:
        self.retry_succeeded += 1
        if self.failed > 0:
            self.failed -= 1

    def record_retry_skipped(self) -> None:
        self.retry_skipped += 1

    @property
    def completed(self) -> int:
        return (
            self.skipped_existing
            + self.skipped_resumed
            + self.skipped_failed
            + self.succeeded
            + self.failed
            + self.planned
        )

    @property
    def throughput_completed(self) -> int:
        return self.succeeded + self.failed + self.planned

    def as_dict(self) -> dict[str, int]:
        return {
            "discovered_directories": self.discovered_directories,
            "discovered_files": self.discovered_files,
            "selected_files": self.selected_files,
            "completed": self.completed,
            "skipped_existing": self.skipped_existing,
            "skipped_resumed": self.skipped_resumed,
            "skipped_failed": self.skipped_failed,
            "skipped_too_large": self.skipped_too_large,
            "reprocess_changed": self.reprocess_changed,
            "reprocess_config_changed": self.reprocess_config_changed,
            "submitted": self.submitted,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "planned": self.planned,
            "failed_attempts": self.failed_attempts,
            "retry_attempted": self.retry_attempted,
            "retry_succeeded": self.retry_succeeded,
            "retry_still_failed": self.retry_still_failed,
            "retry_skipped": self.retry_skipped,
        }


class ResumeJournal:
    def __init__(self, processed_log_path: Path, failure_log_path: Path) -> None:
        self.processed_log_path = processed_log_path
        self.failure_log_path = failure_log_path
        self._processed_records: dict[str, dict[str, Any]] = {}
        self._failure_records: dict[str, dict[str, Any]] = {}
        self._load_processed_records()
        self._load_failure_records()

    def should_skip(
        self,
        source_path: Path,
        *,
        require_target_exists: bool,
        fingerprint: dict[str, Any],
        settings_signature: str,
        settings: Settings,
    ) -> tuple[bool, str]:
        if settings.FORCE_REPROCESS:
            return False, "force_reprocess"

        record = self._processed_records.get(str(source_path))
        if not record:
            return False, "no_record"

        if settings.CHANGE_DETECTION_ENABLED:
            record_fingerprint = record.get("fingerprint")
            if record_fingerprint != fingerprint:
                return False, "source_changed"

            record_signature = record.get("settings_signature")
            if record_signature not in build_compatible_settings_signatures(
                settings, settings_signature
            ):
                return False, "settings_changed"

        if not require_target_exists and record.get("status") in {"planned", "success"}:
            return True, "processed"

        target_path = record.get("target_path")
        if not target_path:
            return False, "missing_target_record"
        if Path(target_path).exists():
            return True, "target_exists"
        return False, "target_missing"

    def previous_target_path(self, source_path: Path) -> Path | None:
        record = self._processed_records.get(str(source_path))
        if not record:
            return None
        target_path = record.get("target_path")
        if not target_path:
            return None
        return Path(str(target_path))

    def record_processed(
        self,
        source_path: Path,
        target_path: Path,
        status: str,
        score: SemanticScore | None = None,
        fingerprint: dict[str, Any] | None = None,
        settings_signature: str | None = None,
    ) -> None:
        record = {
            "source_path": str(source_path),
            "target_path": str(target_path),
            "status": status,
            "quality": score.quality if score else None,
            "category": score.category if score else None,
            "fingerprint": fingerprint,
            "settings_signature": settings_signature,
        }
        self._processed_records[str(source_path)] = record
        self._append_jsonl(self.processed_log_path, record)

    def record_failure(
        self,
        source_path: Path,
        stage: str,
        error: str,
        fingerprint: dict[str, Any] | None = None,
        settings_signature: str | None = None,
    ) -> None:
        record = {
            "source_path": str(source_path),
            "stage": stage,
            "error": error,
            "fingerprint": fingerprint,
            "settings_signature": settings_signature,
        }
        self._failure_records[str(source_path)] = record
        self._append_jsonl(self.failure_log_path, record)

    def should_skip_failed(
        self,
        source_path: Path,
        *,
        fingerprint: dict[str, Any],
        settings_signature: str,
        settings: Settings,
    ) -> tuple[bool, str]:
        if settings.RETRY_FAILED or settings.FORCE_REPROCESS:
            return False, "retry_failed_enabled"

        record = self._failure_records.get(str(source_path))
        if not record:
            return False, "no_failure_record"

        if not settings.CHANGE_DETECTION_ENABLED:
            return True, "previous_failure"

        if record.get("fingerprint") == fingerprint and record.get(
            "settings_signature"
        ) in build_compatible_settings_signatures(settings, settings_signature):
            return True, "previous_failure"
        return False, "failure_stale"

    def has_unprocessed_failure(self, source_path: Path) -> bool:
        key = str(source_path)
        return key in self._failure_records and key not in self._processed_records

    @property
    def decision_log_path(self) -> Path:
        return self.processed_log_path.parent / "decisions.jsonl"

    @property
    def run_summary_path(self) -> Path:
        return self.processed_log_path.parent / "run_summary.json"

    def record_decision(
        self,
        source_path: Path,
        target_path: Path,
        status: str,
        score: SemanticScore,
        relative_path: Path,
        fingerprint: dict[str, Any],
        settings_signature: str,
        summary: str = "",
    ) -> None:
        record = {
            "source_path": str(source_path),
            "relative_path": relative_path.as_posix(),
            "target_path": str(target_path),
            "status": status,
            "quality": score.quality,
            "category": score.category,
            "document_kind": score.document_kind,
            "topic_tags": score.topic_tags,
            "knowledge_density": score.knowledge_density,
            "implementation_specificity": score.implementation_specificity,
            "logical_structure": score.logical_structure,
            "evidence_richness": score.evidence_richness,
            "actionability": score.actionability,
            "strategic_value": score.strategic_value,
            "freshness": score.freshness,
            "uniqueness": score.uniqueness,
            "sensitivity_risk": score.sensitivity_risk,
            "public_writing_suitability": score.public_writing_suitability,
            "reason": score.reason,
            "summary": summary,
            "fingerprint": fingerprint,
            "source_size_bytes": fingerprint.get("size_bytes"),
            "source_mtime_ns": fingerprint.get("mtime_ns"),
            "source_ctime_ns": fingerprint.get("ctime_ns"),
            "source_mtime": fingerprint_mtime_iso(fingerprint),
            "settings_signature": settings_signature,
        }
        self._append_jsonl(self.decision_log_path, record)

    def record_run_summary(self, stats: RunStats, settings: Settings | None = None) -> None:
        self.run_summary_path.parent.mkdir(parents=True, exist_ok=True)
        payload = stats.as_dict()
        if settings is not None:
            payload.update(
                {
                    "copy_files": settings.COPY_FILES,
                    "plan_only": not settings.COPY_FILES,
                }
            )
        payload.update(self.failure_summary(settings))
        with self.run_summary_path.open("w", encoding="utf-8", errors="ignore") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def failure_summary(self, settings: Settings | None = None) -> dict[str, int]:
        supported_extensions = (
            {suffix.lower() for suffix in settings.SUPPORTED_EXTENSIONS}
            if settings is not None
            else set()
        )
        failed_sources: set[str] = set()
        for source_path, record in self._failure_records.items():
            stage = str(record.get("stage") or "")
            if stage == "manifest_analysis":
                continue
            if supported_extensions and Path(source_path).suffix.lower() not in supported_extensions:
                continue
            failed_sources.add(source_path)

        processed_sources = set(self._processed_records)
        return {
            "failed_sources": len(failed_sources),
            "recovered_failed_sources": len(failed_sources & processed_sources),
            "unresolved_failures": len(failed_sources - processed_sources),
        }

    def _load_processed_records(self) -> None:
        if not self.processed_log_path.exists():
            return

        with self.processed_log_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                source_path = record.get("source_path")
                if source_path:
                    self._processed_records[source_path] = record

    def _load_failure_records(self) -> None:
        if not self.failure_log_path.exists():
            return

        with self.failure_log_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                source_path = record.get("source_path")
                if source_path:
                    self._failure_records[source_path] = record

    @staticmethod
    def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", errors="ignore") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


class ProgressReporter:
    MIN_COMPLETED_DELTA_FOR_EARLY_REPORT = 100

    def __init__(self, settings: Settings, stats: RunStats) -> None:
        self.settings = settings
        self.stats = stats
        self.started_at = time.monotonic()
        self._rate_started_at: float | None = None
        self._rate_stopped_at: float | None = None
        self._rate_started_throughput = 0
        self._rate_stopped_throughput: int | None = None
        self._last_report_at = 0.0
        self._last_reported_completed = 0

    def start_rate_window(self, now: float | None = None) -> None:
        if self._rate_started_at is not None:
            return

        self._rate_started_at = time.monotonic() if now is None else now
        self._rate_started_throughput = self.stats.throughput_completed

    def stop_rate_window(self, now: float | None = None) -> None:
        if self._rate_started_at is None or self._rate_stopped_at is not None:
            return

        self._rate_stopped_at = time.monotonic() if now is None else now
        self._rate_stopped_throughput = self.stats.throughput_completed

    def report(self, *, force: bool = False, now: float | None = None) -> None:
        if not self.settings.PROGRESS_ENABLED:
            return

        current = time.monotonic() if now is None else now
        snapshot = self.snapshot(current)
        if (
            not force
            and self._last_report_at
            and current - self._last_report_at < self.settings.PROGRESS_LOG_INTERVAL_SECONDS
            and not self._should_report_activity(snapshot)
        ):
            return

        self._last_report_at = current
        self._last_reported_completed = int(snapshot.get("completed") or 0)
        self._write_snapshot(snapshot)
        rate_text = (
            f"{snapshot['files_per_minute']:.2f} files/min"
            if snapshot["rate_window_active"]
            and int(snapshot.get("rate_window_completed") or 0) > 0
            else "not_calculated"
        )
        LOGGER.info(
            "Progress %s/%s (%.1f%%), rate=%s, ETA=%s, submitted=%s, failed=%s, skipped=%s",
            snapshot["completed"],
            snapshot["total"],
            snapshot["percent"],
            rate_text,
            snapshot["eta_human"],
            snapshot["submitted"],
            snapshot["failed"],
            snapshot["skipped_total"],
        )

    def _should_report_activity(self, snapshot: dict[str, Any]) -> bool:
        completed = int(snapshot.get("completed") or 0)
        if completed <= self._last_reported_completed:
            return False
        if self._last_reported_completed == 0:
            return True
        return (
            completed - self._last_reported_completed
            >= self.MIN_COMPLETED_DELTA_FOR_EARLY_REPORT
        )

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        current = now if now is not None else time.monotonic()
        elapsed_seconds = max(0.0, current - self.started_at)
        total = self.stats.selected_files or self.stats.discovered_files
        completed = min(self.stats.completed, total) if total else self.stats.completed
        remaining = max(0, total - completed)
        throughput_completed = self.stats.throughput_completed
        rate_window_started = self._rate_started_at is not None
        rate_window_active = (
            self._rate_started_at is not None and self._rate_stopped_at is None
        )
        if self._rate_started_at is None:
            rate_elapsed_seconds = None
            rate_window_completed = 0
        else:
            rate_ended_at = self._rate_stopped_at if self._rate_stopped_at is not None else current
            rate_elapsed_seconds = max(0.0, rate_ended_at - self._rate_started_at)
            rate_ended_throughput = (
                self._rate_stopped_throughput
                if self._rate_stopped_throughput is not None
                else throughput_completed
            )
            rate_window_completed = max(
                0, rate_ended_throughput - self._rate_started_throughput
            )
        rate_per_second = (
            rate_window_completed / rate_elapsed_seconds
            if rate_window_active and rate_elapsed_seconds and rate_window_completed > 0
            else 0.0
        )
        eta_seconds = remaining / rate_per_second if rate_per_second > 0 else None
        skipped_total = (
            self.stats.skipped_existing
            + self.stats.skipped_resumed
            + self.stats.skipped_failed
            + self.stats.skipped_too_large
        )

        return {
            **self.stats.as_dict(),
            "copy_files": self.settings.COPY_FILES,
            "plan_only": not self.settings.COPY_FILES,
            "total": total,
            "completed": completed,
            "remaining": remaining,
            "throughput_completed": throughput_completed,
            "rate_window_started": rate_window_started,
            "rate_window_active": rate_window_active,
            "rate_window_completed": rate_window_completed,
            "rate_elapsed_seconds": (
                round(rate_elapsed_seconds, 2)
                if rate_elapsed_seconds is not None
                else None
            ),
            "percent": round((completed / total * 100) if total else 0.0, 2),
            "elapsed_seconds": round(elapsed_seconds, 2),
            "eta_seconds": round(eta_seconds, 2) if eta_seconds is not None else None,
            "eta_human": format_duration(eta_seconds),
            "files_per_minute": round(rate_per_second * 60, 2),
            "skipped_total": skipped_total,
        }

    def _write_snapshot(self, snapshot: dict[str, Any]) -> None:
        self.settings.progress_path.parent.mkdir(parents=True, exist_ok=True)
        with self.settings.progress_path.open("w", encoding="utf-8", errors="ignore") as handle:
            json.dump(snapshot, handle, ensure_ascii=False, indent=2)


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown"

    remaining = max(0, int(seconds))
    hours, remainder = divmod(remaining, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}m"
    if minutes:
        return f"{minutes}m{secs:02d}s"
    return f"{secs}s"


def configure_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    handlers: list[logging.Handler] = [
        logging.FileHandler(settings.application_log_path, encoding="utf-8"),
    ]
    if not any(
        stream_points_to_path(stream, settings.application_log_path)
        for stream in (sys.stdout, sys.stderr)
    ):
        handlers.insert(0, logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=handlers,
        force=True,
    )


def stream_points_to_path(stream: Any, path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        stream_stat = os.fstat(stream.fileno())
        path_stat = path.stat()
    except (OSError, AttributeError, ValueError):
        return False
    return (
        stream_stat.st_ino == path_stat.st_ino
        and stream_stat.st_dev == path_stat.st_dev
    )


def scan_candidate_files(settings: Settings) -> tuple[dict[Path, list[Path]], int, int]:
    extension_set = {suffix.lower() for suffix in settings.SUPPORTED_EXTENSIONS}
    directories: dict[Path, list[Path]] = {}
    skipped_too_large = 0
    stat_failures = 0
    max_file_size_bytes = (
        int(settings.MAX_FILE_SIZE_MB * 1024 * 1024)
        if settings.MAX_FILE_SIZE_MB is not None
        else None
    )

    seen_paths: set[Path] = set()
    for source_root in analysis_source_roots(settings):
        for root, _, file_names in os.walk(source_root):
            root_path = Path(root)
            candidates = directories.setdefault(root_path, [])
            modified_times: dict[Path, float] = {}
            for existing in candidates:
                try:
                    modified_times[existing] = existing.stat().st_mtime
                except OSError:
                    modified_times[existing] = 0.0
            for file_name in file_names:
                path = root_path / file_name
                if path.suffix.lower() not in extension_set:
                    continue
                try:
                    resolved_path = path.resolve()
                except OSError:
                    resolved_path = path.absolute()
                if resolved_path in seen_paths:
                    continue
                seen_paths.add(resolved_path)

                try:
                    stat = path.stat()
                except OSError as exc:
                    LOGGER.warning("Skipping unreadable candidate during scan: %s: %s", path, exc)
                    stat_failures += 1
                    continue

                if max_file_size_bytes is not None and stat.st_size > max_file_size_bytes:
                    LOGGER.info("Skipping over-size file: %s", path)
                    skipped_too_large += 1
                    continue
                modified_times[path] = stat.st_mtime
                candidates.append(path)
            if not candidates:
                directories.pop(root_path, None)
                continue

            candidates.sort(key=lambda path: (modified_times[path], path.name.lower()))

    return directories, skipped_too_large, stat_failures


def analysis_source_roots(settings: Settings) -> tuple[Path, ...]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for candidate in (settings.SOURCE_DIR, *settings.ADDITIONAL_SOURCE_DIRS):
        resolved = candidate.expanduser().resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        roots.append(resolved)
    return tuple(roots)


def source_root_for_path(settings: Settings, source_path: Path) -> tuple[Path, int]:
    resolved_path = source_path.expanduser().resolve()
    matches: list[tuple[int, Path, int]] = []
    for index, root in enumerate(analysis_source_roots(settings)):
        if _is_relative_to(resolved_path, root):
            matches.append((len(root.parts), root, index))
    if not matches:
        raise ValueError(f"Source path is outside configured source directories: {source_path}")
    _, root, index = max(matches, key=lambda item: (item[0], -item[2]))
    return root, index


def source_relative_path(settings: Settings, source_path: Path) -> Path:
    root, index = source_root_for_path(settings, source_path)
    relative = source_path.expanduser().resolve().relative_to(root)
    if index == 0:
        return relative
    additional_count = len(analysis_source_roots(settings)) - 1
    prefix = Path("_uploads")
    if additional_count > 1:
        prefix /= f"source_{index}"
    return prefix / relative


def apply_file_limit(
    directory_map: dict[Path, list[Path]], max_files: int | None
) -> dict[Path, list[Path]]:
    if max_files is None:
        return directory_map

    selected: dict[Path, list[Path]] = {}
    remaining = max_files

    for directory in sorted(directory_map):
        if remaining <= 0:
            break

        files = directory_map[directory][:remaining]
        if files:
            selected[directory] = files
            remaining -= len(files)

    return selected


def prioritize_failed_files(
    directory_map: dict[Path, list[Path]], journal: ResumeJournal
) -> dict[Path, list[Path]]:
    def has_unprocessed_failure(path: Path) -> bool:
        return journal.has_unprocessed_failure(path.resolve())

    prioritized: dict[Path, list[Path]] = {}
    directory_items = sorted(
        directory_map.items(),
        key=lambda item: (
            0 if any(has_unprocessed_failure(path) for path in item[1]) else 1,
            str(item[0]).lower(),
        ),
    )
    for directory, files in directory_items:
        failed_files = [path for path in files if has_unprocessed_failure(path)]
        other_files = [path for path in files if not has_unprocessed_failure(path)]
        prioritized[directory] = failed_files + other_files
    return prioritized


def collect_retry_failed_path(
    retry_failed_paths: list[Path] | None, source_path: Path
) -> None:
    if retry_failed_paths is not None:
        retry_failed_paths.append(source_path.resolve())


def prepare_document_for_scoring(
    source_path: Path, settings: Settings
) -> PreparedDocument:
    washer = DocumentWasher(settings=settings)
    profiler = MetadataProfiler(settings=settings)
    washed = washer.wash(source_path)
    profile = profiler.profile_document(source_path, washed.clean_markdown)
    summary = (
        build_local_summary(
            washed.clean_markdown,
            max_chars=settings.DOCUMENT_SUMMARY_MAX_CHARS,
        )
        if settings.DOCUMENT_SUMMARY_ENABLED
        else ""
    )
    return PreparedDocument(
        clean_markdown=washed.clean_markdown,
        profile=profile,
        summary=summary,
    )


def handle_prepare_failure(
    *,
    context: PrepareDocumentContext,
    exc: BaseException,
    journal: ResumeJournal,
    stats: RunStats,
    progress: ProgressReporter,
    retry_failed_paths: list[Path] | None,
) -> None:
    if isinstance(exc, DocumentWashError):
        LOGGER.warning("Document washing failed for %s: %s", context.source_path, exc)
        stage = "wash"
    elif isinstance(exc, OSError):
        LOGGER.warning("File access failed for %s: %s", context.source_path, exc)
        stage = "read"
    else:
        LOGGER.exception("Unexpected preparation failure for %s", context.source_path)
        stage = "prepare"

    stats.record_failure_attempt()
    journal.record_failure(
        context.resolved_source_path,
        stage,
        str(exc),
        fingerprint=context.fingerprint,
        settings_signature=context.settings_signature,
    )
    collect_retry_failed_path(retry_failed_paths, context.source_path)
    progress.report()


def find_existing_target(settings: Settings, relative_path: Path) -> Path | None:
    all_candidate_paths = [
        settings.archive_dir / relative_path,
        *(
            settings.category_dir(category) / relative_path
            for category in settings.CATEGORY_MAP
        ),
    ]

    for candidate in all_candidate_paths:
        if candidate.exists():
            return candidate
    return None


def resolve_target_path(
    settings: Settings,
    relative_path: Path,
    score: SemanticScore,
    manifest: ManifestResult,
) -> Path:
    final_category = score.category

    if manifest.is_series_candidate(relative_path.name):
        final_category = "Series"

    if score.quality >= settings.QUALITY_THRESHOLD:
        if final_category not in settings.CATEGORY_MAP:
            final_category = "Implementation"
        return settings.category_dir(final_category) / relative_path

    return settings.archive_dir / relative_path


def build_local_summary(clean_markdown: str, max_chars: int) -> str:
    if max_chars <= 0:
        return ""

    normalized = normalize_summary_text(clean_markdown)
    if len(normalized) <= max_chars:
        return normalized

    return normalized[:max_chars].rstrip() + "..."


def normalize_summary_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<!--\s*page\s+\d+\s*-->", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", " ", text)
    text = re.sub(r"[\ue000-\uf8ff]", " ", text)
    text = re.sub(r"(?i)\bpowered by\b.*?(?=\s|$)", " ", text)
    text = re.sub(
        r"(创作中心|朗读文章|通义语音合成|字号|笔记|分享|浏览|发表|更新|阅读全文|阅读助手)",
        " ",
        text,
    )
    lines = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip(" #*-•·\t")
        if not line:
            continue
        if len(line) <= 2:
            continue
        if re.fullmatch(r"(目录|文章|专题|视频&活动|New)", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\d+(?:\.\d+){0,4}", line):
            continue
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def summary_for_decision(
    score: SemanticScore, fallback_summary: str, max_chars: int
) -> str:
    if max_chars <= 0:
        return ""
    summary = normalize_summary_text(score.summary)
    selected = summary or fallback_summary
    if len(selected) <= max_chars:
        return selected
    return selected[:max_chars].rstrip() + "..."


def build_file_fingerprint(path: Path, settings: Settings) -> dict[str, Any]:
    stat = path.stat()
    fingerprint: dict[str, Any] = {
        "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "ctime_ns": stat.st_ctime_ns,
    }
    if settings.CHANGE_DETECTION_USE_CONTENT_HASH:
        fingerprint["content_sha256"] = compute_file_sha256(path)
    return fingerprint


def fingerprint_mtime_iso(fingerprint: dict[str, Any]) -> str:
    try:
        mtime_ns = int(fingerprint.get("mtime_ns"))
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(mtime_ns / 1_000_000_000, timezone.utc).isoformat()


def compute_file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_settings_signature(settings: Settings) -> str:
    signature_payload = build_settings_signature_payload(settings)
    serialized = json.dumps(signature_payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_compatible_settings_signatures(
    settings: Settings, current_signature: str
) -> set[str]:
    signatures = {current_signature}
    base_payload = build_settings_signature_payload(settings)

    legacy_summary_payload = dict(base_payload)
    legacy_summary_payload["document_summary_max_chars"] = 240
    signatures.add(settings_signature_from_payload(legacy_summary_payload))

    without_output_language = dict(base_payload)
    without_output_language.pop("output_language", None)
    signatures.add(settings_signature_from_payload(without_output_language))

    legacy_without_output_language = dict(without_output_language)
    legacy_without_output_language["document_summary_max_chars"] = 240
    signatures.add(settings_signature_from_payload(legacy_without_output_language))
    return signatures


def build_settings_signature_payload(settings: Settings) -> dict[str, Any]:
    return {
        "pipeline_version": settings.PIPELINE_VERSION,
        "llm_endpoint": settings.LLM_ENDPOINT,
        "llm_model": settings.LLM_MODEL,
        "llm_num_ctx": settings.LLM_NUM_CTX,
        "quality_threshold": settings.QUALITY_THRESHOLD,
        "ocr_enabled": settings.OCR_ENABLED,
        "pdf_text_fallback_enabled": settings.PDF_TEXT_FALLBACK_ENABLED,
        "pdf_text_fallback_max_pages": settings.PDF_TEXT_FALLBACK_MAX_PAGES,
        "pdf_metadata_enabled": settings.PDF_METADSample_ENABLED,
        "document_summary_enabled": settings.DOCUMENT_SUMMARY_ENABLED,
        "document_summary_max_chars": settings.DOCUMENT_SUMMARY_MAX_CHARS,
        "output_language": settings.OUTPUT_LANGUAGE,
        "skip_manifest_analysis": settings.SKIP_MANIFEST_ANALYSIS,
        "category_map": settings.CATEGORY_MAP,
        "noise_patterns": settings.NOISE_PATTERNS,
        "supported_extensions": settings.SUPPORTED_EXTENSIONS,
    }


def settings_signature_from_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_safe_paths(settings: Settings) -> None:
    output_root = settings.OUTPUT_ROOT.resolve()
    for source_dir in analysis_source_roots(settings):
        if source_dir == output_root:
            raise ValueError("OUTPUT_ROOT must be different from every SOURCE_DIR")
        if _is_relative_to(output_root, source_dir):
            raise ValueError(
                "OUTPUT_ROOT must not be inside a SOURCE_DIR; this would mix generated files into the source scan."
            )

def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


class OutputRunLock:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.lock_path = settings.state_dir / "run.lock"
        self.token = uuid.uuid4().hex
        self.acquired = False

    def __enter__(self) -> OutputRunLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()

    def acquire(self) -> None:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(
                    str(self.lock_path),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError:
                info = read_run_lock(self.lock_path)
                pid = coerce_pid(info.get("pid"))
                if pid and is_process_alive(pid):
                    raise RuntimeError(
                        "Another DocTriage run is already using this OUTPUT_ROOT: "
                        f"pid={pid}, lock={self.lock_path}"
                    )
                try:
                    self.lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue

            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "schema_version": "doctriage_run_lock.v1",
                        "pid": os.getpid(),
                        "token": self.token,
                        "source_dir": str(self.settings.SOURCE_DIR),
                        "source_dirs": [
                            str(path) for path in analysis_source_roots(self.settings)
                        ],
                        "output_root": str(self.settings.OUTPUT_ROOT),
                        "created_epoch": time.time(),
                    },
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
            self.acquired = True
            return
        raise RuntimeError(f"Could not acquire run lock: {self.lock_path}")

    def release(self) -> None:
        if not self.acquired:
            return
        info = read_run_lock(self.lock_path)
        if info.get("token") != self.token:
            LOGGER.warning("Not releasing run lock owned by another process: %s", self.lock_path)
            return
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            LOGGER.warning("Failed to release run lock %s: %s", self.lock_path, exc)
        finally:
            self.acquired = False


def read_run_lock(path: Path) -> dict[str, Any]:
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


def run_pipeline(settings: Settings | None = None) -> None:
    current_settings = settings or get_settings()
    validate_safe_paths(current_settings)

    for source_dir in analysis_source_roots(current_settings):
        if not source_dir.exists():
            raise FileNotFoundError(f"Source directory does not exist: {source_dir}")
        if not source_dir.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    current_settings.OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    current_settings.state_dir.mkdir(parents=True, exist_ok=True)
    with OutputRunLock(current_settings):
        configure_logging(current_settings)
        _run_pipeline_locked(current_settings)


def _run_pipeline_locked(current_settings: Settings) -> None:
    prepare_scoring_model_for_analysis(current_settings)
    journal = ResumeJournal(
        processed_log_path=current_settings.processed_log_path,
        failure_log_path=current_settings.failure_log_path,
    )
    stats = RunStats()
    settings_signature = build_settings_signature(current_settings)

    washer = DocumentWasher(settings=current_settings)
    profiler = MetadataProfiler(settings=current_settings)
    with LLMClient(settings=current_settings) as llm_client:
        manifest_analysis = ManifestAnalysis(llm_client=llm_client)
        semantic_scoring = SemanticScoring(llm_client=llm_client)

        _run_pipeline_with_llm(
            current_settings=current_settings,
            journal=journal,
            stats=stats,
            settings_signature=settings_signature,
            washer=washer,
            profiler=profiler,
            manifest_analysis=manifest_analysis,
            semantic_scoring=semantic_scoring,
        )


def _run_pipeline_with_llm(
    *,
    current_settings: Settings,
    journal: ResumeJournal,
    stats: RunStats,
    settings_signature: str,
    washer: DocumentWasher,
    profiler: MetadataProfiler,
    manifest_analysis: ManifestAnalysis,
    semantic_scoring: SemanticScoring,
) -> None:

    full_directory_map, skipped_too_large, scan_stat_failures = scan_candidate_files(
        current_settings
    )
    stats.skipped_too_large = skipped_too_large
    stats.failed = scan_stat_failures
    stats.failed_attempts = scan_stat_failures
    if not full_directory_map:
        LOGGER.info(
            "No candidate documents found in %s",
            ", ".join(str(path) for path in analysis_source_roots(current_settings)),
        )
        journal.record_run_summary(stats, current_settings)
        ProgressReporter(current_settings, stats).report(force=True)
        return

    prioritized_directory_map = (
        prioritize_failed_files(full_directory_map, journal)
        if current_settings.RETRY_FAILED
        else full_directory_map
    )
    directory_map = apply_file_limit(prioritized_directory_map, current_settings.MAX_FILES)
    stats.discovered_directories = len(full_directory_map)
    stats.discovered_files = sum(len(files) for files in full_directory_map.values())
    planned_file_count = sum(len(files) for files in directory_map.values())
    stats.selected_files = planned_file_count
    progress = ProgressReporter(current_settings, stats)
    LOGGER.info("Discovered %s directories for analysis", stats.discovered_directories)
    LOGGER.info("Discovered %s candidate files", stats.discovered_files)
    LOGGER.info("Selected %s candidate files for this run", planned_file_count)
    progress.report(force=True)
    retry_failed_paths: list[Path] | None = [] if current_settings.RETRY_FAILED else None

    manifests: dict[Path, ManifestResult] = {}
    with ThreadPoolExecutor(
        max_workers=current_settings.CONCURRENCY_LIMIT,
        thread_name_prefix="doctriage-llm",
    ) as score_executor, ThreadPoolExecutor(
        max_workers=current_settings.CONCURRENCY_LIMIT,
        thread_name_prefix="doctriage-prepare",
    ) as prepare_executor:
        if current_settings.SKIP_MANIFEST_ANALYSIS:
            LOGGER.info("Skipping manifest analysis by configuration")
            manifests = {directory: ManifestResult() for directory in directory_map}
        else:
            manifest_futures = {
                score_executor.submit(
                    manifest_analysis.analyze_directory,
                    directory,
                    files,
                    source_root_for_path(current_settings, directory)[0],
                ): directory
                for directory, files in directory_map.items()
            }

            for future in as_completed(manifest_futures):
                directory = manifest_futures[future]
                try:
                    manifests[directory] = future.result()
                except Exception as exc:
                    LOGGER.warning(
                        "Manifest analysis failed for %s: %s", directory, exc, exc_info=True
                    )
                    journal.record_failure(directory, "manifest_analysis", str(exc))
                    manifests[directory] = ManifestResult()

        pending_scores: dict[Future[SemanticScore], PendingScoreContext] = {}
        pending_prepares: dict[Future[PreparedDocument], PrepareDocumentContext] = {}
        max_pending_scores = max(1, current_settings.CONCURRENCY_LIMIT * 2)
        max_pending_prepares = max(1, current_settings.CONCURRENCY_LIMIT * 2)
        selected_for_processing = 0

        def drain_prepared_documents(*, block: bool) -> None:
            if not pending_prepares:
                return

            done, _ = wait(
                pending_prepares.keys(),
                timeout=None if block else 0.0,
                return_when=FIRST_COMPLETED,
            )
            if not done and block:
                return

            for future in done:
                context = pending_prepares.pop(future)
                try:
                    prepared = future.result()
                except Exception as exc:
                    handle_prepare_failure(
                        context=context,
                        exc=exc,
                        journal=journal,
                        stats=stats,
                        progress=progress,
                        retry_failed_paths=retry_failed_paths,
                    )
                    continue

                score_future = score_executor.submit(
                    semantic_scoring.score_document,
                    context.source_path,
                    prepared.clean_markdown,
                    prepared.profile,
                    context.manifest,
                )
                pending_scores[score_future] = PendingScoreContext(
                    source_path=context.resolved_source_path,
                    relative_path=context.relative_path,
                    manifest=context.manifest,
                    fingerprint=context.fingerprint,
                    settings_signature=context.settings_signature,
                    reprocess_reason=context.reprocess_reason,
                    previous_target_path=context.previous_target_path,
                    summary=prepared.summary,
                )
                stats.submitted += 1

                if len(pending_scores) >= max_pending_scores:
                    _drain_completed_scores(
                        pending_scores=pending_scores,
                        journal=journal,
                        settings=current_settings,
                        stats=stats,
                        progress=progress,
                        retry_failed_paths=retry_failed_paths,
                        block=True,
                    )

        for directory, files in directory_map.items():
            manifest = manifests.get(directory, ManifestResult())

            for source_path in files:
                relative_path = source_relative_path(current_settings, source_path)
                resolved_source_path = source_path.resolve()
                retrying_prior_failure = (
                    current_settings.RETRY_FAILED
                    and journal.has_unprocessed_failure(resolved_source_path)
                )
                try:
                    fingerprint = build_file_fingerprint(source_path, current_settings)
                except OSError as exc:
                    LOGGER.warning("File stat failed for %s: %s", source_path, exc)
                    stats.record_failure_attempt()
                    journal.record_failure(
                        source_path.resolve(),
                        "stat",
                        str(exc),
                        settings_signature=settings_signature,
                    )
                    collect_retry_failed_path(retry_failed_paths, source_path)
                    progress.report()
                    continue
                existing_target = find_existing_target(current_settings, relative_path)

                if (
                    existing_target is not None
                    and not current_settings.FORCE_REPROCESS
                    and not current_settings.CHANGE_DETECTION_ENABLED
                ):
                    LOGGER.info("Skipping existing target: %s", source_path)
                    stats.skipped_existing += 1
                    journal.record_processed(
                        source_path=resolved_source_path,
                        target_path=existing_target.resolve(),
                        status="skipped_existing_target",
                        fingerprint=fingerprint,
                        settings_signature=settings_signature,
                    )
                    progress.report()
                    continue

                should_skip, skip_reason = journal.should_skip(
                    resolved_source_path,
                    require_target_exists=current_settings.COPY_FILES,
                    fingerprint=fingerprint,
                    settings_signature=settings_signature,
                    settings=current_settings,
                )
                if should_skip:
                    LOGGER.info(
                        "Skipping resumed item already materialized: %s [%s]",
                        source_path,
                        skip_reason,
                    )
                    stats.skipped_resumed += 1
                    progress.report()
                    continue

                if skip_reason == "source_changed":
                    stats.reprocess_changed += 1
                    LOGGER.info("Reprocessing changed source: %s", source_path)
                elif skip_reason == "settings_changed":
                    stats.reprocess_config_changed += 1
                    LOGGER.info("Reprocessing due to settings signature change: %s", source_path)

                should_skip_failure, failure_reason = journal.should_skip_failed(
                    resolved_source_path,
                    fingerprint=fingerprint,
                    settings_signature=settings_signature,
                    settings=current_settings,
                )
                if should_skip_failure:
                    LOGGER.info(
                        "Skipping previous failure: %s [%s]",
                        source_path,
                        failure_reason,
                    )
                    stats.skipped_failed += 1
                    progress.report()
                    continue

                if not retrying_prior_failure:
                    progress.start_rate_window()

                prepare_future = prepare_executor.submit(
                    prepare_document_for_scoring,
                    source_path,
                    current_settings,
                )
                pending_prepares[prepare_future] = PrepareDocumentContext(
                    source_path=source_path,
                    resolved_source_path=resolved_source_path,
                    relative_path=relative_path,
                    manifest=manifest,
                    fingerprint=fingerprint,
                    settings_signature=settings_signature,
                    reprocess_reason=skip_reason,
                    previous_target_path=journal.previous_target_path(resolved_source_path),
                )
                selected_for_processing += 1
                if len(pending_prepares) >= max_pending_prepares:
                    drain_prepared_documents(block=True)

                if len(pending_scores) >= max_pending_scores:
                    _drain_completed_scores(
                        pending_scores=pending_scores,
                        journal=journal,
                        settings=current_settings,
                        stats=stats,
                        progress=progress,
                        retry_failed_paths=retry_failed_paths,
                        block=True,
                    )

                if current_settings.MAX_FILES and selected_for_processing >= current_settings.MAX_FILES:
                    LOGGER.info("Reached MAX_FILES=%s; draining submitted work", current_settings.MAX_FILES)
                    break

            if current_settings.MAX_FILES and selected_for_processing >= current_settings.MAX_FILES:
                break

        while pending_prepares:
            drain_prepared_documents(block=True)

        while pending_scores:
            _drain_completed_scores(
                pending_scores=pending_scores,
                journal=journal,
                settings=current_settings,
                stats=stats,
                progress=progress,
                retry_failed_paths=retry_failed_paths,
                block=True,
            )
        progress.stop_rate_window()
        if retry_failed_paths:
            _retry_failed_documents_once(
                retry_failed_paths=retry_failed_paths,
                executor=score_executor,
                journal=journal,
                settings=current_settings,
                settings_signature=settings_signature,
                manifests=manifests,
                washer=washer,
                profiler=profiler,
                semantic_scoring=semantic_scoring,
                stats=stats,
                progress=progress,
            )
    journal.record_run_summary(stats, current_settings)
    progress.report(force=True)
    LOGGER.info("Run summary: %s", stats.as_dict())

    if current_settings.RELATIONSHIP_MINING_ENABLED:
        from relationship_miner import mine_relationships

        LOGGER.info("Starting relationship mining")
        mine_relationships(current_settings)
        LOGGER.info("Relationship mining completed")


def _retry_failed_documents_once(
    *,
    retry_failed_paths: list[Path],
    executor: ThreadPoolExecutor,
    journal: ResumeJournal,
    settings: Settings,
    settings_signature: str,
    manifests: dict[Path, ManifestResult],
    washer: DocumentWasher,
    profiler: MetadataProfiler,
    semantic_scoring: SemanticScoring,
    stats: RunStats,
    progress: ProgressReporter,
) -> None:
    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in retry_failed_paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(resolved)

    if not unique_paths:
        return

    LOGGER.info("Retrying %s failed documents once at end of run", len(unique_paths))
    pending_scores: dict[Future[SemanticScore], PendingScoreContext] = {}
    max_pending_scores = max(1, settings.CONCURRENCY_LIMIT * 2)

    for source_path in unique_paths:
        try:
            relative_path = source_relative_path(settings, source_path)
            fingerprint = build_file_fingerprint(source_path, settings)
        except OSError as exc:
            LOGGER.warning("Retry stat failed for %s: %s", source_path, exc)
            stats.record_retry_attempt()
            stats.record_failure_attempt(retry=True)
            journal.record_failure(
                source_path,
                "retry_stat",
                str(exc),
                settings_signature=settings_signature,
            )
            progress.report()
            continue
        except ValueError:
            LOGGER.warning("Retry path is outside configured source directories: %s", source_path)
            stats.record_retry_skipped()
            continue

        should_skip, skip_reason = journal.should_skip(
            source_path,
            require_target_exists=settings.COPY_FILES,
            fingerprint=fingerprint,
            settings_signature=settings_signature,
            settings=settings,
        )
        if should_skip:
            LOGGER.info("Skipping failed retry already materialized: %s [%s]", source_path, skip_reason)
            stats.record_retry_skipped()
            continue

        if skip_reason in {"source_changed", "settings_changed"}:
            reprocess_reason = skip_reason
        else:
            reprocess_reason = "retry_failed_once"

        stats.record_retry_attempt()
        try:
            washed = washer.wash(source_path)
            profile = profiler.profile_document(source_path, washed.clean_markdown)
            summary = (
                build_local_summary(
                    washed.clean_markdown,
                    max_chars=settings.DOCUMENT_SUMMARY_MAX_CHARS,
                )
                if settings.DOCUMENT_SUMMARY_ENABLED
                else ""
            )
        except DocumentWashError as exc:
            LOGGER.warning("Retry document washing failed for %s: %s", source_path, exc)
            stats.record_failure_attempt(retry=True)
            journal.record_failure(
                source_path,
                "retry_wash",
                str(exc),
                fingerprint=fingerprint,
                settings_signature=settings_signature,
            )
            progress.report()
            continue
        except OSError as exc:
            LOGGER.warning("Retry file access failed for %s: %s", source_path, exc)
            stats.record_failure_attempt(retry=True)
            journal.record_failure(
                source_path,
                "retry_read",
                str(exc),
                fingerprint=fingerprint,
                settings_signature=settings_signature,
            )
            progress.report()
            continue
        except Exception as exc:
            LOGGER.exception("Unexpected retry preparation failure for %s", source_path)
            stats.record_failure_attempt(retry=True)
            journal.record_failure(
                source_path,
                "retry_prepare",
                str(exc),
                fingerprint=fingerprint,
                settings_signature=settings_signature,
            )
            progress.report()
            continue

        manifest = manifests.get(source_path.parent, ManifestResult())
        future = executor.submit(
            semantic_scoring.score_document,
            source_path,
            washed.clean_markdown,
            profile,
            manifest,
        )
        pending_scores[future] = PendingScoreContext(
            source_path=source_path,
            relative_path=relative_path,
            manifest=manifest,
            fingerprint=fingerprint,
            settings_signature=settings_signature,
            reprocess_reason=reprocess_reason,
            previous_target_path=journal.previous_target_path(source_path),
            summary=summary,
            retry_of_failed=True,
        )
        stats.submitted += 1

        if len(pending_scores) >= max_pending_scores:
            _drain_completed_scores(
                pending_scores=pending_scores,
                journal=journal,
                settings=settings,
                stats=stats,
                progress=progress,
                block=True,
            )

    while pending_scores:
        _drain_completed_scores(
            pending_scores=pending_scores,
            journal=journal,
            settings=settings,
            stats=stats,
            progress=progress,
            block=True,
        )


def _drain_completed_scores(
    pending_scores: dict[Future[SemanticScore], PendingScoreContext],
    journal: ResumeJournal,
    settings: Settings,
    stats: RunStats,
    progress: ProgressReporter,
    block: bool,
    retry_failed_paths: list[Path] | None = None,
) -> None:
    if not pending_scores:
        return

    done, _ = wait(
        pending_scores.keys(),
        timeout=None if block else 0.0,
        return_when=FIRST_COMPLETED,
    )

    if not done and block:
        return

    for future in done:
        context = pending_scores.pop(future)
        try:
            score = future.result()
            target_path = resolve_target_path(
                settings=settings,
                relative_path=context.relative_path,
                score=score,
                manifest=context.manifest,
            )
            summary = (
                summary_for_decision(
                    score,
                    context.summary,
                    settings.DOCUMENT_SUMMARY_MAX_CHARS,
                )
                if settings.DOCUMENT_SUMMARY_ENABLED
                else ""
            )

            if not settings.COPY_FILES:
                resolved_target_path = target_path.resolve()
                journal.record_decision(
                    source_path=context.source_path,
                    target_path=resolved_target_path,
                    status="planned",
                    score=score,
                    relative_path=context.relative_path,
                    fingerprint=context.fingerprint,
                    settings_signature=context.settings_signature,
                    summary=summary,
                )
                journal.record_processed(
                    source_path=context.source_path,
                    target_path=resolved_target_path,
                    status="planned",
                    score=score,
                    fingerprint=context.fingerprint,
                    settings_signature=context.settings_signature,
                )
                stats.planned += 1
                if context.retry_of_failed:
                    stats.record_retry_success()
                LOGGER.info(
                    "Planned %s [quality=%s category=%s]",
                    context.source_path,
                    score.quality,
                    score.category,
                )
                progress.report()
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path.exists():
                if should_overwrite_existing_target(context.reprocess_reason, settings):
                    shutil.copy2(context.source_path, target_path)
                    resolved_target_path = target_path.resolve()
                    cleanup_stale_target(context.previous_target_path, resolved_target_path)
                    stats.succeeded += 1
                    if context.retry_of_failed:
                        stats.record_retry_success()
                    status = "success_overwritten_changed_target"
                    journal.record_decision(
                        source_path=context.source_path,
                        target_path=resolved_target_path,
                        status=status,
                        score=score,
                        relative_path=context.relative_path,
                        fingerprint=context.fingerprint,
                        settings_signature=context.settings_signature,
                        summary=summary,
                    )
                    journal.record_processed(
                        source_path=context.source_path,
                        target_path=resolved_target_path,
                        status=status,
                        score=score,
                        fingerprint=context.fingerprint,
                        settings_signature=context.settings_signature,
                    )
                    LOGGER.info(
                        "Updated existing target after reprocess: %s -> %s [%s]",
                        context.source_path.name,
                        target_path,
                        context.reprocess_reason,
                    )
                    progress.report()
                    continue

                LOGGER.info("Skipping copy because target already exists: %s", target_path)
                stats.skipped_existing += 1
                if context.retry_of_failed:
                    stats.record_retry_success()
                resolved_target_path = target_path.resolve()
                status = "skipped_existing_target"
                journal.record_decision(
                    source_path=context.source_path,
                    target_path=resolved_target_path,
                    status=status,
                    score=score,
                    relative_path=context.relative_path,
                    fingerprint=context.fingerprint,
                    settings_signature=context.settings_signature,
                    summary=summary,
                )
                journal.record_processed(
                    source_path=context.source_path,
                    target_path=resolved_target_path,
                    status=status,
                    score=score,
                    fingerprint=context.fingerprint,
                    settings_signature=context.settings_signature,
                )
                progress.report()
                continue

            shutil.copy2(context.source_path, target_path)
            resolved_target_path = target_path.resolve()
            cleanup_stale_target(context.previous_target_path, resolved_target_path)
            stats.succeeded += 1
            if context.retry_of_failed:
                stats.record_retry_success()
            status = "success"
            journal.record_decision(
                source_path=context.source_path,
                target_path=resolved_target_path,
                status=status,
                score=score,
                relative_path=context.relative_path,
                fingerprint=context.fingerprint,
                settings_signature=context.settings_signature,
                summary=summary,
            )
            journal.record_processed(
                source_path=context.source_path,
                target_path=resolved_target_path,
                status=status,
                score=score,
                fingerprint=context.fingerprint,
                settings_signature=context.settings_signature,
            )
            LOGGER.info(
                "Processed %s -> %s [quality=%s category=%s]",
                context.source_path.name,
                target_path,
                score.quality,
                score.category,
            )
            progress.report()
        except Exception as exc:
            stats.record_failure_attempt(retry=context.retry_of_failed)
            LOGGER.warning("Scoring or copy failed for %s: %s", context.source_path, exc)
            journal.record_failure(
                context.source_path,
                "score_or_copy",
                str(exc),
                fingerprint=context.fingerprint,
                settings_signature=context.settings_signature,
            )
            collect_retry_failed_path(retry_failed_paths, context.source_path)
            progress.report()


def should_overwrite_existing_target(reprocess_reason: str, settings: Settings) -> bool:
    if not settings.OVERWRITE_CHANGED_TARGET:
        return False
    return reprocess_reason in {
        "source_changed",
        "settings_changed",
        "force_reprocess",
        "target_missing",
    }


def cleanup_stale_target(previous_target_path: Path | None, current_target_path: Path) -> None:
    if previous_target_path is None:
        return

    try:
        previous_resolved = previous_target_path.expanduser().resolve()
        current_resolved = current_target_path.expanduser().resolve()
    except OSError:
        LOGGER.debug("Could not resolve stale target path: %s", previous_target_path)
        return

    if previous_resolved == current_resolved or not previous_resolved.exists():
        return
    if previous_resolved.is_dir():
        LOGGER.warning("Not removing stale target directory: %s", previous_resolved)
        return

    try:
        previous_resolved.unlink()
        LOGGER.info("Removed stale routed copy: %s", previous_resolved)
    except OSError as exc:
        LOGGER.warning("Failed to remove stale routed copy %s: %s", previous_resolved, exc)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage",
        description="Document triage and classification middleware for RAG and agent pipelines.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="DocTriage 1.0.0",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        action="append",
        help="Source document directory. Repeat to analyze the union of multiple directories.",
    )
    parser.add_argument("--output-root", type=Path, help="Directory for generated state and routed copies.")
    parser.add_argument("--llm-endpoint", help="LLM endpoint, for example http://localhost:11434/api/generate.")
    parser.add_argument("--llm-model", help="LLM model name, for example gemma4:e4b.")
    parser.add_argument("--llm-api-key", help="LLM API key for OpenAI-compatible endpoints.")
    parser.add_argument("--concurrency", type=int, help="Maximum concurrent LLM requests.")
    parser.add_argument("--limit", type=int, help="Maximum number of files to prepare and score in this run.")
    parser.add_argument("--max-file-size-mb", type=float, help="Skip candidate files larger than this size.")
    parser.add_argument("--quality-threshold", type=int, help="Minimum quality score for HQ routing.")
    parser.add_argument("--timeout-seconds", type=int, help="LLM request timeout.")
    parser.add_argument("--retry-count", type=int, help="LLM retry count per request.")
    parser.add_argument("--num-ctx", type=int, help="Ollama context window option.")
    parser.add_argument(
        "--output-language",
        choices=["auto", "zh-CN", "en", "ja", "ko", "de", "fr", "es"],
        help="Natural-language output language for summaries/reasons. 'auto' infers from document body.",
    )
    parser.add_argument("--manifest-max-files", type=int, help="Maximum file rows sent to manifest analysis per directory.")
    parser.add_argument("--pdf-fallback-max-pages", type=int, help="Maximum PDF pages to extract with the local text fallback.")
    parser.add_argument("--progress-interval", type=float, help="Progress log/write interval in seconds.")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Score and record routing decisions without copying source documents.",
    )
    manifest_group = parser.add_mutually_exclusive_group()
    manifest_group.add_argument(
        "--skip-manifest-analysis",
        action="store_true",
        help="Skip directory-level series detection and start file-level scoring immediately.",
    )
    manifest_group.add_argument(
        "--manifest-analysis",
        action="store_true",
        help="Run directory-level series detection before file-level scoring.",
    )
    ocr_group = parser.add_mutually_exclusive_group()
    ocr_group.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable PDF OCR to speed up large first-pass runs.",
    )
    ocr_group.add_argument(
        "--ocr",
        action="store_true",
        help="Enable PDF OCR for scanned or image-only documents.",
    )
    parser.add_argument(
        "--pdf-metadata",
        action="store_true",
        help="Extract native PDF metadata in the profiler. This reopens PDFs and can slow large runs.",
    )
    parser.add_argument(
        "--document-summary",
        action="store_true",
        help="Persist short local text summaries in decisions.jsonl for better relationship mining.",
    )
    parser.add_argument(
        "--no-overwrite-changed-target",
        action="store_true",
        help="Do not refresh an existing copied target when the source/settings changed.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable periodic progress logs and progress.json writes.",
    )
    parser.add_argument(
        "--no-change-detection",
        action="store_true",
        help="Disable source/settings fingerprint checks and use legacy path-based resume behavior.",
    )
    parser.add_argument(
        "--content-hash",
        action="store_true",
        help="Include SHA-256 content hash in source fingerprints. Slower on large folders.",
    )
    parser.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Ignore processed state and reprocess selected files.",
    )
    parser.add_argument(
        "--no-retry-failed",
        action="store_true",
        help="Skip files that previously failed with the same source/settings fingerprint.",
    )
    parser.add_argument(
        "--mine-relationships",
        action="store_true",
        help="Run relationship mining after document scoring completes.",
    )
    parser.add_argument(
        "--relationship-use-embeddings",
        action="store_true",
        help="Enable optional embedding-based relationship signals.",
    )
    parser.add_argument(
        "--relationship-use-text-citations",
        action="store_true",
        help="Enable lightweight title/path citation signals during relationship mining.",
    )
    parser.add_argument(
        "--relationship-workers",
        type=int,
        help="Worker process count for non-LLM relationship mining. Defaults to an automatic CPU-based value.",
    )
    parser.add_argument("--embedding-endpoint", help="Embedding endpoint, for example http://localhost:11434/api/embeddings.")
    parser.add_argument("--embedding-model", help="Embedding model name.")
    parser.add_argument("--embedding-api-key", help="Embedding API key. Defaults to LLM_API_KEY when omitted.")
    return parser


def build_settings_from_args(args: argparse.Namespace) -> Settings:
    if args.skip_manifest_analysis and args.manifest_analysis:
        raise ValueError(
            "--manifest-analysis and --skip-manifest-analysis cannot be used together."
        )
    if args.no_ocr and args.ocr:
        raise ValueError("--ocr and --no-ocr cannot be used together.")

    overrides: dict[str, Any] = {}
    if args.source_dir:
        overrides["SOURCE_DIR"] = args.source_dir[0]
        overrides["ADDITIONAL_SOURCE_DIRS"] = tuple(args.source_dir[1:])
    if args.output_root is not None:
        overrides["OUTPUT_ROOT"] = args.output_root
    if args.llm_endpoint is not None:
        overrides["LLM_ENDPOINT"] = args.llm_endpoint
    if args.llm_model is not None:
        overrides["LLM_MODEL"] = args.llm_model
    if args.llm_api_key is not None:
        overrides["LLM_API_KEY"] = args.llm_api_key
    if args.concurrency is not None:
        overrides["CONCURRENCY_LIMIT"] = args.concurrency
    if args.limit is not None:
        overrides["MAX_FILES"] = args.limit
    if args.max_file_size_mb is not None:
        overrides["MAX_FILE_SIZE_MB"] = args.max_file_size_mb
    if args.quality_threshold is not None:
        overrides["QUALITY_THRESHOLD"] = args.quality_threshold
    if args.timeout_seconds is not None:
        overrides["LLM_TIMEOUT_SECONDS"] = args.timeout_seconds
    if args.retry_count is not None:
        overrides["LLM_RETRY_COUNT"] = args.retry_count
    if args.num_ctx is not None:
        overrides["LLM_NUM_CTX"] = args.num_ctx
    if args.output_language is not None:
        overrides["OUTPUT_LANGUAGE"] = args.output_language
    if args.manifest_max_files is not None:
        overrides["MANIFEST_MAX_FILES"] = args.manifest_max_files
    if args.pdf_fallback_max_pages is not None:
        overrides["PDF_TEXT_FALLBACK_MAX_PAGES"] = args.pdf_fallback_max_pages
    if args.progress_interval is not None:
        overrides["PROGRESS_LOG_INTERVAL_SECONDS"] = args.progress_interval
    if args.plan_only:
        overrides["COPY_FILES"] = False
    if args.skip_manifest_analysis:
        overrides["SKIP_MANIFEST_ANALYSIS"] = True
    if args.manifest_analysis:
        overrides["SKIP_MANIFEST_ANALYSIS"] = False
    if args.no_ocr:
        overrides["OCR_ENABLED"] = False
    if args.ocr:
        overrides["OCR_ENABLED"] = True
    if args.pdf_metadata:
        overrides["PDF_METADSample_ENABLED"] = True
    if args.document_summary:
        overrides["DOCUMENT_SUMMARY_ENABLED"] = True
    if args.no_overwrite_changed_target:
        overrides["OVERWRITE_CHANGED_TARGET"] = False
    if args.no_progress:
        overrides["PROGRESS_ENABLED"] = False
    if args.no_change_detection:
        overrides["CHANGE_DETECTION_ENABLED"] = False
    if args.content_hash:
        overrides["CHANGE_DETECTION_USE_CONTENT_HASH"] = True
    if args.force_reprocess:
        overrides["FORCE_REPROCESS"] = True
    if args.no_retry_failed:
        overrides["RETRY_FAILED"] = False
    if args.mine_relationships:
        overrides["RELATIONSHIP_MINING_ENABLED"] = True
    if args.relationship_use_embeddings:
        overrides["RELATIONSHIP_USE_EMBEDDINGS"] = True
    if args.relationship_use_text_citations:
        overrides["RELATIONSHIP_USE_TEXT_CITATIONS"] = True
    if args.relationship_workers is not None:
        overrides["RELATIONSHIP_WORKERS"] = args.relationship_workers
    if args.embedding_endpoint is not None:
        overrides["EMBEDDING_ENDPOINT"] = args.embedding_endpoint
    if args.embedding_model is not None:
        overrides["EMBEDDING_MODEL"] = args.embedding_model
    if args.embedding_api_key is not None:
        overrides["EMBEDDING_API_KEY"] = args.embedding_api_key

    if overrides:
        settings = Settings(**overrides)
    else:
        settings = get_settings()
    if settings.RELATIONSHIP_USE_EMBEDDINGS and not str(settings.EMBEDDING_MODEL or "").strip():
        raise ValueError(
            "--embedding-model is required when --relationship-use-embeddings is enabled."
        )
    return settings


def main(argv: list[str] | None = None) -> None:
    configure_utf8_runtime()
    effective_argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    if not effective_argv:
        parser.print_help()
        print()
        launch_default_ui()
        return

    args = parser.parse_args(effective_argv)
    run_pipeline(build_settings_from_args(args))


def launch_default_ui() -> None:
    url = f"http://{DEFAULT_UI_HOST}:{DEFAULT_UI_PORT}/"
    if is_doctriage_ui_running(url):
        print(f"DocTriage Console already running: {url}")
        webbrowser.open(url)
        return

    try:
        from reading_ui import serve

        serve(None, DEFAULT_UI_HOST, DEFAULT_UI_PORT, open_browser=True)
    except OSError as exc:
        print(f"Port {DEFAULT_UI_PORT} is unavailable ({exc}); starting on a free port.")
        from reading_ui import serve

        serve(None, DEFAULT_UI_HOST, 0, open_browser=True)


def is_doctriage_ui_running(base_url: str) -> bool:
    config_url = base_url.rstrip("/") + "/api/config"
    try:
        with urllib.request.urlopen(config_url, timeout=1.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return False
    return isinstance(payload, dict) and "capabilities" in payload


if __name__ == "__main__":
    main()
