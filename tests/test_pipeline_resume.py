import json
import threading
import time
from pathlib import Path

import main
import relationship_miner
from config import Settings
from ranker_engine import SemanticScore
from meta_profiler import DocumentProfile


def test_pipeline_resume_then_reprocess_changed_file(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("# Title\n\nbody", encoding="utf-8")

    calls = {"score": 0}

    def fake_score_document(self, file_path, clean_markdown, profile, manifest):
        calls["score"] += 1
        return SemanticScore(
            quality=80,
            category="Design",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        )

    monkeypatch.setattr(
        main.ManifestAnalysis,
        "analyze_directory",
        lambda self, directory, files, source_root: main.ManifestResult(),
    )
    monkeypatch.setattr(
        main.SemanticScoring,
        "score_document",
        fake_score_document,
    )

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
    )

    main.run_pipeline(settings)
    assert calls["score"] == 1
    assert (output_root / "_state" / "progress.json").exists()

    main.run_pipeline(settings)
    assert calls["score"] == 1

    file_path.write_text("# Title\n\nchanged body", encoding="utf-8")
    main.run_pipeline(settings)
    assert calls["score"] == 2


def test_previous_failures_are_scored_first(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    first = source_dir / "a.md"
    failed = source_dir / "z.md"
    first.write_text("# A\n\nbody", encoding="utf-8")
    failed.write_text("# Z\n\nbody", encoding="utf-8")
    order: list[str] = []

    def fake_score_document(self, file_path, clean_markdown, profile, manifest):
        order.append(Path(file_path).name)
        return SemanticScore(
            quality=80,
            category="Design",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        )

    monkeypatch.setattr(main.SemanticScoring, "score_document", fake_score_document)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
    )
    journal = main.ResumeJournal(settings.processed_log_path, settings.failure_log_path)
    journal.record_failure(failed.resolve(), "score", "previous failure")

    main.run_pipeline(settings)

    assert order[0] == "z.md"


def test_prepare_stage_runs_concurrently(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    for index in range(4):
        (source_dir / f"doc{index}.md").write_text("# Title\n\nbody", encoding="utf-8")

    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_prepare_document_for_scoring(source_path, settings):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return main.PreparedDocument(
            clean_markdown="body",
            profile=DocumentProfile(
                file_name=Path(source_path).name,
                file_suffix=".md",
                file_size_bytes=1,
                created_at="2026-01-01T00:00:00+00:00",
                modified_at="2026-01-01T00:00:00+00:00",
                ctime_mtime_span_seconds=0,
                header_density=0,
                header_count=0,
                non_empty_lines=1,
                code_to_text_ratio=0,
                code_block_count=0,
            ),
            summary="",
        )

    monkeypatch.setattr(
        main,
        "prepare_document_for_scoring",
        fake_prepare_document_for_scoring,
    )
    monkeypatch.setattr(
        main.SemanticScoring,
        "score_document",
        lambda self, file_path, clean_markdown, profile, manifest: SemanticScore(
            quality=80,
            category="Design",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        ),
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=3,
        SKIP_MANIFEST_ANALYSIS=True,
    )

    main.run_pipeline(settings)

    assert max_active == 3


def test_pipeline_writes_llm_summary_when_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text(
        "<!-- page 1 -->\n\n# Title\n\n创作中心\n\nLocal noisy body",
        encoding="utf-8",
    )

    def fake_score_document(self, file_path, clean_markdown, profile, manifest):
        return SemanticScore(
            quality=80,
            category="Design",
            summary="本文聚焦复杂表单的状态管理，通过分层模型和校验流水线减少重复逻辑，适合复用到前端配置平台。",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        )

    monkeypatch.setattr(main.SemanticScoring, "score_document", fake_score_document)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
        DOCUMENT_SUMMARY_ENABLED=True,
    )

    main.run_pipeline(settings)

    decision = json.loads(
        (output_root / "_state" / "decisions.jsonl").read_text(encoding="utf-8")
    )
    assert decision["summary"].startswith("本文聚焦复杂表单")
    assert "<!-- page" not in decision["summary"]
    assert "创作中心" not in decision["summary"]


def test_failed_document_is_retried_once_at_end(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("# Title\n\nbody", encoding="utf-8")
    calls = {"value": 0}

    def fake_score_document(self, file_path, clean_markdown, profile, manifest):
        calls["value"] += 1
        if calls["value"] == 1:
            raise RuntimeError("temporary model failure")
        return SemanticScore(
            quality=80,
            category="Design",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        )

    monkeypatch.setattr(main.SemanticScoring, "score_document", fake_score_document)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
    )

    main.run_pipeline(settings)

    assert calls["value"] == 2
    decisions = (output_root / "_state" / "decisions.jsonl").read_text(encoding="utf-8")
    assert '"relative_path": "doc.md"' in decisions
    summary = json.loads(
        (output_root / "_state" / "run_summary.json").read_text(encoding="utf-8")
    )
    progress = json.loads(
        (output_root / "_state" / "progress.json").read_text(encoding="utf-8")
    )
    assert summary["completed"] == 1
    assert summary["plan_only"] is True
    assert summary["copy_files"] is False
    assert progress["plan_only"] is True
    assert progress["copy_files"] is False
    assert summary["failed"] == 0
    assert summary["failed_attempts"] == 1
    assert summary["retry_attempted"] == 1
    assert summary["retry_succeeded"] == 1
    assert summary["unresolved_failures"] == 0
    assert summary["recovered_failed_sources"] == 1
    assert progress["failed"] == 0


def test_failed_document_retry_keeps_unresolved_failure_count_unique(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("# Title\n\nbody", encoding="utf-8")
    calls = {"value": 0}

    def fake_score_document(self, file_path, clean_markdown, profile, manifest):
        calls["value"] += 1
        raise RuntimeError("persistent model failure")

    monkeypatch.setattr(main.SemanticScoring, "score_document", fake_score_document)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
    )

    main.run_pipeline(settings)

    summary = json.loads(
        (output_root / "_state" / "run_summary.json").read_text(encoding="utf-8")
    )
    progress = json.loads(
        (output_root / "_state" / "progress.json").read_text(encoding="utf-8")
    )
    assert calls["value"] == 2
    assert summary["completed"] == 1
    assert summary["failed"] == 1
    assert summary["failed_attempts"] == 2
    assert summary["retry_attempted"] == 1
    assert summary["retry_still_failed"] == 1
    assert summary["unresolved_failures"] == 1
    assert progress["failed"] == 1


def test_changed_source_refreshes_existing_copy(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    file_path = source_dir / "doc.md"
    file_path.write_text("# Title\n\nfirst", encoding="utf-8")

    call_count = {"value": 0}

    def fake_score_document(self, file_path, clean_markdown, profile, manifest):
        call_count["value"] += 1
        category = "Design" if call_count["value"] == 1 else "Implementation"
        return SemanticScore(
            quality=80,
            category=category,
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        )

    monkeypatch.setattr(
        main.SemanticScoring,
        "score_document",
        fake_score_document,
    )

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=True,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
    )

    main.run_pipeline(settings)
    target_path = output_root / "HQ" / "Design" / "doc.md"
    assert target_path.read_text(encoding="utf-8") == "# Title\n\nfirst"

    file_path.write_text("# Title\n\nsecond", encoding="utf-8")
    main.run_pipeline(settings)

    new_target_path = output_root / "HQ" / "Implementation" / "doc.md"
    assert new_target_path.read_text(encoding="utf-8") == "# Title\n\nsecond"
    assert not target_path.exists()


def test_run_pipeline_rejects_active_output_lock(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    (source_dir / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
    (state_dir / "run.lock").write_text(
        '{"pid": 12345, "token": "other"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "is_process_alive", lambda pid: True)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
    )

    try:
        main.run_pipeline(settings)
    except RuntimeError as exc:
        assert "already using this OUTPUT_ROOT" in str(exc)
    else:
        raise AssertionError("Expected active run lock to reject concurrent run")


def test_run_pipeline_removes_stale_output_lock(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    (source_dir / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
    (state_dir / "run.lock").write_text(
        '{"pid": 12345, "token": "stale"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "is_process_alive", lambda pid: False)
    monkeypatch.setattr(
        main.SemanticScoring,
        "score_document",
        lambda self, file_path, clean_markdown, profile, manifest: SemanticScore(
            quality=80,
            category="Design",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        ),
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
    )

    main.run_pipeline(settings)

    assert not (state_dir / "run.lock").exists()


def test_embedding_relationships_are_mined_after_analysis_when_selected(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    (source_dir / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
    relationship_settings: list[Settings] = []

    monkeypatch.setattr(
        main.SemanticScoring,
        "score_document",
        lambda self, file_path, clean_markdown, profile, manifest: SemanticScore(
            quality=80,
            category="Design",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        ),
    )
    monkeypatch.setattr(
        relationship_miner,
        "mine_relationships",
        lambda settings: relationship_settings.append(settings),
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
        RELATIONSHIP_MINING_ENABLED=True,
        RELATIONSHIP_USE_EMBEDDINGS=True,
    )

    main.run_pipeline(settings)

    assert len(relationship_settings) == 1
    assert relationship_settings[0].RELATIONSHIP_USE_EMBEDDINGS is True


def test_plain_relationship_mining_does_not_release_scoring_model(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    (source_dir / "doc.md").write_text("# Title\n\nbody", encoding="utf-8")
    events: list[str] = []

    monkeypatch.setattr(
        main.SemanticScoring,
        "score_document",
        lambda self, file_path, clean_markdown, profile, manifest: SemanticScore(
            quality=80,
            category="Design",
            knowledge_density=80,
            implementation_specificity=40,
            logical_structure=80,
            reason="test",
        ),
    )
    monkeypatch.setattr(
        relationship_miner,
        "mine_relationships",
        lambda settings: events.append("mine"),
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        COPY_FILES=False,
        CONCURRENCY_LIMIT=1,
        SKIP_MANIFEST_ANALYSIS=True,
        RELATIONSHIP_MINING_ENABLED=True,
        RELATIONSHIP_USE_EMBEDDINGS=False,
    )

    main.run_pipeline(settings)

    assert events == ["mine"]
