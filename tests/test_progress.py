import json
from pathlib import Path

from config import Settings
import main
from main import ProgressReporter, RunStats, format_duration, scan_candidate_files


def make_settings(source_dir: Path, output_root: Path) -> Settings:
    return Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        PROGRESS_LOG_INTERVAL_SECONDS=1,
    )


def test_format_duration() -> None:
    assert format_duration(None) == "unknown"
    assert format_duration(5) == "5s"
    assert format_duration(65) == "1m05s"
    assert format_duration(3665) == "1h01m"


def test_progress_reporter_writes_snapshot(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    settings = make_settings(source_dir, output_root)
    stats = RunStats(selected_files=10)
    reporter = ProgressReporter(settings, stats)
    start = reporter.started_at
    reporter.start_rate_window(now=start)
    stats.planned = 4
    stats.failed = 1

    reporter.report(force=True, now=start + 60)

    payload = json.loads(settings.progress_path.read_text(encoding="utf-8"))
    assert payload["total"] == 10
    assert payload["completed"] == 5
    assert payload["remaining"] == 5
    assert payload["percent"] == 50.0
    assert payload["eta_seconds"] is not None
    assert payload["rate_window_started"] is True
    assert payload["rate_window_completed"] == 5


def test_progress_reporter_writes_first_nonzero_activity_before_interval(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    settings = make_settings(source_dir, output_root).model_copy(
        update={"PROGRESS_LOG_INTERVAL_SECONDS": 30}
    )
    stats = RunStats(selected_files=10)
    reporter = ProgressReporter(settings, stats)

    reporter.report(force=True)
    stats.skipped_resumed = 1
    reporter.report()

    payload = json.loads(settings.progress_path.read_text(encoding="utf-8"))
    assert payload["completed"] == 1
    assert payload["skipped_resumed"] == 1
    assert payload["throughput_completed"] == 0
    assert payload["rate_window_started"] is False
    assert payload["rate_window_completed"] == 0
    assert payload["files_per_minute"] == 0.0
    assert payload["eta_seconds"] is None
    assert payload["eta_human"] == "unknown"


def test_progress_rate_window_excludes_resume_before_analysis(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    settings = make_settings(source_dir, output_root)
    stats = RunStats(selected_files=10)
    reporter = ProgressReporter(settings, stats)
    start = reporter.started_at

    stats.skipped_resumed = 4
    resume_snapshot = reporter.snapshot(now=start + 120)

    assert resume_snapshot["completed"] == 4
    assert resume_snapshot["rate_window_started"] is False
    assert resume_snapshot["files_per_minute"] == 0.0
    assert resume_snapshot["eta_seconds"] is None

    reporter.start_rate_window(now=start + 120)
    stats.planned = 2
    analysis_snapshot = reporter.snapshot(now=start + 180)

    assert analysis_snapshot["completed"] == 6
    assert analysis_snapshot["rate_window_started"] is True
    assert analysis_snapshot["rate_window_completed"] == 2
    assert analysis_snapshot["files_per_minute"] == 2.0


def test_progress_rate_window_freezes_before_retry(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    settings = make_settings(source_dir, output_root)
    stats = RunStats(selected_files=10)
    reporter = ProgressReporter(settings, stats)
    start = reporter.started_at

    reporter.start_rate_window(now=start)
    stats.planned = 2
    active_snapshot = reporter.snapshot(now=start + 60)
    reporter.stop_rate_window(now=start + 60)
    stats.planned = 4
    retry_snapshot = reporter.snapshot(now=start + 180)

    assert active_snapshot["rate_window_active"] is True
    assert active_snapshot["files_per_minute"] == 2.0
    assert retry_snapshot["rate_window_active"] is False
    assert retry_snapshot["rate_window_completed"] == 2
    assert retry_snapshot["files_per_minute"] == 0.0
    assert retry_snapshot["eta_seconds"] is None


def test_progress_completion_excludes_oversized_files() -> None:
    stats = RunStats(selected_files=2, succeeded=1, skipped_too_large=5)

    assert stats.completed == 1


def test_scan_candidate_files_counts_oversized_once(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    (source_dir / "small.md").write_text("ok", encoding="utf-8")
    (source_dir / "large.md").write_text("x" * 2048, encoding="utf-8")
    settings = make_settings(source_dir, output_root).model_copy(
        update={"MAX_FILE_SIZE_MB": 0.001}
    )

    directory_map, skipped_too_large, stat_failures = scan_candidate_files(settings)

    assert skipped_too_large == 1
    assert stat_failures == 0
    assert [path.name for paths in directory_map.values() for path in paths] == [
        "small.md"
    ]


def test_pipeline_writes_summary_when_all_files_are_oversized(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    (source_dir / "large.md").write_text("x" * 2048, encoding="utf-8")
    settings = make_settings(source_dir, output_root).model_copy(
        update={"MAX_FILE_SIZE_MB": 0.001}
    )

    main.run_pipeline(settings)

    summary = json.loads(
        settings.processed_log_path.parent.joinpath("run_summary.json").read_text(
            encoding="utf-8"
        )
    )
    progress = json.loads(settings.progress_path.read_text(encoding="utf-8"))
    assert summary["skipped_too_large"] == 1
    assert progress["skipped_too_large"] == 1
