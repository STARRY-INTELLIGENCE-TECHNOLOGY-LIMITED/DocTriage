from pathlib import Path

from config import Settings
from main import (
    ResumeJournal,
    build_compatible_settings_signatures,
    build_file_fingerprint,
    build_settings_signature,
    build_settings_signature_payload,
    settings_signature_from_payload,
)


def make_settings(source_dir: Path, output_root: Path, **overrides: object) -> Settings:
    return Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        **overrides,
    )


def test_resume_skips_when_fingerprint_and_settings_match(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    settings = make_settings(source_dir, output_root)
    journal = ResumeJournal(
        processed_log_path=settings.processed_log_path,
        failure_log_path=settings.failure_log_path,
    )
    fingerprint = build_file_fingerprint(file_path, settings)
    signature = build_settings_signature(settings)

    journal.record_processed(
        source_path=file_path.resolve(),
        target_path=(output_root / "HQ" / "doc.md").resolve(),
        status="planned",
        fingerprint=fingerprint,
        settings_signature=signature,
    )

    should_skip, reason = journal.should_skip(
        file_path.resolve(),
        require_target_exists=False,
        fingerprint=fingerprint,
        settings_signature=signature,
        settings=settings,
    )

    assert should_skip is True
    assert reason == "processed"


def test_resume_reprocesses_when_source_changes(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    settings = make_settings(source_dir, output_root)
    journal = ResumeJournal(settings.processed_log_path, settings.failure_log_path)
    old_fingerprint = build_file_fingerprint(file_path, settings)
    signature = build_settings_signature(settings)
    journal.record_processed(
        file_path.resolve(),
        (output_root / "HQ" / "doc.md").resolve(),
        "planned",
        fingerprint=old_fingerprint,
        settings_signature=signature,
    )

    file_path.write_text("hello changed", encoding="utf-8")
    new_fingerprint = build_file_fingerprint(file_path, settings)
    should_skip, reason = journal.should_skip(
        file_path.resolve(),
        require_target_exists=False,
        fingerprint=new_fingerprint,
        settings_signature=signature,
        settings=settings,
    )

    assert should_skip is False
    assert reason == "source_changed"


def test_resume_reprocesses_when_settings_signature_changes(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    settings = make_settings(source_dir, output_root)
    changed_settings = make_settings(source_dir, output_root, QUALITY_THRESHOLD=90)
    journal = ResumeJournal(settings.processed_log_path, settings.failure_log_path)
    fingerprint = build_file_fingerprint(file_path, settings)
    journal.record_processed(
        file_path.resolve(),
        (output_root / "HQ" / "doc.md").resolve(),
        "planned",
        fingerprint=fingerprint,
        settings_signature=build_settings_signature(settings),
    )

    should_skip, reason = journal.should_skip(
        file_path.resolve(),
        require_target_exists=False,
        fingerprint=fingerprint,
        settings_signature=build_settings_signature(changed_settings),
        settings=changed_settings,
    )

    assert should_skip is False
    assert reason == "settings_changed"


def test_resume_accepts_legacy_summary_signature_without_reprocessing(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    settings = make_settings(
        source_dir,
        output_root,
        DOCUMENT_SUMMARY_ENABLED=True,
        DOCUMENT_SUMMARY_MAX_CHARS=600,
        OUTPUT_LANGUAGE="auto",
    )
    assert settings.PIPELINE_VERSION == "0.1.0"
    legacy_payload = build_settings_signature_payload(settings)
    legacy_payload["document_summary_max_chars"] = 240
    legacy_payload.pop("output_language", None)
    legacy_signature = settings_signature_from_payload(legacy_payload)
    current_signature = build_settings_signature(settings)
    assert legacy_signature in build_compatible_settings_signatures(
        settings, current_signature
    )

    journal = ResumeJournal(settings.processed_log_path, settings.failure_log_path)
    fingerprint = build_file_fingerprint(file_path, settings)
    journal.record_processed(
        file_path.resolve(),
        (output_root / "HQ" / "doc.md").resolve(),
        "planned",
        fingerprint=fingerprint,
        settings_signature=legacy_signature,
    )

    should_skip, reason = journal.should_skip(
        file_path.resolve(),
        require_target_exists=False,
        fingerprint=fingerprint,
        settings_signature=current_signature,
        settings=settings,
    )

    assert should_skip is True
    assert reason == "processed"


def test_legacy_resume_can_disable_change_detection(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    settings = make_settings(source_dir, output_root, CHANGE_DETECTION_ENABLED=False)
    journal = ResumeJournal(settings.processed_log_path, settings.failure_log_path)
    fingerprint = build_file_fingerprint(file_path, settings)
    journal.record_processed(
        file_path.resolve(),
        (output_root / "HQ" / "doc.md").resolve(),
        "planned",
    )

    file_path.write_text("hello changed", encoding="utf-8")
    should_skip, reason = journal.should_skip(
        file_path.resolve(),
        require_target_exists=False,
        fingerprint=fingerprint,
        settings_signature="different",
        settings=settings,
    )

    assert should_skip is True
    assert reason == "processed"


def test_can_skip_previous_failure_when_retry_disabled(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("hello", encoding="utf-8")

    settings = make_settings(source_dir, output_root, RETRY_FAILED=False)
    journal = ResumeJournal(settings.processed_log_path, settings.failure_log_path)
    fingerprint = build_file_fingerprint(file_path, settings)
    signature = build_settings_signature(settings)

    journal.record_failure(
        file_path.resolve(),
        "wash",
        "failed",
        fingerprint=fingerprint,
        settings_signature=signature,
    )

    should_skip, reason = journal.should_skip_failed(
        file_path.resolve(),
        fingerprint=fingerprint,
        settings_signature=signature,
        settings=settings,
    )

    assert should_skip is True
    assert reason == "previous_failure"
