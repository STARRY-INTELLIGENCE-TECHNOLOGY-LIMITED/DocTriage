import json
import subprocess
import time
from pathlib import Path

import pytest

import reading_ui
from reading_tracker import ReadingPaths
from reading_ui import (
    AppState,
    analysis_status,
    build_analysis_command,
    build_failure_rows,
    build_rag_payload,
    build_relationship_payload,
    build_state_payload,
    config_payload,
    infer_source_dir_from_decisions,
    mark_document,
    mark_documents,
    model_api_key_env,
    open_failure_document,
    reading_paths_from_payload,
    reset_analysis_output,
    reset_relationship_output,
    relationship_task_command,
    rag_log_path,
    rag_task_command,
    rag_redaction_env,
    run_lock_path,
    row_matches_query,
    set_reading_output,
    sort_rows,
    start_analysis,
    start_early_relationships,
    start_rag_task,
    start_relationship_task,
    stop_analysis,
    stop_rag_task,
    stop_relationship_task,
    latest_log_activity,
    subprocess_env_for_payload,
)


@pytest.fixture(autouse=True)
def clear_source_file_scan_cache() -> None:
    reading_ui.clear_source_file_scan_cache()


def frontend_source() -> str:
    return reading_ui.read_ui_frontend_source()


def frontend_source_compact() -> str:
    return " ".join(frontend_source().split())


def test_reading_ui_builds_filtered_state_payload(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    first = source_dir / "alpha.md"
    second = source_dir / "beta.md"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")

    decisions = [
        {
            "source_path": str(first),
            "relative_path": "alpha.md",
            "status": "planned",
            "quality": 90,
            "category": "Architecture",
            "target_path": str(output_root / "HQ" / "Architecture" / "alpha.md"),
            "document_kind": "ArchitectureDecision",
            "topic_tags": ["DistributedSystems"],
            "sensitivity_risk": 20,
            "public_writing_suitability": 80,
            "summary": "Alpha architecture summary",
            "reason": "High-density distributed systems design notes",
            "knowledge_density": 88,
            "implementation_specificity": 81,
            "logical_structure": 79,
            "evidence_richness": 76,
            "actionability": 84,
            "strategic_value": 72,
            "freshness": 66,
            "uniqueness": 64,
        },
        {
            "source_path": str(second),
            "relative_path": "beta.md",
            "status": "planned",
            "quality": 70,
            "category": "LowQuality",
            "sensitivity_risk": 10,
            "public_writing_suitability": 90,
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    payload = build_state_payload(
        ReadingPaths(source_dir=source_dir, output_root=output_root),
        {"status": "unread", "min_quality": "80", "q": "distributed"},
    )

    assert payload["total_count"] == 2
    assert payload["filtered_count"] == 1
    assert payload["available_categories"] == ["Architecture", "LowQuality"]
    assert payload["available_topic_tags"] == ["DistributedSystems"]
    assert payload["rows"][0]["relative_path"] == "alpha.md"
    assert payload["rows"][0]["display_name"] == "alpha.md"
    assert payload["rows"][0]["target_path"] == ""
    assert payload["rows"][0]["summary"] == "Alpha architecture summary"
    assert payload["rows"][0]["reason"] == "High-density distributed systems design notes"
    assert payload["rows"][0]["knowledge_density"] == 88
    assert payload["rows"][0]["implementation_specificity"] == 81
    assert payload["rows"][0]["logical_structure"] == 79
    assert payload["rows"][0]["evidence_richness"] == 76
    assert payload["rows"][0]["actionability"] == 84
    assert payload["rows"][0]["strategic_value"] == 72
    assert payload["rows"][0]["freshness"] == 66
    assert payload["rows"][0]["uniqueness"] == 64


def test_reading_ui_source_scope_includes_unanalyzed_files_and_ignores_quality_filters(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    nested = source_dir / "author"
    nested.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    analyzed = source_dir / "analyzed.md"
    source_only = nested / "draft.md"
    analyzed.write_text("analyzed", encoding="utf-8")
    source_only.write_text("draft", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(analyzed),
                "relative_path": "analyzed.md",
                "status": "planned",
                "quality": 90,
                "category": "Design",
                "fingerprint": {"size_bytes": 8, "mtime_ns": 1},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "reading_status.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(source_only),
                "relative_path": "author/draft.md",
                "status": "deferred",
                "note": "later",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = build_state_payload(
        ReadingPaths(source_dir=source_dir, output_root=output_root),
        {"scope": "source", "min_quality": "100", "sort": "source_path_asc"},
    )

    assert payload["scope"] == "source"
    assert payload["total_count"] == 2
    assert [row["relative_path"] for row in payload["rows"]] == [
        "analyzed.md",
        "author/draft.md",
    ]
    source_row = payload["rows"][1]
    assert source_row["source_only"] is True
    assert source_row["status"] == "deferred"
    assert source_row["quality"] is None
    assert source_row["source_mtime_label"]
    assert source_row["source_size_label"].endswith("B")


def test_reading_ui_source_scope_sorts_by_modified_time(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    older = source_dir / "older.md"
    newer = source_dir / "newer.md"
    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")
    old_time = 1_700_000_000
    new_time = 1_800_000_000
    import os

    os.utime(older, (old_time, old_time))
    os.utime(newer, (new_time, new_time))

    payload = build_state_payload(
        ReadingPaths(source_dir=source_dir, output_root=output_root),
        {"scope": "source", "sort": "source_mtime_desc"},
    )

    assert [row["relative_path"] for row in payload["rows"]] == ["newer.md", "older.md"]


def test_supported_source_file_scan_uses_short_cache(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    first = source_dir / "first.md"
    first.write_text("first", encoding="utf-8")
    calls = 0
    original_rglob = Path.rglob

    def counting_rglob(path, pattern):
        nonlocal calls
        calls += 1
        return original_rglob(path, pattern)

    monkeypatch.setattr(reading_ui, "SOURCE_FILE_SCAN_CACHE_TTL_SECONDS", 60.0)
    monkeypatch.setattr(Path, "rglob", counting_rglob)

    first_scan = reading_ui.iter_supported_source_files(source_dir)
    second = source_dir / "second.md"
    second.write_text("second", encoding="utf-8")
    cached_scan = reading_ui.iter_supported_source_files(source_dir)
    reading_ui.clear_source_file_scan_cache(source_dir)
    refreshed_scan = reading_ui.iter_supported_source_files(source_dir)

    assert calls == 2
    assert [path.name for path in first_scan] == ["first.md"]
    assert [path.name for path in cached_scan] == ["first.md"]
    assert sorted(path.name for path in refreshed_scan) == ["first.md", "second.md"]


def test_reading_ui_source_scope_excludes_missing_legacy_decisions(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    current = source_dir / "current.md"
    missing = source_dir / "missing.md"
    current.write_text("current", encoding="utf-8")
    decisions = [
        {
            "source_path": str(current),
            "relative_path": "current.md",
            "status": "planned",
            "quality": 90,
            "category": "Design",
        },
        {
            "source_path": str(missing),
            "relative_path": "missing.md",
            "status": "planned",
            "quality": 95,
            "category": "Design",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    payload = build_state_payload(
        ReadingPaths(source_dir=source_dir, output_root=output_root),
        {"scope": "source", "sort": "source_path_asc"},
    )

    assert [row["relative_path"] for row in payload["rows"]] == ["current.md"]


def test_reading_ui_merges_unresolved_failures_into_reading_rows(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    document = source_dir / "scan.pdf"
    document.write_bytes(b"%PDF-1.4")
    recovered = source_dir / "recovered.pdf"
    recovered.write_bytes(b"%PDF-1.4")

    failures = [
        {
            "source_path": str(document),
            "stage": "wash",
            "error": "PDF text fallback produced empty text",
        },
        {
            "source_path": str(document),
            "stage": "retry_wash",
            "error": "PDF text fallback produced empty text",
        },
        {
            "source_path": str(recovered),
            "stage": "wash",
            "error": "temporary model failure",
        },
    ]
    with (state_dir / "failed_files.jsonl").open("w", encoding="utf-8") as handle:
        for failure in failures:
            handle.write(json.dumps(failure, ensure_ascii=False) + "\n")
    (state_dir / "processed_files.jsonl").write_text(
        json.dumps({"source_path": str(recovered)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    payload = build_state_payload(paths, {"status": "failed", "q": "ocr"})

    assert payload["total_count"] == 1
    assert payload["filtered_count"] == 1
    row = payload["rows"][0]
    assert row["status"] == "failed"
    assert row["relative_path"] == "scan.pdf"
    assert row["attempts"] == 2
    assert row["failure_stage"] == "retry_wash"
    assert row["failure_reason"] == "PDF 无文本层/需 OCR"
    assert row["exists"] is True
    assert row["size_label"].endswith("B")
    assert "scan.pdf" in row["source_path"]


def test_reading_ui_can_open_known_failed_document_only(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    document = source_dir / "broken.docx"
    document.write_text("doc", encoding="utf-8")
    unknown = source_dir / "unknown.docx"
    unknown.write_text("doc", encoding="utf-8")
    (state_dir / "failed_files.jsonl").write_text(
        json.dumps(
            {"source_path": str(document), "stage": "wash", "error": "not valid"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    opened = []
    monkeypatch.setattr(reading_ui, "open_path", lambda path: opened.append(path))

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    payload = open_failure_document(paths, {"source_path": str(document)}, reveal=False)

    assert payload["ok"] is True
    assert opened == [document]
    with pytest.raises(ValueError, match="Unknown failed document"):
        open_failure_document(paths, {"source_path": str(unknown)}, reveal=False)


def test_failure_rows_are_available_without_decision_log(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    document = source_dir / "empty.txt"
    document.write_text("", encoding="utf-8")
    (state_dir / "failed_files.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "stage": "wash",
                "error": "Input document is empty",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    rows = build_failure_rows(ReadingPaths(source_dir=source_dir, output_root=output_root))

    assert rows[0]["relative_path"] == "empty.txt"
    assert rows[0]["failure_reason"] == "空文件"


def test_reading_ui_mark_document_appends_event(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    document.write_text("doc", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
                "quality": 88,
                "category": "CaseStudy",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    event = mark_document(paths, {"relative_path": "doc.md", "status": "reading"})

    assert event["status"] == "reading"
    assert (state_dir / "reading_status.jsonl").exists()


def test_reading_ui_mark_document_appends_event_for_source_only_file(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    nested = source_dir / "folder"
    nested.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    document = nested / "doc.md"
    document.write_text("doc", encoding="utf-8")

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    event = mark_document(paths, {"relative_path": "folder/doc.md", "status": "read"})

    assert event["status"] == "read"
    assert event["relative_path"] == "folder/doc.md"
    assert event["source_path"] == str(document.resolve())
    assert (state_dir / "reading_status.jsonl").exists()


def test_reading_ui_can_open_source_only_file_and_reject_outside_path(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    outside = tmp_path / "outside.md"
    document.write_text("doc", encoding="utf-8")
    outside.write_text("outside", encoding="utf-8")

    opened = []
    monkeypatch.setattr(reading_ui, "open_path", lambda path: opened.append(path))

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    payload = reading_ui.open_document(paths, {"relative_path": "doc.md"}, reveal=False)

    assert payload["ok"] is True
    assert opened == [document.resolve()]
    with pytest.raises(ValueError, match="Unknown source document"):
        reading_ui.open_document(paths, {"source_path": str(outside)}, reveal=False)


def test_row_matches_query_checks_path_kind_tags_and_note() -> None:
    row = {
        "relative_path": "foo/bar.pdf",
        "category": "Research",
        "document_kind": "ResearchReport",
        "topic_tags": ["Agent", "RAG"],
        "summary": "retrieval evaluation benchmark",
        "reason": "strong evidence chain",
        "note": "great for writing",
    }

    assert row_matches_query(row, "agent")
    assert row_matches_query(row, "researchreport")
    assert row_matches_query(row, "benchmark")
    assert row_matches_query(row, "evidence")
    assert row_matches_query(row, "writing")
    assert not row_matches_query(row, "frontend")


def test_reading_ui_sort_rows_by_public_suitability() -> None:
    rows = [
        {"relative_path": "a.md", "quality": 90, "public_writing_suitability": 20},
        {"relative_path": "b.md", "quality": 80, "public_writing_suitability": 90},
    ]

    sorted_rows = sort_rows(rows, "public_desc")

    assert [row["relative_path"] for row in sorted_rows] == ["b.md", "a.md"]


def test_reading_ui_sort_rows_by_path_desc() -> None:
    rows = [
        {"relative_path": "z.md", "source_path": "C:/Docs/AuthorA/z.md", "quality": 90},
        {"relative_path": "a.md", "source_path": "C:/Docs/AuthorB/a.md", "quality": 80},
    ]

    sorted_rows = sort_rows(rows, "path_desc")

    assert [row["relative_path"] for row in sorted_rows] == ["a.md", "z.md"]


def test_reading_ui_source_path_sort_prefers_full_source_path() -> None:
    rows = [
        {"relative_path": "z.md", "source_path": "C:/Docs/AuthorB/z.md"},
        {"relative_path": "a.md", "source_path": "C:/Docs/AuthorA/a.md"},
    ]

    sorted_rows = sort_rows(rows, "source_path_asc")

    assert [row["relative_path"] for row in sorted_rows] == ["a.md", "z.md"]


def test_build_analysis_command_includes_selected_flags(tmp_path: Path) -> None:
    command = build_analysis_command(
        {
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "output_language": "en",
            "embedding_endpoint": "http://localhost:11434/api/embeddings",
            "embedding_model": "nomic-embed-text",
            "concurrency": "3",
            "limit": "10",
            "plan_only": True,
            "ocr_enabled": True,
            "manifest_analysis": True,
            "document_summary": True,
            "mine_relationships": True,
            "relationship_use_text_citations": True,
            "relationship_use_embeddings": True,
        },
        tmp_path / "source",
        tmp_path / "output",
    )

    assert "--source-dir" in command
    assert "--output-root" in command
    assert "--llm-model" in command
    assert "local-model" in command
    assert "--output-language" in command
    assert "en" in command
    assert command[command.index("--embedding-endpoint") + 1] == "http://localhost:11434/api/embeddings"
    assert "--embedding-model" in command
    assert "nomic-embed-text" in command
    assert "--concurrency" in command
    assert "3" in command
    assert "--limit" in command
    assert "--plan-only" in command
    assert "--ocr" in command
    assert "--no-ocr" not in command
    assert "--manifest-analysis" in command
    assert "--skip-manifest-analysis" not in command
    assert "--document-summary" in command
    assert "--mine-relationships" in command
    assert "--relationship-use-text-citations" in command
    assert "--relationship-use-embeddings" in command

    disabled_command = build_analysis_command(
        {"ocr_enabled": False, "manifest_analysis": False},
        tmp_path / "source",
        tmp_path / "output",
    )
    assert "--no-ocr" in disabled_command
    assert "--skip-manifest-analysis" in disabled_command
    assert "--ocr" not in disabled_command
    assert "--manifest-analysis" not in disabled_command


def test_relationship_task_command_includes_embedding_options(tmp_path: Path) -> None:
    paths = ReadingPaths(
        source_dir=tmp_path / "source",
        output_root=tmp_path / "output",
    )

    command = relationship_task_command(
        "mine",
        {
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "embedding_endpoint": "http://localhost:11434/api/embeddings",
            "embedding_model": "nomic-embed-text",
            "concurrency": "3",
            "relationship_use_embeddings": True,
            "relationship_use_text_citations": True,
        },
        paths,
    )

    assert "--use-embeddings" in command
    assert command[command.index("--embedding-endpoint") + 1] == "http://localhost:11434/api/embeddings"
    assert "--embedding-model" in command
    assert "nomic-embed-text" in command
    assert "--concurrency" in command
    assert "3" in command
    assert "--use-text-citations" in command


def test_relationship_task_command_requires_embedding_model(tmp_path: Path) -> None:
    paths = ReadingPaths(
        source_dir=tmp_path / "source",
        output_root=tmp_path / "output",
    )

    with pytest.raises(ValueError, match="Embedding model is required"):
        relationship_task_command(
            "mine",
            {
                "llm_endpoint": "http://localhost:11434/api/generate",
                "llm_model": "local-model",
                "relationship_use_embeddings": True,
            },
            paths,
        )


def test_rag_task_command_includes_index_options(tmp_path: Path) -> None:
    paths = ReadingPaths(
        source_dir=tmp_path / "source",
        output_root=tmp_path / "output",
    )

    command = rag_task_command(
        {
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "embedding_endpoint": "http://localhost:11434/api/embeddings",
            "embedding_model": "nomic-embed-text",
            "rag_min_quality": "82",
            "rag_categories": "Architecture,Research",
            "rag_limit": "20",
            "rag_chunk_max_chars": "1200",
            "rag_chunk_overlap_chars": "160",
        },
        paths,
    )

    assert any(str(part).endswith("rag_indexer.py") for part in command)
    assert "build" in command
    assert "--source-dir" in command
    assert "--output-root" in command
    assert command[command.index("--embedding-endpoint") + 1] == "http://localhost:11434/api/embeddings"
    assert "--embedding-model" in command
    assert "nomic-embed-text" in command
    assert command[command.index("--min-quality") + 1] == "82"
    assert command[command.index("--categories") + 1] == "Architecture,Research"
    assert command[command.index("--limit") + 1] == "20"
    assert command[command.index("--chunk-max-chars") + 1] == "1200"
    assert command[command.index("--chunk-overlap-chars") + 1] == "160"
    assert "--no-embeddings" not in command

    text_only = rag_task_command(
        {"llm_endpoint": "http://localhost:11434/api/generate"},
        paths,
    )
    assert "--no-embeddings" in text_only


def test_rag_task_command_keeps_redaction_rules_out_of_cli_arguments(
    tmp_path: Path,
) -> None:
    paths = ReadingPaths(
        source_dir=tmp_path / "source",
        output_root=tmp_path / "output",
    )

    payload = {
        "llm_endpoint": "http://localhost:11434/api/generate",
        "rag_redaction_enabled": True,
        "rag_redact_terms": "Alice\nSecretProject",
        "rag_redact_mappings": "13800138000=>[PHONE]",
        "rag_redact_placeholder": "[MASKED]",
        "rag_redact_drop_matched_documents": True,
    }

    command = rag_task_command(payload, paths)

    assert "--redact-terms" not in command
    assert "--redact-mappings" not in command
    assert "--redact-placeholder" not in command
    assert "--redact-drop-matched-documents" not in command
    assert "Alice\nSecretProject" not in command
    assert "13800138000=>[PHONE]" not in command


def test_rag_redaction_env_only_sets_rules_when_enabled(tmp_path: Path) -> None:
    disabled_env = rag_redaction_env(
        {
            "rag_redaction_enabled": False,
            "rag_redact_terms": "Alice\nSecretProject",
            "rag_redact_mappings": "13800138000=>[PHONE]",
            "rag_redact_placeholder": "[MASKED]",
            "rag_redact_drop_matched_documents": True,
        }
    )
    assert disabled_env == {}

    enabled_env = rag_redaction_env(
        {
            "rag_redaction_enabled": True,
            "rag_redact_terms": "Alice\nSecretProject",
            "rag_redact_mappings": "13800138000=>[PHONE]",
            "rag_redact_placeholder": "[MASKED]",
            "rag_redact_drop_matched_documents": True,
        }
    )
    assert enabled_env["DOCTRIAGE_RAG_REDACT_TERMS"] == "Alice\nSecretProject"
    assert enabled_env["DOCTRIAGE_RAG_REDACT_MAPPINGS"] == "13800138000=>[PHONE]"
    assert enabled_env["DOCTRIAGE_RAG_REDACT_PLACEHOLDER"] == "[MASKED]"
    assert enabled_env["DOCTRIAGE_RAG_REDACT_DROP_MATCHED_DOCUMENTS"] == "1"


def test_rag_redaction_env_requires_rules_when_enabled() -> None:
    with pytest.raises(ValueError, match="no redaction rules"):
        rag_redaction_env(
            {
                "rag_redaction_enabled": True,
                "rag_redact_terms": "",
                "rag_redact_mappings": "",
            }
        )


def test_model_api_keys_are_passed_through_subprocess_env() -> None:
    payload = {
        "llm_api_key": "chat-key",
        "embedding_api_key": "embedding-key",
    }

    assert model_api_key_env(payload) == {
        "LLM_API_KEY": "chat-key",
        "EMBEDDING_API_KEY": "embedding-key",
    }
    process_env = subprocess_env_for_payload(payload)
    assert process_env["LLM_API_KEY"] == "chat-key"
    assert process_env["EMBEDDING_API_KEY"] == "embedding-key"
    assert process_env["PYTHONUTF8"] == "1"


def test_frontend_model_api_key_fields_are_payload_only() -> None:
    html = frontend_source()
    compact = frontend_source_compact()

    assert 'id="run_llm_api_key"' in html
    assert 'id="run_embedding_api_key"' in html
    assert 'const RUN_FORM_SECRET_FIELDS = [' in html
    assert '"run_llm_api_key"' in html
    assert '"run_embedding_api_key"' in html
    assert '"run_llm_api_key",' not in html.split("const RUN_FORM_VALUE_FIELDS = [", 1)[1].split("];", 1)[0]
    assert '"run_embedding_api_key",' not in html.split("const RUN_FORM_VALUE_FIELDS = [", 1)[1].split("];", 1)[0]
    assert 'llm_api_key: $("run_llm_api_key") ? $("run_llm_api_key").value.trim() : ""' in compact
    assert 'embedding_api_key: $("run_embedding_api_key") ? $("run_embedding_api_key").value.trim() : ""' in compact
    assert 'probePayload.llm_api_key = _requestPayload.llm_api_key' in compact


def test_llm_connection_checks_ollama_tags(monkeypatch) -> None:
    calls: list[str] = []

    def fake_http_json_request(url, **kwargs):
        calls.append(url)
        return {
            "reachable": True,
            "status_code": 200,
            "json": {"models": [{"name": "nomic-embed-text:latest"}]},
            "text": "",
            "error": "",
        }

    monkeypatch.setattr(reading_ui, "http_json_request", fake_http_json_request)

    found = reading_ui.test_llm_connection(
        {
            "endpoint": "http://localhost:11434/api/generate",
            "model": "nomic-embed-text",
        }
    )
    missing = reading_ui.test_llm_connection(
        {
            "endpoint": "http://localhost:11434/api/generate",
            "model": "missing-model",
        }
    )

    assert calls == [
        "http://localhost:11434/api/tags",
        "http://localhost:11434/api/tags",
    ]
    assert found["ok"] is True
    assert found["provider"] == "ollama"
    assert found["model_exists"] is True
    assert missing["ok"] is False
    assert missing["model_exists"] is False


def test_llm_connection_checks_openai_compatible_models_with_embedding_key(
    monkeypatch,
) -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    def fake_http_json_request(url, **kwargs):
        calls.append((url, kwargs.get("headers") or {}))
        return {
            "reachable": True,
            "status_code": 200,
            "json": {"data": [{"id": "text-embedding-3-small"}]},
            "text": "",
            "error": "",
        }

    monkeypatch.setenv("LLM_API_KEY", "chat-key")
    monkeypatch.setenv("EMBEDDING_API_KEY", "embedding-key")
    monkeypatch.setattr(reading_ui, "http_json_request", fake_http_json_request)

    payload = reading_ui.test_llm_connection(
        {
            "role": "embedding",
            "endpoint": "https://api.openai.com/v1/embeddings",
            "model": "text-embedding-3-small",
        }
    )

    assert payload["ok"] is True
    assert payload["provider"] == "openai-compatible"
    assert calls == [
        (
            "https://api.openai.com/v1/models",
            {"Authorization": "Bearer embedding-key"},
        )
    ]


def test_vector_store_connection_checks_local_rag_jsonl(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    rag_dir = output_root / "_rag"
    source_dir.mkdir()
    rag_dir.mkdir(parents=True)
    (rag_dir / "vectors.jsonl").write_text(
        '{"chunk_id":"a","embedding":[1]}\n{"chunk_id":"b","embedding":[2]}\n',
        encoding="utf-8",
    )

    payload = reading_ui.test_vector_store_connection(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root)),
        {
            "store_type": "local_jsonl",
            "source_dir": str(source_dir),
            "output_root": str(output_root),
        },
    )

    assert payload["ok"] is True
    assert payload["reachable"] is True
    assert payload["vectors_exists"] is True
    assert payload["vector_count"] == 2


def test_vector_store_connection_checks_qdrant_collection(monkeypatch) -> None:
    calls: list[str] = []

    def fake_http_json_request(url, **kwargs):
        calls.append(url)
        return {"reachable": True, "status_code": 200, "json": {}, "text": "", "error": ""}

    monkeypatch.setattr(reading_ui, "http_json_request", fake_http_json_request)

    payload = reading_ui.test_vector_store_connection(
        AppState(),
        {
            "store_type": "qdrant",
            "url": "http://localhost:6333/",
            "collection": "docs",
        },
    )

    assert calls == [
        "http://localhost:6333/collections",
        "http://localhost:6333/collections/docs",
    ]
    assert payload["ok"] is True
    assert payload["collection_checked"] is True
    assert payload["collection_exists"] is True


def test_build_analysis_command_requires_embedding_model_for_embedding_relationships(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Embedding model is required"):
        build_analysis_command(
            {
                "llm_endpoint": "http://localhost:11434/api/generate",
                "llm_model": "local-model",
                "mine_relationships": True,
                "relationship_use_embeddings": True,
            },
            tmp_path / "source",
            tmp_path / "output",
        )


def test_start_analysis_redirects_child_output_to_application_log(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    popen_call: dict[str, object] = {}

    class FakeProcess:
        pid = 12345

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        popen_call["stdout_name"] = kwargs["stdout"].name
        popen_call["stderr"] = kwargs["stderr"]
        popen_call["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_analysis(
        AppState(),
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
            "concurrency": "3",
        },
    )

    assert result["started"] is True
    assert popen_call["command"][0] == reading_ui.sys.executable
    assert popen_call["stdout_name"] == str(output_root / "_logs" / "doctriage.log")
    assert popen_call["stderr"] is reading_ui.subprocess.STDOUT
    env = popen_call["env"]
    assert isinstance(env, dict)
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert not (output_root / "_state" / "ui_runs.jsonl").exists()


def test_managed_process_options_create_process_group_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(reading_ui.os, "name", "posix")

    assert reading_ui.managed_process_popen_options() == {"start_new_session": True}


def test_http_server_uses_daemon_request_threads() -> None:
    assert reading_ui.DocTriageHTTPServer.daemon_threads is True
    assert reading_ui.DocTriageHTTPServer.block_on_close is False


def test_frontend_assets_are_split_from_python_html() -> None:
    css = reading_ui.read_ui_asset_text("app.css")

    assert '<link rel="stylesheet" href="/assets/app.css" />' in reading_ui.HTML_PAGE
    assert '<script src="/assets/app.js"></script>' in reading_ui.HTML_PAGE
    assert "<style>" not in reading_ui.HTML_PAGE
    assert "<script>" not in reading_ui.HTML_PAGE
    assert "header {\n  padding: 16px 20px 0;" in css
    assert "function switchTab" in reading_ui.read_ui_asset_text("app.js")


def test_terminate_process_tree_kills_process_group_off_windows(monkeypatch) -> None:
    calls: list[tuple[int, int]] = []

    class FakeProcess:
        pid = 24680

        def __init__(self):
            self.stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def wait(self, timeout=None):
            return 0

    process = FakeProcess()

    def fake_killpg(pid, sig):
        calls.append((pid, sig))
        process.stopped = True

    monkeypatch.setattr(reading_ui.os, "name", "posix")
    monkeypatch.setattr(reading_ui.os, "killpg", fake_killpg, raising=False)

    assert reading_ui.terminate_process_tree(process) is True
    assert calls == [(24680, reading_ui.signal.SIGTERM)]


def test_start_relationship_task_uses_graph_output_without_mutating_active_paths(
    tmp_path: Path, monkeypatch
) -> None:
    analysis_source = tmp_path / "analysis-source"
    analysis_output = tmp_path / "analysis-output"
    graph_source = tmp_path / "graph-source"
    graph_output = tmp_path / "graph-output"
    document = graph_source / "nested" / "doc.md"
    analysis_source.mkdir()
    analysis_output.mkdir()
    document.parent.mkdir(parents=True)
    (graph_output / "_state").mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (graph_output / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "nested/doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    app_state = AppState(
        paths=ReadingPaths(source_dir=analysis_source, output_root=analysis_output)
    )
    popen_call: dict[str, object] = {}

    class FakeProcess:
        pid = 24601

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        popen_call["stdout_name"] = kwargs["stdout"].name
        popen_call["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_relationship_task(
        app_state,
        {
            "output_root": str(graph_output),
            "llm_endpoint": "http://localhost:11434/api/generate",
        },
        "mine",
    )

    command = popen_call["command"]
    assert result["started"] is True
    assert command[command.index("--source-dir") + 1] == str(graph_source.resolve())
    assert command[command.index("--output-root") + 1] == str(graph_output.resolve())
    assert popen_call["stdout_name"] == str(graph_output / "_logs" / "doctriage.log")
    assert not reading_ui.relationship_task_record_path(
        ReadingPaths(source_dir=graph_source, output_root=graph_output)
    ).exists()
    assert app_state.paths is not None
    assert app_state.paths.source_dir == analysis_source
    assert app_state.paths.output_root == analysis_output


def test_start_relationship_task_allows_different_output_while_other_relationship_runs(
    tmp_path: Path, monkeypatch
) -> None:
    source_a = tmp_path / "source-a"
    output_a = tmp_path / "output-a"
    source_b = tmp_path / "source-b"
    output_b = tmp_path / "output-b"
    document = source_b / "doc.md"
    source_a.mkdir()
    output_a.mkdir()
    source_b.mkdir()
    (output_b / "_state").mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (output_b / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    class RunningRelationshipProcess:
        pid = 111

        def poll(self):
            return None

    class NewRelationshipProcess:
        pid = 222

        def poll(self):
            return None

    popen_call: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        return NewRelationshipProcess()

    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_relationship_task(
        AppState(
            paths=ReadingPaths(source_dir=source_a, output_root=output_a),
            relationship_process=RunningRelationshipProcess(),
            relationship_process_kind="mine",
            relationship_process_command=[
                "python",
                "relationship_miner.py",
                "--source-dir",
                str(source_a.resolve()),
                "--output-root",
                str(output_a.resolve()),
            ],
        ),
        {
            "source_dir": str(source_b),
            "output_root": str(output_b),
            "llm_endpoint": "http://localhost:11434/api/generate",
        },
        "mine",
    )

    command = popen_call["command"]
    assert result["pid"] == 222
    assert command[command.index("--source-dir") + 1] == str(source_b.resolve())
    assert command[command.index("--output-root") + 1] == str(output_b.resolve())


def test_start_rag_task_uses_rag_output_without_mutating_active_paths(
    tmp_path: Path, monkeypatch
) -> None:
    analysis_source = tmp_path / "analysis-source"
    analysis_output = tmp_path / "analysis-output"
    rag_source = tmp_path / "rag-source"
    rag_output = tmp_path / "rag-output"
    document = rag_source / "nested" / "doc.md"
    analysis_source.mkdir()
    analysis_output.mkdir()
    document.parent.mkdir(parents=True)
    (rag_output / "_state").mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (rag_output / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "nested/doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    app_state = AppState(
        paths=ReadingPaths(source_dir=analysis_source, output_root=analysis_output)
    )
    popen_call: dict[str, object] = {}

    class FakeProcess:
        pid = 24691

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        popen_call["stdout_name"] = kwargs["stdout"].name
        popen_call["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_rag_task(
        app_state,
        {
            "output_root": str(rag_output),
            "llm_endpoint": "http://localhost:11434/api/generate",
            "embedding_model": "nomic-embed-text",
            "rag_min_quality": "80",
        },
    )

    command = popen_call["command"]
    assert result["started"] is True
    assert result["pid"] == 24691
    assert command[command.index("--source-dir") + 1] == str(rag_source.resolve())
    assert command[command.index("--output-root") + 1] == str(rag_output.resolve())
    assert popen_call["stdout_name"] == str(rag_output / "_rag" / "rag.log")
    assert "DOCTRIAGE_RAG_REDACT_TERMS" not in popen_call["env"]
    assert app_state.paths is not None
    assert app_state.paths.source_dir == analysis_source
    assert app_state.paths.output_root == analysis_output


def test_start_rag_task_passes_redaction_rules_via_environment_only(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    document = source_dir / "doc.md"
    document.parent.mkdir(parents=True)
    (output_root / "_state").mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    popen_call: dict[str, object] = {}

    class FakeProcess:
        pid = 13579

        def poll(self):
            return None

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        popen_call["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_rag_task(
        AppState(),
        {
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
            "rag_redaction_enabled": True,
            "rag_redact_terms": "Alice\nSecretProject",
            "rag_redact_mappings": "13800138000=>[PHONE]",
            "rag_redact_placeholder": "[MASKED]",
            "rag_redact_drop_matched_documents": True,
        },
    )

    command = popen_call["command"]
    env = popen_call["env"]
    assert result["started"] is True
    assert result["command"] == command
    assert "--redact-terms" not in command
    assert "--redact-mappings" not in command
    assert "--redact-placeholder" not in command
    assert "Alice\nSecretProject" not in command
    assert "13800138000=>[PHONE]" not in command
    assert env["DOCTRIAGE_RAG_REDACT_TERMS"] == "Alice\nSecretProject"
    assert env["DOCTRIAGE_RAG_REDACT_MAPPINGS"] == "13800138000=>[PHONE]"
    assert env["DOCTRIAGE_RAG_REDACT_PLACEHOLDER"] == "[MASKED]"
    assert env["DOCTRIAGE_RAG_REDACT_DROP_MATCHED_DOCUMENTS"] == "1"


def test_stop_rag_task_preserves_resume_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    rag_dir = output_root / "_rag"
    source_dir.mkdir()
    rag_dir.mkdir(parents=True)
    vectors_path = rag_dir / "vectors.jsonl"
    progress_path = rag_dir / "progress.json"
    vectors_path.write_text('{"chunk_id":"cached","embedding":[1.0]}\n', encoding="utf-8")
    progress_path.write_text(
        json.dumps({"phase": "embedding", "generated_vectors": 1}, ensure_ascii=False),
        encoding="utf-8",
    )

    class FakeRagProcess:
        pid = 86430

        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

    process = FakeRagProcess()
    payload = stop_rag_task(
        AppState(
            paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
            rag_process=process,
            rag_process_kind="build",
            rag_process_command=[
                "python",
                "rag_indexer.py",
                "build",
                "--source-dir",
                str(source_dir.resolve()),
                "--output-root",
                str(output_root.resolve()),
                "--embedding-model",
                "nomic-embed-text",
            ],
        ),
        {"source_dir": str(source_dir), "output_root": str(output_root)},
    )

    assert process.terminated is True
    assert payload == {"stopped": True, "running": False, "pid": 86430, "kind": "build"}
    assert vectors_path.exists()
    assert progress_path.exists()


def test_tasks_are_targeted_by_output_directory(tmp_path: Path) -> None:
    source_a = tmp_path / "source-a"
    source_b = tmp_path / "source-b"
    output_a = tmp_path / "output-a"
    output_b = tmp_path / "output-b"
    source_a.mkdir()
    source_b.mkdir()

    class FakeProcess:
        def __init__(self, pid: int):
            self.pid = pid
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

    process_a = FakeProcess(11111)
    process_b = FakeProcess(22222)
    state = AppState(
        paths=ReadingPaths(source_dir=source_a, output_root=output_a),
        analysis_tasks={
            reading_ui.task_key_for_output_root(output_a): reading_ui.ManagedProcessTask(
                process=process_a,
                command=[
                    "python",
                    "main.py",
                    "--source-dir",
                    str(source_a.resolve()),
                    "--output-root",
                    str(output_a.resolve()),
                ],
            ),
            reading_ui.task_key_for_output_root(output_b): reading_ui.ManagedProcessTask(
                process=process_b,
                command=[
                    "python",
                    "main.py",
                    "--source-dir",
                    str(source_b.resolve()),
                    "--output-root",
                    str(output_b.resolve()),
                ],
            ),
        },
    )

    payload_b = analysis_status(
        state,
        paths=ReadingPaths(source_dir=source_b, output_root=output_b),
    )
    stopped_b = stop_analysis(
        state,
        {"source_dir": str(source_b), "output_root": str(output_b)},
    )

    assert payload_b["pid"] == 22222
    assert stopped_b == {"stopped": True, "running": False, "pid": 22222}
    assert process_b.terminated is True
    assert process_a.terminated is False
    assert analysis_status(
        state,
        paths=ReadingPaths(source_dir=source_a, output_root=output_a),
    )["pid"] == 11111


def test_build_rag_payload_reads_dedicated_rag_log(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    source_dir.mkdir()
    paths.log_dir.mkdir(parents=True)
    rag_log_path(paths).parent.mkdir(parents=True)
    paths.application_log_path.write_text("analysis log line\n", encoding="utf-8")
    rag_log_path(paths).write_text("rag log line\n", encoding="utf-8")

    payload = build_rag_payload(AppState(), paths)

    assert payload["log_tail"].strip() == "rag log line"
    assert "analysis log line" not in payload["log_tail"]


def test_start_analysis_does_not_preempt_relationship_task_for_other_output(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    relationship_output = tmp_path / "relationship-output"
    source_dir.mkdir()
    output_root.mkdir()
    relationship_output.mkdir()

    class FakeRelationshipProcess:
        pid = 24680

        def __init__(self):
            self.running = True
            self.terminated = False

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            self.terminated = True
            self.running = False

        def wait(self, timeout=None):
            self.running = False
            return 0

    class FakeAnalysisProcess:
        pid = 24681

        def poll(self):
            return None

    popen_call: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        popen_call["stdout_name"] = kwargs["stdout"].name
        return FakeAnalysisProcess()

    relationship_process = FakeRelationshipProcess()
    app_state = AppState(
        paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
        relationship_process=relationship_process,
        relationship_process_kind="mine",
        relationship_process_command=[
            "python",
            "relationship_miner.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(relationship_output.resolve()),
            "--embedding-model",
            "nomic-embed-text",
        ],
    )
    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_analysis(
        app_state,
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "preempt_relationships": True,
        },
    )

    command = popen_call["command"]
    assert relationship_process.terminated is False
    assert result["started"] is True
    assert result["pid"] == 24681
    assert result["relationship_stop"] is None
    assert "--embedding-model" not in command
    assert popen_call["stdout_name"] == str(output_root / "_logs" / "doctriage.log")


def test_start_analysis_preempts_running_relationship_task_for_same_output(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    output_root.mkdir()

    class FakeRelationshipProcess:
        pid = 24680

        def __init__(self):
            self.running = True
            self.terminated = False

        def poll(self):
            return None if self.running else 0

        def terminate(self):
            self.terminated = True
            self.running = False

        def wait(self, timeout=None):
            self.running = False
            return 0

    class FakeAnalysisProcess:
        pid = 24681

        def poll(self):
            return None

    popen_call: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        popen_call["stdout_name"] = kwargs["stdout"].name
        return FakeAnalysisProcess()

    relationship_process = FakeRelationshipProcess()
    app_state = AppState(
        paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
        relationship_process=relationship_process,
        relationship_process_kind="mine",
        relationship_process_command=[
            "python",
            "relationship_miner.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(output_root.resolve()),
            "--embedding-model",
            "nomic-embed-text",
        ],
    )
    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_analysis(
        app_state,
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "preempt_relationships": True,
        },
    )

    command = popen_call["command"]
    assert relationship_process.terminated is True
    assert result["started"] is True
    assert result["pid"] == 24681
    assert result["relationship_stop"] == {
        "stopped": True,
        "running": False,
        "pid": 24680,
        "kind": "mine",
    }
    assert command[command.index("--embedding-model") + 1] == "nomic-embed-text"
    assert popen_call["stdout_name"] == str(output_root / "_logs" / "doctriage.log")


def test_start_analysis_rejects_existing_locked_run(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    run_lock_path(output_root).parent.mkdir(parents=True)
    run_lock_path(output_root).write_text(
        json.dumps({"pid": 43210}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 43210)
    monkeypatch.setattr(
        reading_ui.subprocess,
        "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("should not spawn")),
    )

    with pytest.raises(RuntimeError, match="PID 43210"):
        start_analysis(
            AppState(),
            {
                "source_dir": str(source_dir),
                "output_root": str(output_root),
                "llm_endpoint": "http://localhost:11434/api/generate",
            },
        )


def test_analysis_status_reports_running_from_run_lock(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    run_lock_path(output_root).parent.mkdir(parents=True)
    run_lock_path(output_root).write_text(
        json.dumps({"pid": 24680}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 24680)

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["running"] is True
    assert payload["pid"] == 24680
    assert payload["command"] is None


def test_analysis_status_reports_inline_relationship_task_during_auto_mining(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    (state_dir / "progress.json").write_text(
        json.dumps({"completed": 1, "total": 1, "remaining": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        "2026-06-13 12:00:00,000 [INFO] doctriage - Run summary: {}\n"
        "2026-06-13 12:00:01,000 [INFO] doctriage - Starting relationship mining\n",
        encoding="utf-8",
    )
    (relationship_dir / "embedding_progress.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "phase": "embedding",
                "total": 10,
                "completed": 3,
                "percent": 30,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeProcess:
        pid = 13579

        def poll(self):
            return None

    command = [
        "python",
        "main.py",
        "--source-dir",
        str(source_dir.resolve()),
        "--output-root",
        str(output_root.resolve()),
        "--mine-relationships",
        "--relationship-use-embeddings",
    ]

    payload = analysis_status(
        AppState(
            paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
            process=FakeProcess(),
            process_command=command,
        )
    )

    task = payload["relationship_task"]
    assert payload["phase"] == "关系挖掘中"
    assert task["running"] is True
    assert task["inline"] is True
    assert task["pid"] == 13579
    assert task["kind"] == "mine"
    assert "--relationship-use-embeddings" in task["command"]
    assert "--use-embeddings" in task["command"]


def test_analysis_status_reports_inline_relationship_task_from_run_lock(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    log_dir = output_root / "_logs"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    log_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    run_lock_path(output_root).parent.mkdir(parents=True, exist_ok=True)
    run_lock_path(output_root).write_text(
        json.dumps({"pid": 24680}, ensure_ascii=False),
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        "2026-06-13 12:00:01,000 [INFO] doctriage - Starting relationship mining\n",
        encoding="utf-8",
    )
    (relationship_dir / "embedding_progress.json").write_text(
        json.dumps({"enabled": True, "phase": "embedding"}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 24680)

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    task = payload["relationship_task"]
    assert payload["running"] is True
    assert task["running"] is True
    assert task["inline"] is True
    assert task["pid"] == 24680
    assert task["command"] == ["--use-embeddings"]


def test_analysis_status_keeps_inline_relationship_when_embedding_logs_displace_start_marker(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    (state_dir / "progress.json").write_text(
        json.dumps({"completed": 25, "total": 25, "remaining": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        "".join(
            "2026-06-13 16:20:22,079 [INFO] httpx - HTTP Request: POST "
            'http://localhost:11434/api/embeddings "HTTP/1.1 200 OK"\n'
            for _ in range(100)
        ),
        encoding="utf-8",
    )
    (relationship_dir / "embedding_progress.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "phase": "embedding",
                "total": 100,
                "completed": 42,
                "percent": 42,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_lock_path(output_root).parent.mkdir(parents=True, exist_ok=True)
    run_lock_path(output_root).write_text(
        json.dumps({"pid": 24680}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 24680)

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    task = payload["relationship_task"]
    assert payload["running"] is True
    assert payload["phase"] == "关系挖掘中"
    assert task["running"] is True
    assert task["inline"] is True
    assert task["pid"] == 24680
    assert task["command"] == ["--use-embeddings"]


def test_analysis_status_exits_relationship_phase_after_outputs_are_written(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    (state_dir / "progress.json").write_text(
        json.dumps({"completed": 25, "total": 25, "remaining": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (state_dir / "decisions.jsonl").write_text(
        json.dumps({"source_path": str(source_dir / "a.md"), "status": "planned"})
        + "\n",
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        "2026-06-13 16:00:00,000 [INFO] doctriage - Starting relationship mining\n",
        encoding="utf-8",
    )
    (relationship_dir / "embedding_progress.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "phase": "complete",
                "total": 100,
                "completed": 100,
                "percent": 100,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    reading_ui.relationship_relations_path(
        ReadingPaths(source_dir=source_dir, output_root=output_root)
    ).write_text("", encoding="utf-8")
    reading_ui.relationship_clusters_path(
        ReadingPaths(source_dir=source_dir, output_root=output_root)
    ).write_text(json.dumps({"clusters": []}), encoding="utf-8")

    class FakeProcess:
        pid = 13579

        def poll(self):
            return None

    monkeypatch.setattr(reading_ui.time, "time", lambda: 1000.0)
    app_state = AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    reading_ui.register_analysis_task(
        app_state,
        ReadingPaths(source_dir=source_dir, output_root=output_root),
        FakeProcess(),
        [
            "python",
            "main.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(output_root.resolve()),
            "--mine-relationships",
            "--relationship-use-embeddings",
        ],
        1000.0,
    )

    payload = analysis_status(app_state)

    assert payload["running"] is False
    assert payload["phase"] == "分析完成，关系已生成"
    assert payload["pid"] is None
    assert payload["relationship_task"]["running"] is False


def test_analysis_status_ignores_stale_embedding_progress_after_relationship_process_killed(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    (state_dir / "progress.json").write_text(
        json.dumps(
            {
                "completed": 25,
                "total": 50,
                "remaining": 25,
                "skipped_resumed": 25,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (state_dir / "decisions.jsonl").write_text(
        json.dumps({"source_path": str(source_dir / "a.md"), "status": "planned"})
        + "\n",
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        "2026-06-13 16:00:00,000 [INFO] doctriage - Starting relationship mining\n"
        "2026-06-13 16:20:22,079 [INFO] httpx - HTTP Request: POST "
        'http://localhost:11434/api/embeddings "HTTP/1.1 200 OK"\n',
        encoding="utf-8",
    )
    (relationship_dir / "embedding_progress.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "phase": "embedding",
                "total": 100,
                "completed": 42,
                "updated_epoch": 1000.0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    run_lock_path(output_root).parent.mkdir(parents=True, exist_ok=True)
    run_lock_path(output_root).write_text(
        json.dumps({"pid": 24680, "created_epoch": 9_999_999_999.0}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 24680)

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    task = payload["relationship_task"]
    assert payload["running"] is True
    assert payload["phase"] == "续传跳过中"
    assert task["running"] is False
    assert "inline" not in task


def test_ui_process_probe_handles_non_utf8_tasklist_output(monkeypatch) -> None:
    class FakeCompletedProcess:
        stdout = b"\xd0\xce\xcf\xb5,999999\r\n"

    monkeypatch.setattr(reading_ui.os, "name", "nt")
    monkeypatch.setattr(
        reading_ui.subprocess,
        "run",
        lambda *args, **kwargs: FakeCompletedProcess(),
    )

    assert reading_ui.is_process_alive(24680) is False


def test_ui_process_probe_handles_missing_stdout(monkeypatch) -> None:
    class FakeCompletedProcess:
        stdout = None

    monkeypatch.setattr(reading_ui.os, "name", "nt")
    monkeypatch.setattr(
        reading_ui.subprocess,
        "run",
        lambda *args, **kwargs: FakeCompletedProcess(),
    )

    assert reading_ui.is_process_alive(24680) is False


def test_stop_analysis_waits_for_ui_child_process_to_exit(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()

    class FakeProcess:
        pid = 97531

        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

    process = FakeProcess()
    payload = stop_analysis(
        AppState(
            paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
            process=process,
            process_command=[
                "python",
                "main.py",
                "--source-dir",
                str(source_dir.resolve()),
                "--output-root",
                str(output_root.resolve()),
            ],
        )
    )

    assert process.terminated is True
    assert payload == {"stopped": True, "running": False, "pid": 97531}


def test_start_early_relationships_stops_analysis_and_starts_title_relationship_mining(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    document = source_dir / "doc.md"
    source_dir.mkdir()
    document.write_text("doc", encoding="utf-8")
    (output_root / "_state").mkdir(parents=True)
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeAnalysisProcess:
        pid = 13524

        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

    class FakeRelationshipProcess:
        def __init__(self, pid: int):
            self.pid = pid
            self.running = True

        def poll(self):
            return None if self.running else 0

    popen_calls: list[dict[str, object]] = []

    def fake_popen(command, **kwargs):
        process = FakeRelationshipProcess(24679 + len(popen_calls) + 1)
        popen_calls.append(
            {
                "command": command,
                "stdout_name": kwargs["stdout"].name,
                "process": process,
            }
        )
        return process

    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    analysis_process = FakeAnalysisProcess()
    app_state = AppState(
        paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
        process=analysis_process,
        process_command=[
            "python",
            "main.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(output_root.resolve()),
        ],
    )

    result = start_early_relationships(
        app_state,
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "mine_relationships": False,
            "relationship_use_text_citations": False,
            "relationship_use_embeddings": False,
        },
    )

    relationship_call = popen_calls[0]
    command = relationship_call["command"]
    assert analysis_process.terminated is True
    assert result["started"] is True
    assert result["stop"] == {"stopped": True, "running": False, "pid": 13524}
    assert result["relationship"]["pid"] == 24680
    assert app_state.relationship_process_kind == "mine"
    assert any(str(part).endswith("relationship_miner.py") for part in command)
    assert "--use-text-citations" in command
    assert "--use-embeddings" not in command
    assert command[command.index("--llm-model") + 1] == "local-model"
    assert relationship_call["stdout_name"] == str(output_root / "_logs" / "doctriage.log")

    with pytest.raises(RuntimeError, match="relationship task"):
        start_analysis(
            app_state,
            {
                "source_dir": str(source_dir),
                "output_root": str(output_root),
                "llm_endpoint": "http://localhost:11434/api/generate",
            },
        )

    relationship_call["process"].running = False
    resume_result = start_analysis(
        app_state,
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
        },
    )
    resume_command = popen_calls[1]["command"]

    assert resume_result["started"] is True
    assert resume_result["pid"] == 24681
    assert "--force-reprocess" not in resume_command
    assert (output_root / "_state" / "decisions.jsonl").exists()


def test_start_early_relationships_uses_embedding_when_selected(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    document = source_dir / "doc.md"
    source_dir.mkdir()
    document.write_text("doc", encoding="utf-8")
    (output_root / "_state").mkdir(parents=True)
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    class FakeRelationshipProcess:
        pid = 24680

        def poll(self):
            return None

    popen_call: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        popen_call["command"] = command
        popen_call["stdout_name"] = kwargs["stdout"].name
        return FakeRelationshipProcess()

    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)

    result = start_early_relationships(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root)),
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "embedding_model": "nomic-embed-text",
            "relationship_use_embeddings": True,
            "relationship_use_text_citations": False,
        },
    )

    command = popen_call["command"]
    assert result["started"] is True
    assert "--use-text-citations" in command
    assert "--use-embeddings" in command
    assert command[command.index("--embedding-model") + 1] == "nomic-embed-text"


def test_start_early_relationships_validates_embedding_model_before_stopping_analysis(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    document = source_dir / "doc.md"
    source_dir.mkdir()
    document.write_text("doc", encoding="utf-8")
    (output_root / "_state").mkdir(parents=True)
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps({"source_path": str(document), "relative_path": "doc.md"}),
        encoding="utf-8",
    )

    class FakeAnalysisProcess:
        pid = 13524

        def __init__(self):
            self.terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

    process = FakeAnalysisProcess()
    app_state = AppState(
        paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
        process=process,
        process_command=[
            "python",
            "main.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(output_root.resolve()),
        ],
    )

    with pytest.raises(ValueError, match="Embedding model is required"):
        start_early_relationships(
            app_state,
            {
                "source_dir": str(source_dir),
                "output_root": str(output_root),
                "llm_endpoint": "http://localhost:11434/api/generate",
                "llm_model": "local-model",
                "relationship_use_embeddings": True,
            },
        )

    assert process.terminated is False


def test_stop_relationship_task_preserves_embedding_resume_outputs(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    relationship_dir.mkdir(parents=True)
    cache_path = relationship_dir / "embedding_cache.jsonl"
    progress_path = relationship_dir / "embedding_progress.json"
    cache_path.write_text('{"key":"cached","embedding":[1.0]}\n', encoding="utf-8")
    progress_path.write_text(
        json.dumps({"enabled": True, "phase": "embedding", "generated": 1}),
        encoding="utf-8",
    )

    class FakeRelationshipProcess:
        pid = 86420

        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

    process = FakeRelationshipProcess()
    payload = stop_relationship_task(
        AppState(
            paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
            relationship_process=process,
            relationship_process_kind="mine",
            relationship_process_command=[
                "python",
                "relationship_miner.py",
                "--source-dir",
                str(source_dir.resolve()),
                "--output-root",
                str(output_root.resolve()),
                "--use-embeddings",
            ],
        ),
        {"source_dir": str(source_dir), "output_root": str(output_root)},
    )

    assert process.terminated is True
    assert payload == {"stopped": True, "running": False, "pid": 86420, "kind": "mine"}
    assert cache_path.exists()
    assert progress_path.exists()


def test_relationship_task_status_includes_target_paths(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()

    class FakeRelationshipProcess:
        pid = 86421

        def poll(self):
            return None

    payload = reading_ui.relationship_task_status(
        AppState(
            paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
            relationship_process=FakeRelationshipProcess(),
            relationship_process_kind="mine",
            relationship_process_command=[
                "python",
                "relationship_miner.py",
                "--source-dir",
                str(source_dir.resolve()),
                "--output-root",
                str(output_root.resolve()),
            ],
        ),
        ReadingPaths(source_dir=source_dir, output_root=output_root),
    )

    assert payload["running"] is True
    assert payload["pid"] == 86421
    assert payload["source_dir"] == str(source_dir)
    assert payload["output_root"] == str(output_root)


def test_relationship_task_status_exits_running_when_outputs_are_written(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    source_dir.mkdir()
    reading_ui.relationship_dir(paths).mkdir(parents=True)
    reading_ui.relationship_relations_path(paths).write_text("", encoding="utf-8")
    reading_ui.relationship_clusters_path(paths).write_text(
        json.dumps({"clusters": []}), encoding="utf-8"
    )

    class FakeRelationshipProcess:
        pid = 86422

        def poll(self):
            return None

    monkeypatch.setattr(reading_ui.time, "time", lambda: 1000.0)
    app_state = AppState(paths=paths)
    reading_ui.register_relationship_task(
        app_state,
        paths,
        FakeRelationshipProcess(),
        [
            "python",
            "relationship_miner.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(output_root.resolve()),
        ],
        "mine",
    )

    payload = reading_ui.relationship_task_status(app_state, paths)

    assert payload["running"] is False
    assert payload["pid"] is None
    assert payload["return_code"] == 0


def test_start_relationship_task_reaps_completed_process_before_restart(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    source_dir.mkdir()
    reading_ui.relationship_dir(paths).mkdir(parents=True)
    reading_ui.relationship_relations_path(paths).write_text("", encoding="utf-8")
    reading_ui.relationship_clusters_path(paths).write_text(
        json.dumps({"clusters": []}), encoding="utf-8"
    )
    (output_root / "_state").mkdir(parents=True)
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(source_dir / "doc.md"),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    class CompletedButAliveProcess:
        pid = 86424

        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def wait(self, timeout=None):
            if self.terminated:
                return 0
            raise subprocess.TimeoutExpired(cmd="relationship", timeout=timeout)

    class NewRelationshipProcess:
        pid = 86425

        def poll(self):
            return None

    old_process = CompletedButAliveProcess()
    popen_calls: list[list[str]] = []

    def fake_terminate_process_tree(target, timeout_seconds=5.0):
        assert target is old_process
        old_process.terminated = True
        return True

    def fake_popen(command, **kwargs):
        popen_calls.append(command)
        return NewRelationshipProcess()

    monkeypatch.setattr(reading_ui.time, "time", lambda: 1000.0)
    monkeypatch.setattr(reading_ui, "terminate_process_tree", fake_terminate_process_tree)
    monkeypatch.setattr(reading_ui.subprocess, "Popen", fake_popen)
    app_state = AppState(paths=paths)
    reading_ui.register_relationship_task(
        app_state,
        paths,
        old_process,
        [
            "python",
            "relationship_miner.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(output_root.resolve()),
        ],
        "mine",
    )

    result = reading_ui.start_relationship_task(
        app_state,
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
        },
        "mine",
    )

    assert old_process.terminated is True
    assert result["pid"] == 86425
    assert len(popen_calls) == 1


def test_completed_relationship_task_reaper_terminates_stuck_process(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    source_dir.mkdir()
    reading_ui.relationship_dir(paths).mkdir(parents=True)
    reading_ui.relationship_relations_path(paths).write_text("", encoding="utf-8")
    reading_ui.relationship_clusters_path(paths).write_text(
        json.dumps({"clusters": []}), encoding="utf-8"
    )

    class StuckRelationshipProcess:
        pid = 86423

        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd="relationship", timeout=timeout)

    process = StuckRelationshipProcess()
    monkeypatch.setattr(reading_ui.time, "time", lambda: 1000.0)
    monkeypatch.setattr(reading_ui, "COMPLETED_TASK_PROCESS_GRACE_SECONDS", 0.01)

    def fake_terminate_process_tree(target, timeout_seconds=5.0):
        assert target is process
        process.terminated = True
        return True

    monkeypatch.setattr(reading_ui, "terminate_process_tree", fake_terminate_process_tree)
    app_state = AppState(paths=paths)
    reading_ui.register_relationship_task(
        app_state,
        paths,
        process,
        [
            "python",
            "relationship_miner.py",
            "--source-dir",
            str(source_dir.resolve()),
            "--output-root",
            str(output_root.resolve()),
        ],
        "mine",
    )

    payload = reading_ui.relationship_task_status(app_state, paths)
    for _ in range(100):
        if (
            process.terminated
            and reading_ui.relationship_task_for_paths(app_state, paths) is None
        ):
            break
        time.sleep(0.01)

    assert payload["running"] is False
    assert process.terminated is True
    assert reading_ui.relationship_task_for_paths(app_state, paths) is None


def test_stop_relationship_task_stops_inline_auto_relationship_mining(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    log_dir = output_root / "_logs"
    source_dir.mkdir()
    log_dir.mkdir(parents=True)
    (log_dir / "doctriage.log").write_text(
        "2026-06-13 12:00:01,000 [INFO] doctriage - Starting relationship mining\n",
        encoding="utf-8",
    )

    class FakeAnalysisProcess:
        pid = 97531

        def __init__(self):
            self.terminated = False

        def poll(self):
            return 0 if self.terminated else None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            self.terminated = True
            return 0

    process = FakeAnalysisProcess()
    payload = stop_relationship_task(
        AppState(
            paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
            process=process,
            process_command=[
                "python",
                "main.py",
                "--source-dir",
                str(source_dir.resolve()),
                "--output-root",
                str(output_root.resolve()),
                "--mine-relationships",
            ],
        ),
        {"source_dir": str(source_dir), "output_root": str(output_root)},
    )

    assert process.terminated is True
    assert payload == {
        "stopped": True,
        "running": False,
        "pid": 97531,
        "kind": "mine",
        "inline": True,
    }


def test_stop_relationship_task_targets_external_relationship_record(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    reading_ui.relationship_dir(paths).mkdir(parents=True)
    reading_ui.relationship_task_record_path(paths).write_text(
        json.dumps(
            {
                "pid": 24680,
                "kind": "mine",
                "command": [
                    "python",
                    "relationship_miner.py",
                    "--source-dir",
                    str(source_dir.resolve()),
                    "--output-root",
                    str(output_root.resolve()),
                    "--use-embeddings",
                ],
                "source_dir": str(source_dir.resolve()),
                "output_root": str(output_root.resolve()),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    state = {"alive": True, "terminated": False}

    def fake_is_process_alive(pid: int) -> bool:
        return pid == 24680 and state["alive"]

    def fake_terminate(pid: int) -> bool:
        if pid == 24680:
            state["alive"] = False
            state["terminated"] = True
            return True
        return False

    monkeypatch.setattr(reading_ui, "is_process_alive", fake_is_process_alive)
    monkeypatch.setattr(reading_ui, "terminate_process_id", fake_terminate)

    status = reading_ui.relationship_task_status(AppState(), paths)
    payload = stop_relationship_task(
        AppState(),
        {"source_dir": str(source_dir), "output_root": str(output_root)},
    )

    assert status["running"] is True
    assert status["pid"] == 24680
    assert "--use-embeddings" in status["command"]
    assert state["terminated"] is True
    assert payload == {"stopped": True, "running": False, "pid": 24680, "kind": "mine"}
    assert not reading_ui.relationship_task_record_path(paths).exists()
    assert reading_ui.relationship_task_status(AppState(), paths)["running"] is False


def test_stop_relationship_task_keeps_external_record_when_process_survives(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    source_dir.mkdir()
    reading_ui.relationship_dir(paths).mkdir(parents=True)
    record_path = reading_ui.relationship_task_record_path(paths)
    record_path.write_text(
        json.dumps(
            {
                "pid": 24681,
                "kind": "mine",
                "source_dir": str(source_dir),
                "output_root": str(output_root),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 24681)
    monkeypatch.setattr(reading_ui, "terminate_process_id", lambda pid: False)

    payload = stop_relationship_task(
        AppState(paths=paths),
        {"source_dir": str(source_dir), "output_root": str(output_root)},
    )

    assert payload == {"stopped": False, "running": True, "pid": 24681, "kind": "mine"}
    assert record_path.exists()


def test_start_relationship_task_rejects_active_relationship_record_for_same_output(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    document = source_dir / "doc.md"
    source_dir.mkdir()
    document.write_text("doc", encoding="utf-8")
    (output_root / "_state").mkdir(parents=True)
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    reading_ui.relationship_dir(paths).mkdir(parents=True)
    reading_ui.relationship_task_record_path(paths).write_text(
        json.dumps({"pid": 24680, "kind": "mine"}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 24680)

    with pytest.raises(RuntimeError, match="Relationship task is already running"):
        start_relationship_task(
            AppState(paths=paths),
            {
                "source_dir": str(source_dir),
                "output_root": str(output_root),
                "llm_endpoint": "http://localhost:11434/api/generate",
            },
            "mine",
        )


def test_start_relationship_task_ignores_stale_relationship_record(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    document = source_dir / "doc.md"
    source_dir.mkdir()
    document.write_text("doc", encoding="utf-8")
    (output_root / "_state").mkdir(parents=True)
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    reading_ui.relationship_dir(paths).mkdir(parents=True)
    reading_ui.relationship_task_record_path(paths).write_text(
        json.dumps({"pid": 999999, "kind": "mine"}, ensure_ascii=False),
        encoding="utf-8",
    )

    class FakeRelationshipProcess:
        pid = 24680

        def poll(self):
            return None

    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: False)
    monkeypatch.setattr(
        reading_ui.subprocess,
        "Popen",
        lambda *args, **kwargs: FakeRelationshipProcess(),
    )

    payload = start_relationship_task(
        AppState(paths=paths),
        {
            "source_dir": str(source_dir),
            "output_root": str(output_root),
            "llm_endpoint": "http://localhost:11434/api/generate",
        },
        "mine",
    )

    assert payload["started"] is True
    assert payload["pid"] == 24680
    assert not reading_ui.relationship_task_record_path(paths).exists()


def test_infer_source_dir_ignores_stale_relationship_record(
    tmp_path: Path, monkeypatch
) -> None:
    stale_source = tmp_path / "stale-source"
    actual_source = tmp_path / "actual-source"
    output_root = tmp_path / "output"
    document = actual_source / "nested" / "doc.md"
    stale_source.mkdir()
    document.parent.mkdir(parents=True)
    (output_root / "_state").mkdir(parents=True)
    reading_ui.relationship_dir(
        ReadingPaths(source_dir=stale_source, output_root=output_root)
    ).mkdir(parents=True)
    reading_ui.relationship_task_record_path(
        ReadingPaths(source_dir=stale_source, output_root=output_root)
    ).write_text(
        json.dumps(
            {
                "pid": 999999,
                "kind": "mine",
                "source_dir": str(stale_source),
                "output_root": str(output_root),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    document.write_text("doc", encoding="utf-8")
    (output_root / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "nested/doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: False)

    assert reading_ui.infer_source_dir_for_output(AppState(), output_root) == actual_source


def test_reset_relationship_output_only_clears_relationship_artifacts(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    relationship_dir = output_root / "_relationships"
    state_dir = output_root / "_state"
    rag_dir = output_root / "_rag"
    source_dir.mkdir()
    relationship_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    rag_dir.mkdir(parents=True)
    (relationship_dir / "relations.jsonl").write_text("x\n", encoding="utf-8")
    (relationship_dir / "clusters.json").write_text("[]", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text("{}\n", encoding="utf-8")
    (output_root / "reading_status.jsonl").write_text("{}\n", encoding="utf-8")
    (rag_dir / "vectors.jsonl").write_text("{}\n", encoding="utf-8")

    payload = reset_relationship_output(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root)),
        {"source_dir": str(source_dir), "output_root": str(output_root)},
    )

    assert payload["reset"] is True
    assert not relationship_dir.exists()
    assert (state_dir / "decisions.jsonl").exists()
    assert (output_root / "reading_status.jsonl").exists()
    assert (rag_dir / "vectors.jsonl").exists()


def test_reset_relationship_output_rejects_running_relationship_task(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    output_root.mkdir()

    class FakeRelationshipProcess:
        pid = 24680

        def poll(self):
            return None

    with pytest.raises(RuntimeError, match="relationship task is running"):
        reset_relationship_output(
            AppState(
                paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
                relationship_process=FakeRelationshipProcess(),
                relationship_process_kind="mine",
                relationship_process_command=[
                    "python",
                    "relationship_miner.py",
                    "--source-dir",
                    str(source_dir.resolve()),
                    "--output-root",
                    str(output_root.resolve()),
                ],
            ),
            {"source_dir": str(source_dir), "output_root": str(output_root)},
        )


def test_stop_analysis_terminates_external_locked_run(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    run_lock_path(output_root).parent.mkdir(parents=True)
    run_lock_path(output_root).write_text(
        json.dumps({"pid": 13579}, ensure_ascii=False),
        encoding="utf-8",
    )
    state = {"alive": True, "terminated": False}

    def fake_is_process_alive(pid: int) -> bool:
        return pid == 13579 and state["alive"]

    def fake_terminate(pid: int) -> bool:
        if pid == 13579:
            state["alive"] = False
            state["terminated"] = True
            return True
        return False

    monkeypatch.setattr(reading_ui, "is_process_alive", fake_is_process_alive)
    monkeypatch.setattr(reading_ui, "terminate_process_id", fake_terminate)

    payload = stop_analysis(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert state["terminated"] is True
    assert payload == {"stopped": True, "running": False, "pid": 13579}


def test_status_and_stop_can_target_unsaved_output_directory(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    old_output = tmp_path / "docs"
    new_output = tmp_path / "docs2"
    source_dir.mkdir()
    (old_output / "_state").mkdir(parents=True)
    (old_output / "_logs").mkdir(parents=True)
    (new_output / "_state").mkdir(parents=True)
    (new_output / "_logs").mkdir(parents=True)
    (old_output / "_logs" / "doctriage.log").write_text(
        "old log\n",
        encoding="utf-8",
    )
    (new_output / "_logs" / "doctriage.log").write_text(
        "2026-06-05 10:00:00,000 [INFO] doctriage - Progress 2/10 (20.0%)\n",
        encoding="utf-8",
    )
    (new_output / "_state" / "progress.json").write_text(
        json.dumps({"completed": 2, "total": 10, "remaining": 8}, ensure_ascii=False),
        encoding="utf-8",
    )
    run_lock_path(new_output).write_text(
        json.dumps({"pid": 22222}, ensure_ascii=False),
        encoding="utf-8",
    )
    state = {"alive": True, "terminated": False}

    def fake_is_process_alive(pid: int) -> bool:
        return pid == 22222 and state["alive"]

    def fake_terminate(pid: int) -> bool:
        if pid == 22222:
            state["alive"] = False
            state["terminated"] = True
            return True
        return False

    monkeypatch.setattr(reading_ui, "is_process_alive", fake_is_process_alive)
    monkeypatch.setattr(reading_ui, "terminate_process_id", fake_terminate)
    app_state = AppState(paths=ReadingPaths(source_dir=source_dir, output_root=old_output))
    requested_paths = ReadingPaths(source_dir=source_dir, output_root=new_output)

    payload = analysis_status(app_state, paths=requested_paths)

    assert payload["output_root"] == str(new_output.resolve())
    assert payload["running"] is True
    assert payload["pid"] == 22222
    assert "Progress 2/10" in payload["log_tail"]
    assert "old log" not in payload["log_tail"]

    stopped = stop_analysis(
        app_state,
        {"source_dir": str(source_dir), "output_root": str(new_output)},
    )

    assert state["terminated"] is True
    assert stopped == {"stopped": True, "running": False, "pid": 22222}


def test_mark_documents_appends_multiple_events(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    decisions = []
    for name in ("a.md", "b.md"):
        path = source_dir / name
        path.write_text(name, encoding="utf-8")
        decisions.append(
            {
                "source_path": str(path),
                "relative_path": name,
                "status": "planned",
                "quality": 90,
                "category": "Design",
            }
        )
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    result = mark_documents(
        ReadingPaths(source_dir=source_dir, output_root=output_root),
        {"relative_paths": ["a.md", "b.md"], "status": "read"},
    )

    assert result["count"] == 2
    assert (state_dir / "reading_status.jsonl").read_text(encoding="utf-8").count("\n") == 2


def test_set_reading_output_infers_source_from_decisions(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    document = source_dir / "nested" / "doc.md"
    document.parent.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "nested/doc.md",
                "status": "planned",
                "quality": 80,
                "category": "Design",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = set_reading_output(AppState(), {"output_root": str(output_root)})

    assert Path(payload["source_dir"]) == source_dir.resolve()
    assert Path(payload["output_root"]) == output_root.resolve()


def test_set_reading_output_does_not_change_active_analysis_paths(
    tmp_path: Path,
) -> None:
    analysis_source = tmp_path / "analysis-source"
    analysis_output = tmp_path / "analysis-output"
    reading_source = tmp_path / "reading-source"
    reading_output = tmp_path / "reading-output"
    document = reading_source / "doc.md"
    analysis_source.mkdir()
    analysis_output.mkdir()
    document.parent.mkdir(parents=True)
    (reading_output / "_state").mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (reading_output / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    app_state = AppState(
        paths=ReadingPaths(source_dir=analysis_source, output_root=analysis_output)
    )

    payload = set_reading_output(app_state, {"output_root": str(reading_output)})

    assert Path(payload["source_dir"]) == reading_source.resolve()
    assert app_state.paths is not None
    assert app_state.paths.source_dir == analysis_source
    assert app_state.paths.output_root == analysis_output


def test_reading_paths_from_payload_can_infer_source_from_output_only(
    tmp_path: Path,
) -> None:
    active_source = tmp_path / "active-source"
    active_output = tmp_path / "active-output"
    reading_source = tmp_path / "reading-source"
    reading_output = tmp_path / "reading-output"
    document = reading_source / "nested" / "doc.md"
    active_source.mkdir()
    active_output.mkdir()
    document.parent.mkdir(parents=True)
    (reading_output / "_state").mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (reading_output / "_state" / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "nested/doc.md",
                "status": "planned",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    app_state = AppState(
        paths=ReadingPaths(source_dir=active_source, output_root=active_output)
    )

    paths = reading_paths_from_payload(app_state, {"output_root": str(reading_output)})

    assert paths is not None
    assert paths.source_dir == reading_source.resolve()
    assert paths.output_root == reading_output.resolve()


def test_export_anydocs_bundle_request_writes_bundle_from_output_only(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    source = source_dir / "architecture.md"
    source.write_text("architecture", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(source),
                "relative_path": "architecture.md",
                "status": "planned",
                "quality": 90,
                "category": "Architecture",
                "document_kind": "Note",
                "summary": "Architecture summary.",
                "reason": "Useful architecture note.",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    payload = reading_ui.export_anydocs_bundle_request(
        AppState(),
        {"output_root": str(output_root), "quality_threshold": "80"},
    )

    bundle_path = Path(payload["bundle_path"])
    assert payload["exported"] is True
    assert bundle_path == output_root / "_relationships" / "doctriage_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["schema_version"] == "doctriage_bundle.v2"
    assert bundle["selection_policy"]["min_quality"] == 80
    assert bundle["documents"][0]["paths"]["source"] == str(source)


def test_infer_source_dir_from_decisions_without_relative_path(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir = tmp_path / "source"
    document = source_dir / "doc.md"
    document.parent.mkdir(parents=True)
    state_dir.mkdir(parents=True)
    document.write_text("doc", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps({"source_path": str(document), "status": "planned"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    assert infer_source_dir_from_decisions(output_root) == source_dir.resolve()


def test_config_payload_reports_capabilities() -> None:
    payload = config_payload(None)

    assert payload["source_dir"] == ""
    assert payload["output_root"] == ""
    assert payload["embedding_endpoint"]
    assert "folder_picker" in payload["capabilities"]
    assert "open_file" in payload["capabilities"]
    assert "reveal_file" in payload["capabilities"]


def test_analysis_form_exposes_help_tooltips_for_run_options() -> None:
    html = frontend_source()
    compact_html = frontend_source_compact()

    assert "挖掘关系" in html
    assert "输出到 _relationships/relations.jsonl 与 clusters.json" in html
    assert "建议在首轮评分稳定后、关系质量比速度更重要时再勾选" in html
    assert "内容检测除了时间和大小，还计算文件内容哈希" not in html
    assert "变更检测除了时间和大小，还计算文件内容哈希" not in html
    assert 'id="run_embedding_model"' in html
    assert 'id="toggle_advanced_btn"' not in html
    assert "选择模板" not in html
    assert "应用模板" not in html
    assert "隐藏高级参数" not in html
    assert "显示高级参数" not in html
    assert 'data-i18n="apply_paths"' not in html
    assert "应用路径" not in html
    assert 'id="start_analysis_btn" class="primary" onclick="toggleAnalysis()"' in html
    assert 'id="stop_analysis_btn"' not in html
    assert 'id="early_relationships_btn" class="primary" onclick="toggleRelationships()"' in html
    assert 'id="stop_relationships_btn"' not in html
    assert 'id="reset_relationships_btn" class="danger"' in html
    assert 'id="graph_mine_btn" class="primary" onclick="toggleGraphRelationships()"' in html
    assert 'id="graph_stop_relationships_btn"' not in html
    assert 'data-i18n="apply_graph_output"' not in html
    assert "应用图谱目录" not in html
    assert 'class="graph-target-row"' in html
    assert 'class="graph-actions-row"' in html
    assert html.index('id="reset_analysis_btn"') < html.index('id="early_relationships_btn"')
    assert html.index('id="early_relationships_btn"') < html.index('id="reset_relationships_btn"')
    assert html.index('id="reset_analysis_btn"') < html.index('<div class="relationship-toolbar">')
    assert 'class="advanced-run relationship-option"><input id="run_plan_only" type="checkbox" checked' in html
    assert 'class="advanced-run relationship-option"><input id="run_document_summary" type="checkbox" checked' in html
    assert html.index('id="run_plan_only"') < html.index('id="run_document_summary"')
    assert 'class="advanced-run relationship-option"><input id="run_ocr_enabled"' in html
    assert 'class="advanced-run relationship-option"><input id="run_manifest_analysis"' in html
    assert 'id="run_force_reprocess"' not in html
    assert 'id="run_content_hash"' not in html
    assert "强制重跑" not in html
    assert "内容 Hash" not in html
    assert '<input id="run_mine_relationships" type="checkbox" checked' in html
    assert '<input id="run_relationship_text" type="checkbox" checked' in html
    assert '<input id="run_relationship_embeddings" type="checkbox" checked' not in html
    assert 'data-i18n="limit">数量上限' in html
    assert 'data-i18n="plan_only">仅评分，不复制文件' in html
    assert 'data-i18n="ocr_enabled">开启OCR' in html
    assert 'data-i18n="manifest_analysis">开启目录分析' in html
    assert 'limit: "数量上限"' in html
    assert 'plan_only: "仅评分，不复制文件"' in html
    assert 'ocr_enabled: "开启OCR"' in html
    assert 'manifest_analysis: "开启目录分析"' in html
    assert 'limit: "Limit"' in html
    assert 'plan_only: "Score only, do not copy files"' in html
    assert 'ocr_enabled: "Enable OCR"' in html
    assert 'manifest_analysis: "Enable directory analysis"' in html
    assert 'class="relationship-embedding-row"' in html
    assert 'justify-content: flex-start' in html
    assert "width: clamp(120px, 16vw, 180px); min-width: 120px;" in compact_html
    assert ".relationship-actions { display: inline-flex; gap: 8px; flex: 0 0 auto;" in compact_html
    assert 'endpoint.replace(/\\/v1\\/chat\\/completions\\/?$/i, "/v1/embeddings")' in html
    assert html.index('id="run_relationship_embeddings"') < html.index('id="run_embedding_model"')
    assert html.index('id="run_embedding_model"') < html.index('id="early_relationships_btn"')
    assert "不会自动沿用这里的模型" in html
    assert "必须填写向量模型" in html
    assert 'data-i18n="refresh_status"' not in html
    assert "刷新状态" not in html
    assert 'data-i18n="test_llm"' not in html
    assert "测试LLM" not in html
    assert 'id="embeddingProgressWrap"' in html
    assert "重置分析" in html
    assert "重置关系" in html
    assert "关系图谱" in html
    assert 'id="graphClusters"' in html
    assert "header { padding: 16px 20px 0;" in compact_html
    assert ".tabs { display: flex; gap: 18px; align-items: flex-end; margin-bottom: 0; border-bottom: 1px solid var(--line); }" in compact_html
    assert ".tab { height: 36px; border: 0; border-bottom: 3px solid transparent;" in compact_html
    assert ".tab.active { border-bottom-color: var(--blue); color: var(--blue); background: var(--surface-soft); }" in compact_html
    assert ".tab.active { background: var(--blue);" not in compact_html
    assert "function setAdvancedRunOptionsVisible" not in html
    assert "function toggleAdvancedRunOptions" not in html
    assert (
        'setInterval(() => {\n'
        '  if ($("section-analysis").classList.contains("active")) loadAnalysis();\n'
        '  if ($("section-graph").classList.contains("active") && graphMeta && graphMeta.task && graphMeta.task.running) loadGraph();\n'
        '  if ($("section-rag").classList.contains("active")) loadRagStatus();\n'
        '}, 3000);'
    ) in html


def test_rag_tab_exposes_independent_index_controls() -> None:
    html = frontend_source()
    compact_html = frontend_source_compact()

    assert 'id="tab-rag"' in html
    assert 'id="section-rag"' in html
    assert 'id="rag_output_root"' in html
    assert 'id="rag_embedding_model"' in html
    assert 'id="start_rag_btn" class="primary" onclick="toggleRagIndex()"' in html
    assert 'id="stop_rag_btn"' not in html
    assert 'id="ragBar"' in html
    assert 'id="ragResults"' in html
    assert 'tab_rag: "RAG 索引"' in html
    assert 'tab_rag: "RAG Index"' in html
    assert "RAG 索引会独立写入该目录下的 _rag" not in html
    assert "敏感词过滤和映射会在分片入库前执行" not in html
    assert "RAG 索引单独写入 `_rag/`" not in html
    assert 'class="rag-target-row"' in html
    assert 'class="rag-options-row"' in html
    assert ".rag-target-row button { min-width: 96px; white-space: nowrap; }" in compact_html
    assert ".rag-options-row { display: grid; grid-template-columns: minmax(180px, 220px)" in compact_html
    assert ".rag-options-row select[multiple] { height: 32px; }" in compact_html
    assert '<select id="rag_categories" multiple>' in html
    assert '<option value="Architecture">Architecture</option>' in html
    assert '<option value="Research">Research</option>' in html
    assert "function selectedValues(id)" in html
    assert "function setSelectedValues(id, values)" in html
    assert 'rag_categories: selectedValues("rag_categories").join(",")' in html
    assert "function ragPathPayload()" in html
    assert "function ragPayload()" in html
    assert "async function toggleAnalysis()" in html
    assert "async function toggleRelationships()" in html
    assert "async function resetRelationships()" in html
    assert "function updateAnalysisButtons(payload)" in html
    assert "function loadRagStatus()" in html
    assert "async function toggleRagIndex()" in html
    assert "function updateRagButtons(payload)" in html
    assert "function startRagIndex()" in html
    assert "function stopRagIndex()" in html
    assert "function searchRag()" in html
    assert 'id="rag_vector_store_type"' in html
    assert 'id="rag_vector_store_url"' in html
    assert 'id="rag_vector_store_collection"' in html
    assert 'id="test_vector_store_btn"' in html
    assert 'id="vectorStoreTestStats"' in html
    assert "function testVectorStore()" in html
    assert 'fetch("/api/test/vector-store"' in html
    assert 'fetch("/api/relationships/reset"' in html
    assert 'fetch("/api/rag" + (query ? "?" + query : ""))' in html
    assert 'fetch("/api/rag/build"' in html
    assert 'fetch("/api/rag/stop"' in html
    assert 'fetch("/api/rag/search"' in html
    assert 'const RAG_TARGET_STORAGE_KEY = "doctriage_rag_target";' in html
    assert "initRagTargetPersistence();" in html
    assert 'if (targetId === "rag_output_root") {' in html
    assert 'id="rag_advanced_panel"' in html
    assert 'id="rag_redaction_enabled"' in html
    assert 'id="rag_redact_drop_matched_documents"' in html
    assert 'id="rag_redact_placeholder"' in html
    assert 'id="rag_redact_terms"' in html
    assert 'id="rag_redact_mappings"' in html
    assert "function syncRagRedactionInputs()" in html
    assert "function validateRagRedactionPayload(payload)" in html
    assert 'showToast(tr("rag_redaction_rules_required"));' in html


def test_anydocs_bridge_ui_is_optional_and_first_class() -> None:
    html = frontend_source()
    compact_html = frontend_source_compact()

    assert 'id="tab-agents"' in html
    assert 'id="section-agents"' in html
    assert 'data-i18n="tab_agents">Agent 编译' in html
    assert 'class="anydocs-toolbar"' in html
    assert 'class="anydocs-target-row"' in html
    assert ".anydocs-target-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(96px, auto) minmax(0, 1fr) minmax(0, 1fr); gap: 8px; align-items: end; }" in compact_html
    assert ".anydocs-target-row input { width: 100%; min-width: 0; }" in compact_html
    assert 'id="anydocs_output_root"' in html
    assert 'id="anydocs_url"' in html
    assert 'id="anydocs_bundle_path" readonly' in html
    assert 'onclick="exportAnydocsBundle()"' in html
    assert 'onclick="openAnyDocs(false)"' in html
    assert 'onclick="openAnyDocs(true)"' in html
    assert "AnyDocsToAgents 独立运行" in html
    assert "不启动、不依赖、不嵌入下游服务" in html
    assert "https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/AnyDocsToAgents" in html
    assert "https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage" not in html
    assert 'class="button-link github-icon-link"' in html
    assert "<svg viewBox=" in html
    assert 'for (const id of ["analysis", "reading", "graph", "rag", "agents"])' in html
    assert 'initAnydocsTargetPersistence();' in html
    assert 'fetch("/api/integrations/anydocs/export-bundle"' in html
    assert 'fetch("/api/integrations/anydocs/open"' in html


def test_reading_tab_uses_compact_filter_layout() -> None:
    html = frontend_source()
    compact_html = frontend_source_compact()

    assert 'class="panel reading-target"' in html
    assert 'class="panel reading-filter-panel"' in html
    assert 'class="reading-filter-primary"' in html
    assert 'class="reading-filter-secondary"' in html
    assert 'data-i18n="apply_reading_output"' not in html
    assert "应用阅读目录" not in html
    assert "Apply reading directory" not in html
    assert "reading_target_hint" not in html
    assert "分析输出目录会单向回填这里" not in html
    assert "Switching the reading directory does not affect analysis execution" not in html
    assert "class=\"panel filters reading-filters\"" not in html
    assert ".reading-filter-primary button { min-width: 96px; white-space: nowrap; }" in compact_html

    primary_start = html.index('class="reading-filter-primary"')
    secondary_start = html.index('class="reading-filter-secondary"')
    primary_body = html[primary_start:secondary_start]

    assert 'id="q"' in primary_body
    assert 'id="status"' in primary_body
    assert 'id="min_quality"' in primary_body
    assert 'onclick="loadRows()" data-i18n="refresh"' in primary_body
    assert 'id="reading_scope"' not in primary_body

    secondary_body = html[secondary_start:html.index('<div class="summary-bar">', secondary_start)]
    assert 'id="reading_scope"' in secondary_body
    assert 'id="categories"' in secondary_body
    assert 'id="topic_tags"' in secondary_body


def test_frontend_status_and_graph_requests_include_current_paths() -> None:
    html = frontend_source()

    assert "function pathPayload()" in html
    assert "function pathQuery()" in html
    assert "function readingPathPayload()" in html
    assert "function readingParams()" in html
    assert "function graphPathPayload()" in html
    assert "function graphQuery()" in html
    graph_payload_start = html.index("function graphPathPayload()")
    graph_payload_end = html.index("function pathQuery()", graph_payload_start)
    graph_payload_body = html[graph_payload_start:graph_payload_end]
    assert 'const outputRoot = $("graph_output_root").value.trim();' in graph_payload_body
    assert '$("reading_output_root").value.trim() || $("run_output_root").value.trim()' not in graph_payload_body
    assert 'const response = await fetch("/api/analysis/status" + (query ? "?" + query : ""));' in html
    assert 'body: JSON.stringify(pathPayload())' in html
    assert "const query = graphQuery();" in html
    assert 'const response = await fetch("/api/relationships" + (query ? "?" + query : ""));' in html
    assert "const query = new URLSearchParams(graphPathPayload());" in html
    assert "const requestPayload = {...runPayload(), ...graphPathPayload()};" in html
    assert 'const response = await fetch("/api/state?" + readingParams());' in html
    assert 'query.set("cluster", String(clusterId));' in html
    assert 'pairs.set("source_dir", paths.source_dir);' in html
    assert 'pairs.set("output_root", paths.output_root);' in html


def test_reading_output_does_not_backfill_analysis_paths() -> None:
    html = frontend_source()

    apply_start = html.index("async function applyReadingOutput()")
    apply_end = html.index("function runPayload()", apply_start)
    apply_body = html[apply_start:apply_end]

    assert '$("run_output_root").value = outputRoot' not in apply_body
    assert 'if (payload.source_dir) $("run_source_dir").value = payload.source_dir' not in apply_body
    assert 'if (payload.output_root) $("run_output_root").value = payload.output_root' not in apply_body
    assert 'setReadingTarget(payload.source_dir || "", payload.output_root || outputRoot);' in apply_body
    assert "renderReadingError(message);" in apply_body
    assert "showToast(message);" in apply_body
    assert "showToast(tr(\"reading_output_applied\"))" not in apply_body
    assert "function autoApplyReadingOutput()" in html
    assert "function renderReadingError(message)" in html
    assert "function readingPathPayload()" in html
    assert "function readingParams()" in html
    assert 'const paths = readingPathPayload();' in html
    assert 'if (id === "run_output_root") syncReadingTargetFromRunOutput({force: true});' in html
    assert 'if (targetId === "reading_output_root") {' in html
    assert 'await applyReadingOutput();' in html
    assert 'element.addEventListener("blur", () => autoApplyReadingOutput());' in html
    assert 'syncGraphTargetFrom("", payload.path || "", {force: true});' in html
    assert 'body: JSON.stringify({relative_path: relativePath, status, note, ...readingPathPayload()})' in html
    assert 'body: JSON.stringify({relative_paths: paths, status, ...readingPathPayload()})' in html


def test_reading_tab_loads_rows_after_config_backfills_existing_output() -> None:
    html = frontend_source()

    switch_start = html.index("function switchTab(name)")
    switch_end = html.index("async function loadConfig()", switch_start)
    switch_body = html[switch_start:switch_end]
    config_start = html.index("async function loadConfig()")
    config_end = html.index("async function pickFolder(targetId)", config_start)
    config_body = html[config_start:config_end]
    helper_start = html.index("function loadReadingRowsIfReady()")
    helper_end = html.index("async function loadConfig()", helper_start)
    helper_body = html[helper_start:helper_end]

    assert 'if (name === "reading") loadReadingRowsIfReady();' in switch_body
    assert "loadReadingRowsIfReady();" in config_body
    assert 'if (!$("section-reading").classList.contains("active")) return;' in helper_body
    assert "if (readingPathPayload().output_root) loadRows();" in helper_body


def test_graph_output_does_not_backfill_analysis_or_reading_paths() -> None:
    html = frontend_source()

    apply_start = html.index("async function applyGraphOutput()")
    apply_end = html.index("function runPayload()", apply_start)
    apply_body = html[apply_start:apply_end]
    graph_input_start = html.index("function initGraphTargetPersistence()")
    graph_input_end = html.index("function setUiLanguage", graph_input_start)
    graph_input_body = html[graph_input_start:graph_input_end]
    pick_start = html.index("async function pickFolder(targetId)")
    pick_end = html.index("async function applyPaths", pick_start)
    pick_body = html[pick_start:pick_end]
    graph_pick_body = pick_body[
        pick_body.index('if (targetId === "graph_output_root") {') :
    ]

    assert 'fetch("/api/graph-output"' in apply_body
    assert "body: JSON.stringify({output_root: outputRoot})" in apply_body
    assert 'setGraphTarget(payload.source_dir || "", payload.output_root || outputRoot);' in apply_body
    assert '$("run_output_root").value' not in apply_body
    assert '$("run_source_dir").value' not in apply_body
    assert '$("reading_output_root").value' not in apply_body
    assert "readingSourceDir =" not in apply_body
    assert "syncReadingTargetFromRunOutput" not in apply_body
    assert "setReadingTarget" not in apply_body
    assert "const GRAPH_TARGET_STORAGE_KEY = \"doctriage_graph_target\";" in html
    assert "function currentGraphTargetState()" in html
    assert "JSON.stringify(currentGraphTargetState())" in html
    assert "function graphPathPayload()" in html
    assert "function graphQuery()" in html
    assert 'graphSourceDir = "";' in graph_input_body
    assert "saveGraphTargetState();" in graph_input_body
    assert 'element.addEventListener("blur", () => autoApplyGraphOutput());' in graph_input_body
    assert 'if (targetId === "graph_output_root") {' in pick_body
    assert 'graphSourceDir = "";' in pick_body
    assert "saveGraphTargetState();" in pick_body
    assert "await applyGraphOutput();" in graph_pick_body
    assert "syncGraphTargetFrom" not in graph_pick_body
    assert "function autoApplyGraphOutput()" in html
    assert "renderGraphError(message);" in apply_body
    assert "initGraphTargetPersistence();" in html
    assert "syncGraphTargetFromReadingOutput({force: true" in html


def test_analysis_run_form_persists_previous_values() -> None:
    html = frontend_source()

    assert 'const RUN_FORM_STORAGE_KEY = "doctriage_run_form";' in html
    assert "const RUN_FORM_STORAGE_VERSION = 3;" in html
    assert "function readStoredRunFormState()" in html
    assert "function applyStoredRunFormState()" in html
    assert "function saveRunFormState()" in html
    assert "function initRunFormPersistence()" in html
    assert "const state = {_version: RUN_FORM_STORAGE_VERSION};" in html
    assert "const applyCheckboxState = Number(state._version || 0) === RUN_FORM_STORAGE_VERSION;" in html
    assert "if (!applyCheckboxState) return;" in html
    for field_id in [
        "run_source_dir",
        "run_output_root",
        "run_llm_endpoint",
        "run_llm_model",
        "run_output_language",
        "run_embedding_model",
        "run_concurrency",
        "run_limit",
        "run_max_file_size_mb",
        "run_quality_threshold",
        "run_timeout_seconds",
        "run_plan_only",
        "run_document_summary",
        "run_ocr_enabled",
        "run_manifest_analysis",
        "run_mine_relationships",
        "run_relationship_text",
        "run_relationship_embeddings",
    ]:
        assert f'"{field_id}"' in html
    assert html.count("applyStoredRunFormState();") >= 2
    assert "initRunFormPersistence();" in html
    assert 'if (targetId.startsWith("run_")) saveRunFormState();' in html
    assert "syncEmbeddingModelVisibility" not in html
    assert 'embedding_model: $("run_embedding_model").value.trim(),' in html
    assert 'embedding_model: $("run_relationship_embeddings").checked ? $("run_embedding_model").value.trim() : ""' not in html
    assert 'saveRunFormState();\n  const requestPayload = runPayload();' in html
    assert 'if (!validateEmbeddingModelSelection(requestPayload)) return;' in html
    assert 'const response = await fetch("/api/analysis/start"' in html
    assert "function applyTemplate()" not in html
    assert 'ocr_enabled: $("run_ocr_enabled").checked,' in html
    assert 'manifest_analysis: $("run_manifest_analysis").checked,' in html
    assert 'no_ocr: !$("run_ocr_enabled").checked,' in html
    assert 'skip_manifest_analysis: !$("run_manifest_analysis").checked,' in html
    assert "force_reprocess: false," in html
    assert "content_hash: false," in html
    assert 'concurrency_pill: "并发"' in html
    assert 'concurrency_pill: "Concurrency"' in html


def test_analysis_paths_auto_apply_on_blur_without_button() -> None:
    html = frontend_source()

    assert 'if (element) element.addEventListener("blur", () => autoApplyPaths());' in html
    assert "async function autoApplyPaths()" in html
    assert "if (!sourceDir || !outputRoot) return;" in html
    assert "if (key === lastAppliedRunPathKey) return;" in html
    assert "await applyPaths({showSuccess: false});" in html
    assert "lastAppliedRunPathKey = runPathKey(sourceDir, outputRoot);" in html
    assert 'if (targetId === "run_source_dir" || targetId === "run_output_root") autoApplyPaths();' in html
    assert 'data-i18n="apply_paths"' not in html


def test_early_relationship_payload_respects_embedding_checkbox() -> None:
    html = frontend_source()

    payload_start = html.index("function earlyRelationshipPayload()")
    payload_end = html.index("function pathPayload()", payload_start)
    payload_body = html[payload_start:payload_end]
    action_start = html.index("async function startEarlyRelationships(currentPayload = null)")
    action_end = html.index("function showRelationshipLaunchPending(payload)", action_start)
    action_body = html[action_start:action_end]

    assert "const payload = runPayload();" in payload_body
    assert 'payload.embedding_model = $("run_embedding_model").value.trim();' in payload_body
    assert "payload.mine_relationships = true;" in payload_body
    assert "payload.relationship_use_text_citations = true;" in payload_body
    assert "payload.relationship_use_embeddings = true;" not in payload_body
    assert 'run_mine_relationships").checked' not in payload_body
    assert 'run_relationship_text").checked' not in payload_body
    assert "const requestPayload = earlyRelationshipPayload();" in action_body
    assert "if (!validateEmbeddingModelSelection(requestPayload)) return;" in action_body
    assert "if (!confirmEarlyRelationshipsWithoutEmbeddingIfNeeded(requestPayload)) return;" in action_body
    assert "body: JSON.stringify(requestPayload)" in action_body
    assert "body: JSON.stringify(earlyRelationshipPayload())" not in action_body
    assert "body: JSON.stringify(runPayload())" not in action_body


def test_embedding_model_validation_before_embedding_requests() -> None:
    html = frontend_source()

    validate_start = html.index("function validateEmbeddingModelSelection(payload)")
    validate_end = html.index("function confirmEarlyRelationshipsWithoutEmbeddingIfNeeded(payload)", validate_start)
    validate_body = html[validate_start:validate_end]
    confirm_start = html.index("function confirmEarlyRelationshipsWithoutEmbeddingIfNeeded(payload)")
    confirm_end = html.index("function pathPayload()", confirm_start)
    confirm_body = html[confirm_start:confirm_end]
    analysis_start = html.index("async function startAnalysis(currentPayload = null)")
    analysis_end = html.index("function shouldPreemptRelationshipsForAnalysis", analysis_start)
    analysis_body = html[analysis_start:analysis_end]
    early_start = html.index("async function startEarlyRelationships(currentPayload = null)")
    early_end = html.index("function showRelationshipLaunchPending(payload)", early_start)
    early_body = html[early_start:early_end]
    graph_start = html.index("async function startGraphTask(taskName)")
    graph_end = html.index("function renderGraphEmptyState()", graph_start)
    graph_body = html[graph_start:graph_end]

    assert "if (!payload || !payload.relationship_use_embeddings) return true;" in validate_body
    assert 'if (String(payload.embedding_model || "").trim()) return true;' in validate_body
    assert 'showToast(tr("embedding_model_required"));' in validate_body
    assert "return false;" in validate_body
    assert "if (!payload || payload.relationship_use_embeddings) return true;" in confirm_body
    assert 'if (String(payload.embedding_model || "").trim()) return true;' in confirm_body
    assert 'return window.confirm(tr("early_relationships_without_embedding_confirm"));' in confirm_body
    assert "已勾选 Embedding 关系，请先填写 Embedding 模型。" in html
    assert "本次将只生成关系挖掘和标题引用，不生成 Embedding 向量" in html
    assert "Embedding relationships are selected. Enter an embedding model first." in html
    assert "without generating embedding vectors" in html
    assert "const requestPayload = runPayload();" in analysis_body
    assert "requestPayload.preempt_relationships = true;" in analysis_body
    assert "const preemptRelationships = shouldPreemptRelationshipsForAnalysis(currentPayload);" in analysis_body
    assert "if (preemptRelationships) {" in analysis_body
    assert "showToast(tr(\"analysis_preempting_relationships\"));" in analysis_body
    assert "if (!validateEmbeddingModelSelection(requestPayload)) return;" in analysis_body
    assert "await requestStopRelationships(requestPayload, {showToastMessage: false, refresh: false});" in analysis_body
    assert "async function ensureEndpointReady" in html
    assert 'fetch("/api/test/llm"' in html
    assert 'endpoint: requestPayload.embedding_endpoint' in analysis_body
    assert analysis_body.index("requestStopRelationships") < analysis_body.index("ensureEndpointReady")
    assert analysis_body.index("ensureEndpointReady") < analysis_body.index('fetch("/api/analysis/start"')
    assert analysis_body.index("validateEmbeddingModelSelection") < analysis_body.index('fetch("/api/analysis/start"')
    assert "const requestPayload = earlyRelationshipPayload();" in early_body
    assert "if (!validateEmbeddingModelSelection(requestPayload)) return;" in early_body
    assert "if (!confirmEarlyRelationshipsWithoutEmbeddingIfNeeded(requestPayload)) return;" in early_body
    assert 'endpoint: requestPayload.embedding_endpoint' in early_body
    assert early_body.index("ensureEndpointReady") < early_body.index('fetch("/api/analysis/early-relationships"')
    assert early_body.index("validateEmbeddingModelSelection") < early_body.index("confirmEarlyRelationshipsWithoutEmbeddingIfNeeded")
    assert early_body.index("confirmEarlyRelationshipsWithoutEmbeddingIfNeeded") < early_body.index('fetch("/api/analysis/early-relationships"')
    assert "const requestPayload = {...runPayload(), ...graphPathPayload()};" in graph_body
    assert 'if (taskName === "mine" && !validateEmbeddingModelSelection(requestPayload)) return;' in graph_body
    assert graph_body.index("validateEmbeddingModelSelection") < graph_body.index('fetch(`/api/relationships/${taskName.replace("_", "-")}`')


def test_reading_table_uses_name_column_with_summary_tooltip() -> None:
    html = frontend_source()

    assert 'setSort(\'path\')"><span data-i18n="table_name">名称' in html
    assert "doc-name" in html
    assert '${escapeHtml(row.relative_path || "")}</span>' in html
    assert "doc-path" in html
    assert '${row.source_path ? `<span class="doc-path">${escapeHtml(row.source_path)}</span>` : ""}' in html
    assert "function rowExplanation(row)" in html
    assert 'data-tip="${escapeAttrValue(explanation)}"' in html
    assert 'tr("explain_reason")' in html
    assert "EXPLANATION_DIMENSIONS" in html
    assert "bindSummaryTooltips();" in html
    assert "path: sortKey === \"source_path_asc\" || sortKey === \"path_asc\" ? \"source_path_desc\" : \"source_path_asc\"" in html


def test_reading_table_exports_filtered_rows_with_explainability_fields() -> None:
    html = frontend_source()

    assert "exportFilteredRows('csv')" in html
    assert "exportFilteredRows('jsonl')" in html
    assert "function rowsToCsv(rows)" in html
    assert "function rowsToJsonl(rows)" in html
    assert "knowledge_density: row.knowledge_density" in html
    assert '"knowledge_density"' in html
    assert '"implementation_specificity"' in html
    assert "exported_rows" in html


def test_reading_table_stores_sort_per_scope() -> None:
    html = frontend_source()

    assert "function sortStorageKey(scope)" in html
    assert "doctriage_reading_sort_source" in html
    assert "doctriage_reading_sort_analysis" in html


def test_analysis_status_pills_use_i18n_labels() -> None:
    html = frontend_source()

    render_start = html.index("function renderAnalysis(payload)")
    render_end = html.index("function activityPillText", render_start)
    render_body = html[render_start:render_end]

    assert 'tr("plan_only_pill")' in render_body
    assert 'tr("not_running_pill")' in render_body
    assert 'tr("stale_lock_pid_pill")' in render_body
    assert "localizedPhase(payload.phase)" in render_body
    assert "activityPillText(latest)" in render_body
    assert 'latest.label ? `${localizedActivityLabel' not in render_body
    assert "Plan only：仅评分与阅读标记，不复制文件" not in render_body
    assert '"未运行"' not in render_body
    assert "陈旧锁 PID" not in render_body

    assert 'plan_only_pill: "Plan only: score and mark reading status without copying files"' in html
    assert 'not_running_pill: "Not running"' in html
    assert 'stale_lock_pid_pill: "Stale lock PID"' in html
    assert 'phase_not_started: "Not started"' in html


def test_embedding_progress_bar_is_independent_and_hidden_until_relationship_embedding() -> None:
    html = frontend_source()

    render_start = html.index("function renderEmbeddingProgress(progress, task)")
    render_end = html.index("function localizedEmbeddingPhase", render_start)
    render_body = html[render_start:render_end]

    assert 'class="embedding-progress-wrap"' in html
    assert 'command.includes("--use-embeddings")' in render_body
    assert 'command.includes("--relationship-use-embeddings")' in render_body
    assert "const progressActive = !!(progress && progress.enabled" in render_body
    assert "const activeEmbeddingTask = !!(task && (task.running || task.stopping) && embeddingTask);" in render_body
    assert "(activeEmbeddingTask || progressActive)" in render_body
    assert "const keepEmbeddingTask = !effectiveRelationshipTask.running && embeddingProgress && embeddingProgress.enabled" in html
    assert "lastEmbeddingTask || effectiveRelationshipTask || {}" in html
    assert "const total = Number(progress.total || 0);" in render_body
    assert 'total > 0 ? `${tr("completed_pill")} ${Number(progress.completed || 0)}/${total}` : ""' in render_body
    assert '`${tr("speed_pill")} ${itemsPerMinute}/min`' in render_body
    assert 'ETA ${etaHuman}' in render_body
    assert 'const progressComplete = progressPhase === "complete";' in render_body
    assert '!progressComplete ? tr("embedding_eta_waiting_pill") : ""' in render_body
    assert '!progressComplete && progress.workers' in render_body
    assert '`${tr("eta_finish_pill")} ${finishTime}`' in render_body
    assert 'tr("embedding_cached_pill")' not in render_body
    assert 'tr("embedding_generated_pill")' not in render_body
    assert 'tr("embedding_missing_pill")' not in render_body
    assert '$("embeddingProgressWrap").style.display = visible ? "block" : "none";' in render_body
    assert '$("embeddingProgressBar").style.width = "0%";' in render_body
    assert "payload.progress || {}" in html
    assert "payload.embedding_progress || {}" in html
    assert "function formatEpochTime(epochSeconds)" in html


def test_relationship_buttons_use_independent_task_state() -> None:
    html = frontend_source()

    action_start = html.index("async function startAnalysis(currentPayload = null)")
    action_end = html.index("function shouldPreemptRelationshipsForAnalysis", action_start)
    action_body = html[action_start:action_end]
    render_start = html.index("function renderAnalysis(payload)")
    render_end = html.index("function renderEmbeddingProgress", render_start)
    render_body = html[render_start:render_end]

    assert 'updateAnalysisButtons(payload);' in render_body
    assert 'relationshipActive ? "stop_relationships" : "early_relationships"' in html
    assert 'relationshipActive ? "danger" : "primary"' in html
    assert 'analysisActive ? "stop_analysis" : "start_analysis"' in html
    assert 'analysisActive ? "danger" : "primary"' in html
    assert "analysisActionBusy || inlineRelationshipActive" in html
    assert "function effectiveRelationshipTaskForPayload(payload = null)" in html
    assert "function relationshipStopPayload()" in html
    assert "relationshipTask.output_root" in html
    assert "output_root: relationshipTask.output_root" in html
    assert "output_root: lastAnalysisPayload.output_root" in html
    assert "function clearRelationshipLaunchPendingState()" in html
    assert "clearRelationshipLaunchPendingState();" in action_body
    assert "function isInlineRelationshipTask(task)" in html
    assert "const inlineRelationshipActive = isInlineRelationshipTask(effectiveRelationshipTask);" in render_body
    assert "const showAnalysisProgress = !inlineRelationshipActive;" in render_body
    assert 'inlineRelationshipActive ? "" : (payload.running ? tr("running_pill") : tr("not_running_pill"))' in render_body
    assert "showAnalysisProgress && progress.percent !== undefined" in render_body
    assert "relationshipTaskPillText(effectiveRelationshipTask)" in render_body
    assert "let graphActionBusy = false;" in html
    assert "function updateGraphButtons(payload)" in html
    assert 'runningMine ? "stop_relationships" : "generate_relationships"' in html
    assert 'generate_relationships: "生成图谱"' in html
    assert 'generate_relationships: "Generate graph"' in html
    assert 'id="graphProgressWrap"' in html
    assert 'id="graphProgressBar"' in html
    assert "function renderGraphProgress(payload)" in html
    assert "function localizedGraphPhase(phase)" in html
    assert "function formatDurationShort(seconds)" in html
    assert "graphMeta.task && graphMeta.task.running) loadGraph();" in html
    assert 'runningMine ? "danger" : "primary"' in html
    assert "async function toggleGraphRelationships()" in html
    assert "const payload = await loadGraph();" in html
    assert 'const response = await fetch("/api/relationships/stop"' in html
    assert 'const payload = await refreshAnalysisStatus();' in html


def test_early_relationship_click_shows_pending_feedback_immediately() -> None:
    html = frontend_source()

    action_start = html.index("async function startEarlyRelationships(currentPayload = null)")
    action_end = html.index("function showRelationshipLaunchPending(payload)", action_start)
    action_body = html[action_start:action_end]
    pending_start = html.index("function showRelationshipLaunchPending(payload)")
    pending_end = html.index("function clearRelationshipLaunchPendingState()", pending_start)
    pending_body = html[pending_start:pending_end]

    assert "let relationshipLaunchPending = null;" in html
    assert "showRelationshipLaunchPending(requestPayload);" in action_body
    assert "clearRelationshipLaunchPending(token);" in action_body
    assert 'return showToast(responsePayload.error || tr("early_relationships_failed"));' in action_body
    assert 'analysis_preempting_relationships: "正在停止生成关系并准备开始分析"' in html
    assert 'analysis_preempting_relationships: "Stopping relationship generation and preparing analysis"' in html
    assert "relationshipLaunchPending = {" in pending_body
    assert "useEmbeddings: !!(payload && payload.relationship_use_embeddings)" in pending_body
    assert "renderAnalysis(lastAnalysisPayload);" in pending_body
    assert "renderEmbeddingProgress(pendingEmbeddingProgress(), task);" in pending_body
    assert "function pendingRelationshipTask()" in html
    assert 'command: relationshipLaunchPending.useEmbeddings ? ["--use-embeddings"] : []' in html
    assert "function pendingEmbeddingProgress()" in html
    assert 'phase: "ready"' in html


def test_activity_pill_omits_empty_detail_suffix() -> None:
    html = frontend_source()

    function_start = html.index("function activityPillText(latest)")
    function_end = html.index("function localizedPhase", function_start)
    function_body = html[function_start:function_end]

    assert "localizedActivityLabel(latest.label)" in function_body
    assert "return detail ? `${label}: ${detail}` : label;" in function_body
    assert 'localizedActivityDetail(latest.detail || "").trim()' in function_body


def test_graph_and_reading_runtime_messages_use_i18n_labels() -> None:
    html = frontend_source()

    graph_start = html.index("function loadGraph(preserveSelection = true)")
    graph_end = html.index("function renderGraphDetail()", graph_start)
    graph_body = html[graph_start:graph_end]
    reading_start = html.index("function renderSortMarks()")
    reading_end = html.index("async function openDoc", reading_start)
    reading_body = html[reading_start:reading_end]

    assert 'tr("cluster")' in graph_body
    assert 'tr("graph_need_analysis_once")' in graph_body
    assert 'tr("graph_need_analysis_before_graph")' in graph_body
    assert "renderGraphError(message);" in graph_body
    assert 'trf("graph_task_started"' in graph_body
    assert 'tr("graph_task_start_failed")' in graph_body
    assert 'localGraphTaskLabel(responsePayload.label, taskName)' in graph_body
    assert "graph_can_generate_relationships" not in html
    assert "可直接生成关系" not in html
    assert 'tr("sort_public_desc")' in reading_body
    assert 'tr("mark_failed")' in reading_body
    assert 'tr("select_documents_first")' in reading_body
    assert 'trf("bulk_marked"' in reading_body
    assert 'tr("current_list_empty")' in reading_body

    leaked_runtime_text = [
        "`簇 ${payload.cluster_count}`",
        '"先完成至少一次文档分析"',
        '"先完成一次文档分析，再生成关系图谱"',
        '"可直接生成关系"',
        '"还没有关系结果，可点击“生成关系”"',
        '"还没有图谱结果，可点击“生成图谱”"',
        '"后台任务运行中，完成后这里会显示局部图和证据。"',
        '"生成关系后，这里会显示局部图、证据和文档详情。"',
        '"生成图谱后，这里会显示局部图、证据和文档详情。"',
        '"关系任务启动失败"',
        '"关系簇加载失败"',
        '"公开↓"',
        '"标记失败"',
        '"请先选择文档"',
        '"批量标记失败"',
        '"当前列表为空"',
    ]
    for text in leaked_runtime_text:
        assert text not in graph_body
        assert text not in reading_body

    assert 'graph_need_analysis_once: "Complete at least one document analysis first"' in html
    assert 'graph_need_analysis_before_graph: "Complete one document analysis before generating the graph"' in html
    assert 'graph_task_mine: "Graph generation"' in html
    assert 'graph_phase_scoring_relationships: "Scoring relationships"' in html
    assert 'sort_public_desc: "Public↓"' in html
    assert 'current_list_empty: "The current list is empty"' in html
    assert 'ph_text_search: "Name/path/note"' in html
    assert 'ph_graph_search: "Path/category/tag"' in html


def test_path_and_analysis_action_messages_use_i18n_labels() -> None:
    html = frontend_source()

    action_start = html.index("async function pickFolder(targetId)")
    action_end = html.index("function renderAnalysis(payload)", action_start)
    action_body = html[action_start:action_end]

    assert 'tr("pick_failed")' in action_body
    assert 'tr("paths_apply_failed")' in action_body
    assert 'tr("paths_applied")' in action_body
    assert 'tr("need_reading_output")' in action_body
    assert 'tr("reading_output_apply_failed")' in action_body
    assert 'tr("reading_output_applied")' not in html
    assert 'tr("analysis_start_failed")' in action_body
    assert 'tr("analysis_started")' in action_body
    assert 'tr("analysis_preempting_relationships")' in action_body
    assert 'tr("early_relationships_failed")' in action_body
    assert 'tr("early_relationships_started")' in action_body
    assert 'tr("relationship_stop_requested")' in action_body
    assert 'tr("relationship_stop_failed")' in action_body
    assert 'tr("stop_requested")' in action_body
    assert 'tr("stop_failed")' in action_body
    assert 'tr("need_source_output")' in action_body
    assert 'trf("reset_confirm", {output: outputRoot})' in action_body
    assert 'trf("reset_relationships_confirm", {output: outputRoot})' in action_body
    assert 'clearGraphState("output_reset")' in action_body
    assert 'clearGraphState("relationships_reset")' in action_body
    assert 'tr("relationship_reset_failed")' in action_body
    assert 'tr("relationships_reset")' in action_body
    assert 'tr("reset_relationships_blocked_analysis")' in action_body
    assert 'tr("reset_relationships_blocked_relationships")' in action_body
    assert 'tr("status_load_failed")' in action_body

    leaked_action_text = [
        '"选择失败"',
        '"路径应用失败"',
        '"路径已应用"',
        '"请先输入阅读目标输出目录"',
        '"阅读目录应用失败"',
        '"启动失败"',
        '"已启动分析"',
        '"正在停止生成关系并准备开始分析"',
        '"已请求停止"',
        '"停止失败"',
        '"请先应用源目录和输出目录"',
        '"重置失败"',
        '"重置关系失败"',
        '"状态加载失败"',
    ]
    for text in leaked_action_text:
        assert text not in action_body

    assert 'pick_failed: "Selection failed"' in html
    assert 'reset_relationships: "Reset relationships"' in html
    assert 'reset_confirm: "This will clear logs, status, and relationship results in the output directory:' in html
    assert 'relationships_reset: "Relationship outputs reset"' in html
    assert 'ph_reading_output_root: "Select or enter an analyzed output directory"' in html
    assert 'data-i18n-placeholder="ph_reading_output_root"' in html
    assert 'data-i18n-placeholder="ph_text_search"' in html
    assert 'data-i18n-placeholder="ph_graph_search"' in html


def test_headless_linux_disables_desktop_integrations(monkeypatch) -> None:
    monkeypatch.setattr(reading_ui.os, "name", "posix", raising=False)
    monkeypatch.setattr(reading_ui.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)

    capabilities = reading_ui.environment_capabilities()

    assert capabilities["folder_picker"] is False
    assert capabilities["open_file"] is False
    assert capabilities["reveal_file"] is False
    assert "Manual path input" in capabilities["headless_hint"]


def test_macos_open_and_reveal_use_finder_open(monkeypatch, tmp_path: Path) -> None:
    commands = []
    document = tmp_path / "doc.pdf"

    monkeypatch.setattr(reading_ui.os, "name", "posix", raising=False)
    monkeypatch.setattr(reading_ui.sys, "platform", "darwin")
    monkeypatch.setattr(
        reading_ui.shutil,
        "which",
        lambda name: "/usr/bin/open" if name == "open" else None,
    )
    monkeypatch.setattr(
        reading_ui.subprocess,
        "Popen",
        lambda command, **kwargs: commands.append((command, kwargs)),
    )

    reading_ui.open_path(document)
    reading_ui.reveal_path(document)

    assert commands[0][0] == ["/usr/bin/open", str(document)]
    assert commands[1][0] == ["/usr/bin/open", "-R", str(document)]


def test_linux_open_falls_back_to_gio(monkeypatch, tmp_path: Path) -> None:
    commands = []
    document = tmp_path / "doc.pdf"

    monkeypatch.setattr(reading_ui.os, "name", "posix", raising=False)
    monkeypatch.setattr(reading_ui.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(
        reading_ui.shutil,
        "which",
        lambda name: "/usr/bin/gio" if name == "gio" else None,
    )
    monkeypatch.setattr(
        reading_ui.subprocess,
        "Popen",
        lambda command, **kwargs: commands.append((command, kwargs)),
    )

    assert reading_ui.can_open_file() is True
    reading_ui.open_path(document)

    assert commands[0][0] == ["/usr/bin/gio", "open", str(document)]


def test_linux_without_supported_opener_disables_open(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(reading_ui.os, "name", "posix", raising=False)
    monkeypatch.setattr(reading_ui.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(reading_ui.shutil, "which", lambda name: None)

    assert reading_ui.can_open_file() is False
    with pytest.raises(RuntimeError, match="No supported Linux desktop opener"):
        reading_ui.open_path(tmp_path / "doc.pdf")


def test_windows_folder_picker_uses_powershell(monkeypatch) -> None:
    class Result:
        returncode = 0
        stdout = "C:\\Docs\n"
        stderr = ""

    commands = []

    monkeypatch.setattr(reading_ui.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        reading_ui.shutil,
        "which",
        lambda name: "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
        if name == "powershell"
        else None,
    )
    monkeypatch.setattr(
        reading_ui.subprocess,
        "run",
        lambda command, **kwargs: commands.append((command, kwargs)) or Result(),
    )

    assert reading_ui.can_use_folder_picker() is True
    assert reading_ui.pick_folder() == {"path": "C:\\Docs"}
    assert "-STA" in commands[0][0]


def test_build_relationship_payload_returns_cluster_and_edge_details(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    a = source_dir / "a.md"
    b = source_dir / "b.md"
    a.write_text("a", encoding="utf-8")
    b.write_text("b", encoding="utf-8")
    decisions = [
        {
            "source_path": str(a),
            "relative_path": "a.md",
            "target_path": str(output_root / "HQ" / "Architecture" / "a.md"),
            "status": "planned",
            "quality": 88,
            "category": "Architecture",
            "document_kind": "ArchitectureDecision",
            "topic_tags": ["Agent"],
            "summary": "A summary",
            "sensitivity_risk": 10,
            "public_writing_suitability": 80,
        },
        {
            "source_path": str(b),
            "relative_path": "b.md",
            "target_path": str(output_root / "HQ" / "Research" / "b.md"),
            "status": "planned",
            "quality": 77,
            "category": "Research",
            "document_kind": "ResearchReport",
            "topic_tags": ["RAG"],
            "summary": "B summary",
            "sensitivity_risk": 20,
            "public_writing_suitability": 60,
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")
    (state_dir / "reading_status.jsonl").write_text(
        json.dumps({"relative_path": "a.md", "status": "read"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (relationship_dir / "clusters.json").write_text(
        json.dumps(
            {
                "clusters": [
                    {
                        "size": 2,
                        "categories": ["Architecture", "Research"],
                        "files": [
                            {
                                "relative_path": "a.md",
                                "quality": 88,
                                "category": "Architecture",
                                "document_kind": "ArchitectureDecision",
                                "topic_tags": ["Agent"],
                            },
                            {
                                "relative_path": "b.md",
                                "quality": 77,
                                "category": "Research",
                                "document_kind": "ResearchReport",
                                "topic_tags": ["RAG"],
                            },
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (relationship_dir / "relations.jsonl").write_text(
        json.dumps(
            {
                "left": {"relative_path": "a.md"},
                "right": {"relative_path": "b.md"},
                "relation_score": 0.91,
                "signals": ["path", "citation"],
                "filename_similarity": 0.5,
                "time_proximity": 0.8,
                "path_proximity": 0.95,
                "embedding_similarity": 0.0,
                "type_compatibility": 0.8,
                "citation_count": 1,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (relationship_dir / "progress.json").write_text(
        json.dumps(
            {
                "schema_version": "doctriage_relationship_progress.v1",
                "phase": "scoring_relationships",
                "percent": 45.0,
                "total_records": 2,
                "candidate_relations": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    summary_payload = build_relationship_payload(AppState(), paths, {})
    detail_payload = build_relationship_payload(AppState(), paths, {"cluster": "0"})

    assert summary_payload["cluster_count"] == 1
    assert summary_payload["decisions_exists"] is True
    assert summary_payload["clusters"][0]["preview_paths"] == ["a.md", "b.md"]
    assert summary_payload["progress"]["phase"] == "scoring_relationships"
    assert summary_payload["progress"]["percent"] == 45.0
    assert detail_payload["selected_cluster"]["edge_count"] == 1
    assert detail_payload["selected_cluster"]["files"][0]["summary"] == "A summary"
    assert detail_payload["selected_cluster"]["files"][0]["status"] == "read"
    assert detail_payload["selected_cluster"]["files"][0]["target_path"] == ""
    assert detail_payload["selected_cluster"]["edges"][0]["signals"] == ["path", "citation"]


def test_status_payloads_include_independent_embedding_progress(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    progress = {
        "enabled": True,
        "phase": "embedding",
        "total": 4,
        "cached": 1,
        "generated": 2,
        "completed": 3,
        "missing": 1,
        "percent": 75.0,
    }
    (state_dir / "progress.json").write_text(
        json.dumps({"completed": 1, "total": 10}, ensure_ascii=False),
        encoding="utf-8",
    )
    (relationship_dir / "embedding_progress.json").write_text(
        json.dumps(progress, ensure_ascii=False),
        encoding="utf-8",
    )
    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    app_state = AppState(paths=paths)

    analysis_payload = analysis_status(app_state, paths=paths)
    relationship_payload = build_relationship_payload(app_state, paths, {})

    assert analysis_payload["progress"] == {"completed": 1, "total": 10}
    assert analysis_payload["embedding_progress"] == progress
    assert relationship_payload["embedding_progress"] == progress


def test_analysis_status_reports_resume_phase_from_existing_decisions(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    document.write_text("doc", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {"source_path": str(document), "relative_path": "doc.md", "status": "planned"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "progress.json").write_text(
        json.dumps(
            {"completed": 0, "submitted": 0, "skipped_resumed": 0, "total": 10, "remaining": 10},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text("", encoding="utf-8")

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["phase"] == "已停止，可续传"


def test_analysis_status_reports_completed_relationship_phase(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    document.write_text("doc", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {"source_path": str(document), "relative_path": "doc.md", "status": "planned"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "progress.json").write_text(
        json.dumps({"completed": 1, "total": 1, "remaining": 0}, ensure_ascii=False),
        encoding="utf-8",
    )
    (state_dir / "run_summary.json").write_text(
        json.dumps({"unresolved_failures": 0}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )
    assert payload["phase"] == "分析完成，关系未生成"

    relationship_dir = output_root / "_relationships"
    relationship_dir.mkdir()
    (relationship_dir / "relations.jsonl").write_text("", encoding="utf-8")
    (relationship_dir / "clusters.json").write_text("[]", encoding="utf-8")

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )
    assert payload["phase"] == "分析完成，关系已生成"


def test_analysis_status_reports_activity_when_progress_is_stale(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    document.write_text("doc", encoding="utf-8")
    decision = {
        "source_path": str(document),
        "relative_path": "doc.md",
        "status": "planned",
        "quality": 80,
        "category": "Design",
    }
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(decision, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (state_dir / "processed_files.jsonl").write_text(
        json.dumps({"source_path": str(document)}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (state_dir / "progress.json").write_text(
        json.dumps({"completed": 0, "total": 10, "remaining": 10}, ensure_ascii=False),
        encoding="utf-8",
    )
    run_lock_path(output_root).write_text(
        json.dumps({"pid": 999999}, ensure_ascii=False),
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        "2026-06-02 19:23:29,991 [INFO] doctriage - Planned doc.md -> output [quality=80 category=Design]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: False)

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["running"] is False
    assert payload["run_lock"] == {
        "exists": True,
        "pid": 999999,
        "active": False,
        "source_dir": "",
        "output_root": "",
        "created_epoch": None,
    }
    assert payload["activity"]["state_counts"]["decisions"] == 1
    assert payload["activity"]["state_counts"]["processed"] == 1
    assert payload["activity"]["latest_activity"]["label"] == ""


def test_latest_log_activity_omits_progress_pill() -> None:
    log_tail = (
        "2026-06-05 10:00:00,000 [INFO] doctriage - "
        "Progress 5/30174 (0.0%), rate=7.06 files/min, ETA=71h13m, submitted=9, completed=5\n"
    )

    payload = latest_log_activity(log_tail)

    assert payload["label"] == ""
    assert payload["detail"] == ""
    assert "Progress 5/30174" in payload["line"]


def test_read_text_tail_decodes_legacy_gbk_log_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "doctriage.log"
    gbk_line = (
        "2026-06-05 16:35:54,609 [INFO] doctriage - "
        "Skipping resumed item already materialized: E:\\Docs\\示例资料\\业务中台 - Sample.pdf [processed]\n"
    )
    utf8_line = (
        "2026-06-05 16:36:19,944 [INFO] doctriage - "
        "Planned 服务框架源码学习一@Provider - Sample.pdf [quality=75 category=Implementation]\n"
    )
    log_path.write_bytes(gbk_line.encode("gbk") + utf8_line.encode("utf-8"))

    text = reading_ui.read_text_tail(log_path, max_lines=10)

    assert "示例资料" in text
    assert "业务中台" in text
    assert "服务框架源码学习一@Provider" in text


def test_analysis_status_shows_plan_only_source_paths(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    document.write_text("doc", encoding="utf-8")
    target_path = output_root / "HQ" / "Design" / "doc.md"
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(document),
                "relative_path": "doc.md",
                "target_path": str(target_path),
                "status": "planned",
                "quality": 80,
                "category": "Design",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "progress.json").write_text(
        json.dumps({"plan_only": True, "completed": 1, "total": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        f"2026-06-02 19:23:29,991 [INFO] doctriage - Planned {document} [quality=80 category=Design]\n",
        encoding="utf-8",
    )

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["plan_only"] is True
    assert str(document) in payload["log_tail"]
    assert "HQ" not in payload["log_tail"]
    assert str(target_path) not in payload["log_tail"]
    assert payload["activity"]["latest_activity"]["label"] == ""
    assert payload["activity"]["latest_activity"]["detail"] == ""
    assert str(document) in payload["activity"]["latest_activity"]["line"]
    assert str(target_path) not in payload["activity"]["latest_activity"]["line"]


def test_analysis_status_reports_effective_concurrency(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    command = [
        "python",
        "main.py",
        "--output-root",
        str(output_root.resolve()),
        "--concurrency",
        "4",
    ]
    process = type(
        "FakeProcess",
        (),
        {"pid": 1, "poll": lambda self: None},
    )

    payload = analysis_status(
        AppState(
            paths=ReadingPaths(source_dir=source_dir, output_root=output_root),
            process=process(),
            process_command=command,
        )
    )

    assert payload["effective_concurrency"] == "4"


def test_analysis_status_infers_plan_only_from_progress(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    log_dir = output_root / "_logs"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    document.write_text("doc", encoding="utf-8")
    target_path = output_root / "HQ" / "Design" / "doc.md"
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {"source_path": str(document), "relative_path": "doc.md", "status": "planned"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (state_dir / "progress.json").write_text(
        json.dumps({"plan_only": True, "completed": 1, "total": 1}, ensure_ascii=False),
        encoding="utf-8",
    )
    (log_dir / "doctriage.log").write_text(
        f"2026-06-02 19:23:29,991 [INFO] doctriage - Planned {document} [quality=80 category=Design]\n",
        encoding="utf-8",
    )

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["plan_only"] is True
    assert str(document) in payload["log_tail"]
    assert str(target_path) not in payload["log_tail"]


def test_reset_analysis_output_clears_output_directory(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    (output_root / "_state").mkdir(parents=True)
    (output_root / "_logs").mkdir(parents=True)
    (output_root / "_relationships").mkdir(parents=True)
    (output_root / "HQ" / "Architecture").mkdir(parents=True)
    (output_root / "_state" / "progress.json").write_text("{}", encoding="utf-8")
    (output_root / "_logs" / "doctriage.log").write_text("log", encoding="utf-8")
    (output_root / "_relationships" / "relations.jsonl").write_text("x", encoding="utf-8")
    (output_root / "HQ" / "Architecture" / "doc.pdf").write_text("x", encoding="utf-8")
    app_state = AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))

    payload = reset_analysis_output(
        app_state,
        {"source_dir": str(source_dir), "output_root": str(output_root)},
    )

    assert payload["reset"] is True
    assert sorted(path.name for path in output_root.iterdir()) == ["_logs", "_state"]
    assert app_state.process_command is None


def test_reset_analysis_output_rejects_same_source_and_output(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()

    with pytest.raises(ValueError, match="same"):
        reset_analysis_output(
            AppState(),
            {"source_dir": str(source_dir), "output_root": str(source_dir)},
        )


def test_reset_analysis_output_rejects_output_inside_source(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = source_dir / "output"
    source_dir.mkdir()

    with pytest.raises(ValueError, match="inside the source"):
        reset_analysis_output(
            AppState(),
            {"source_dir": str(source_dir), "output_root": str(output_root)},
        )


def test_reset_analysis_output_rejects_source_inside_output(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    source_dir = output_root / "source"
    source_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match="contains the source"):
        reset_analysis_output(
            AppState(),
            {"source_dir": str(source_dir), "output_root": str(output_root)},
        )
