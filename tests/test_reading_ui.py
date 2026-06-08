import json
from pathlib import Path

import pytest

import reading_ui
from reading_tracker import ReadingPaths
from reading_ui import (
    AppState,
    analysis_status,
    append_run_history,
    build_analysis_command,
    build_failure_rows,
    build_relationship_payload,
    build_state_payload,
    config_payload,
    infer_source_dir_from_decisions,
    load_run_history,
    mark_document,
    mark_documents,
    open_failure_document,
    reading_paths_from_payload,
    reset_analysis_output,
    relationship_task_command,
    run_lock_path,
    row_matches_query,
    set_reading_output,
    sort_rows,
    start_analysis,
    start_relationship_task,
    stop_analysis,
    latest_log_activity,
)


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
        {"relative_path": "a.md", "quality": 90},
        {"relative_path": "b.md", "quality": 80},
    ]

    sorted_rows = sort_rows(rows, "path_desc")

    assert [row["relative_path"] for row in sorted_rows] == ["b.md", "a.md"]


def test_build_analysis_command_includes_selected_flags(tmp_path: Path) -> None:
    command = build_analysis_command(
        {
            "llm_endpoint": "http://localhost:11434/api/generate",
            "llm_model": "local-model",
            "output_language": "en",
            "embedding_model": "nomic-embed-text",
            "concurrency": "1",
            "limit": "10",
            "plan_only": True,
            "no_ocr": True,
            "skip_manifest_analysis": True,
            "document_summary": True,
            "require_local_llm": True,
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
    assert "--embedding-model" in command
    assert "nomic-embed-text" in command
    assert "--limit" in command
    assert "--plan-only" in command
    assert "--no-ocr" in command
    assert "--skip-manifest-analysis" in command
    assert "--document-summary" in command
    assert "--require-local-llm" in command
    assert "--mine-relationships" in command
    assert "--relationship-use-text-citations" in command
    assert "--relationship-use-embeddings" in command


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
            "embedding_model": "nomic-embed-text",
            "relationship_use_embeddings": True,
            "relationship_use_text_citations": True,
        },
        paths,
    )

    assert "--use-embeddings" in command
    assert "--embedding-model" in command
    assert "nomic-embed-text" in command
    assert "--use-text-citations" in command


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
    assert app_state.paths is not None
    assert app_state.paths.source_dir == analysis_source
    assert app_state.paths.output_root == analysis_output


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
    append_run_history(
        output_root,
        {"run_id": "1", "pid": 24680, "command": ["python", "main.py"]},
    )
    monkeypatch.setattr(reading_ui, "is_process_alive", lambda pid: pid == 24680)

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["running"] is True
    assert payload["pid"] == 24680
    assert payload["command"] == ["python", "main.py"]


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


def test_run_history_round_trip(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    append_run_history(output_root, {"run_id": "1", "pid": 1})
    append_run_history(output_root, {"run_id": "2", "pid": 2})

    history = load_run_history(output_root, limit=1)

    assert history == [{"run_id": "2", "pid": 2}]


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
    assert "folder_picker" in payload["capabilities"]
    assert "open_file" in payload["capabilities"]
    assert "reveal_file" in payload["capabilities"]


def test_analysis_form_exposes_help_tooltips_for_run_options() -> None:
    html = reading_ui.HTML_PAGE

    assert "挖掘关系" in html
    assert "输出到 _relationships/relations.jsonl 与 clusters.json" in html
    assert "建议在首轮评分稳定后、关系质量比速度更重要时再勾选" in html
    assert "内容检测除了时间和大小，还计算文件内容哈希" not in html
    assert "变更检测除了时间和大小，还计算文件内容哈希" in html
    assert 'id="run_embedding_model"' in html
    assert 'id="toggle_advanced_btn"' in html
    assert "重置分析" in html
    assert "关系图谱" in html
    assert 'id="graphClusters"' in html
    assert 'visible ? "grid" : "none"' in html
    assert (
        'setInterval(() => {\n'
        '      if ($("section-analysis").classList.contains("active")) loadAnalysis();\n'
        '    }, 3000);'
    ) in html


def test_frontend_status_and_graph_requests_include_current_paths() -> None:
    html = reading_ui.HTML_PAGE

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
    assert "body: JSON.stringify({...runPayload(), ...graphPathPayload()})" in html
    assert 'const response = await fetch("/api/state?" + readingParams());' in html
    assert 'query.set("cluster", String(clusterId));' in html
    assert 'pairs.set("source_dir", paths.source_dir);' in html
    assert 'pairs.set("output_root", paths.output_root);' in html


def test_reading_output_does_not_backfill_analysis_paths() -> None:
    html = reading_ui.HTML_PAGE

    apply_start = html.index("async function applyReadingOutput()")
    apply_end = html.index("function runPayload()", apply_start)
    apply_body = html[apply_start:apply_end]

    assert '$("run_output_root").value = outputRoot' not in apply_body
    assert 'if (payload.source_dir) $("run_source_dir").value = payload.source_dir' not in apply_body
    assert 'if (payload.output_root) $("run_output_root").value = payload.output_root' not in apply_body
    assert 'setReadingTarget(payload.source_dir || "", payload.output_root || outputRoot);' in apply_body
    assert "function readingPathPayload()" in html
    assert "function readingParams()" in html
    assert 'const paths = readingPathPayload();' in html
    assert 'if (id === "run_output_root") syncReadingTargetFromRunOutput({force: true});' in html
    assert 'if (targetId === "reading_output_root") {' in html
    assert 'syncGraphTargetFrom("", payload.path || "", {force: true});' in html
    assert 'body: JSON.stringify({relative_path: relativePath, status, note, ...readingPathPayload()})' in html
    assert 'body: JSON.stringify({relative_paths: paths, status, ...readingPathPayload()})' in html


def test_graph_output_does_not_backfill_analysis_or_reading_paths() -> None:
    html = reading_ui.HTML_PAGE

    apply_start = html.index("async function applyGraphOutput()")
    apply_end = html.index("function runPayload()", apply_start)
    apply_body = html[apply_start:apply_end]
    graph_input_start = html.index("function initGraphTargetPersistence()")
    graph_input_end = html.index("function setUiLanguage", graph_input_start)
    graph_input_body = html[graph_input_start:graph_input_end]
    pick_start = html.index("async function pickFolder(targetId)")
    pick_end = html.index("async function applyPaths()", pick_start)
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
    assert 'if (targetId === "graph_output_root") {' in pick_body
    assert 'graphSourceDir = "";' in pick_body
    assert "saveGraphTargetState();" in pick_body
    assert "syncGraphTargetFrom" not in graph_pick_body
    assert "initGraphTargetPersistence();" in html
    assert "syncGraphTargetFromReadingOutput({force: true});" in html


def test_analysis_run_form_persists_previous_values() -> None:
    html = reading_ui.HTML_PAGE

    assert 'const RUN_FORM_STORAGE_KEY = "doctriage_run_form";' in html
    assert "function readStoredRunFormState()" in html
    assert "function applyStoredRunFormState()" in html
    assert "function saveRunFormState()" in html
    assert "function initRunFormPersistence()" in html
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
        "run_template",
        "run_document_summary",
        "run_plan_only",
        "run_no_ocr",
        "run_skip_manifest",
        "run_require_local_llm",
        "run_force_reprocess",
        "run_content_hash",
        "run_mine_relationships",
        "run_relationship_text",
        "run_relationship_embeddings",
    ]:
        assert f'"{field_id}"' in html
    assert html.count("applyStoredRunFormState();") >= 2
    assert "initRunFormPersistence();" in html
    assert 'if (targetId.startsWith("run_")) saveRunFormState();' in html
    assert 'if (id === "run_relationship_embeddings") syncEmbeddingModelVisibility();' in html
    assert 'saveRunFormState();\n      const response = await fetch("/api/analysis/start"' in html


def test_reading_table_uses_name_column_with_summary_tooltip() -> None:
    html = reading_ui.HTML_PAGE

    assert 'setSort(\'path\')"><span data-i18n="table_name">名称' in html
    assert "doc-name" in html
    assert '${escapeHtml(row.relative_path || "")}</span>' in html
    assert "function rowExplanation(row)" in html
    assert 'data-tip="${escapeAttrValue(explanation)}"' in html
    assert 'tr("explain_reason")' in html
    assert "EXPLANATION_DIMENSIONS" in html
    assert "bindSummaryTooltips();" in html


def test_reading_table_exports_filtered_rows_with_explainability_fields() -> None:
    html = reading_ui.HTML_PAGE

    assert "exportFilteredRows('csv')" in html
    assert "exportFilteredRows('jsonl')" in html
    assert "function rowsToCsv(rows)" in html
    assert "function rowsToJsonl(rows)" in html
    assert "knowledge_density: row.knowledge_density" in html
    assert '"knowledge_density"' in html
    assert '"implementation_specificity"' in html
    assert "exported_rows" in html


def test_reading_table_stores_sort_per_scope() -> None:
    html = reading_ui.HTML_PAGE

    assert "function sortStorageKey(scope)" in html
    assert "doctriage_reading_sort_source" in html
    assert "doctriage_reading_sort_analysis" in html


def test_analysis_status_pills_use_i18n_labels() -> None:
    html = reading_ui.HTML_PAGE

    render_start = html.index("function renderAnalysis(payload)")
    render_end = html.index("function shortText", render_start)
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


def test_activity_pill_omits_empty_detail_suffix() -> None:
    html = reading_ui.HTML_PAGE

    function_start = html.index("function activityPillText(latest)")
    function_end = html.index("function localizedPhase", function_start)
    function_body = html[function_start:function_end]

    assert "localizedActivityLabel(latest.label)" in function_body
    assert "return detail ? `${label}: ${shortText(detail, 72)}` : label;" in function_body
    assert 'localizedActivityDetail(latest.detail || "").trim()' in function_body


def test_graph_and_reading_runtime_messages_use_i18n_labels() -> None:
    html = reading_ui.HTML_PAGE

    graph_start = html.index("function loadGraph(preserveSelection = true)")
    graph_end = html.index("function renderGraphDetail()", graph_start)
    graph_body = html[graph_start:graph_end]
    reading_start = html.index("function renderSortMarks()")
    reading_end = html.index("async function openDoc", reading_start)
    reading_body = html[reading_start:reading_end]

    assert 'tr("cluster")' in graph_body
    assert 'tr("graph_need_analysis_once")' in graph_body
    assert 'tr("graph_need_analysis_before_graph")' in graph_body
    assert 'trf("graph_task_started"' in graph_body
    assert 'tr("graph_task_start_failed")' in graph_body
    assert 'localGraphTaskLabel(payload.label, taskName)' in graph_body
    assert 'tr("sort_public_desc")' in reading_body
    assert 'tr("mark_failed")' in reading_body
    assert 'tr("select_documents_first")' in reading_body
    assert 'trf("bulk_marked"' in reading_body
    assert 'tr("current_list_empty")' in reading_body

    leaked_runtime_text = [
        "`簇 ${payload.cluster_count}`",
        '"先完成至少一次文档分析"',
        '"先完成一次文档分析，再生成关系图谱"',
        '"可直接生成关系结果"',
        '"还没有关系结果，可点击“生成关系结果”"',
        '"后台任务运行中，完成后这里会显示局部图和证据。"',
        '"生成关系结果后，这里会显示局部图、证据和文档详情。"',
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
    assert 'graph_task_mine: "Relationship generation"' in html
    assert 'sort_public_desc: "Public↓"' in html
    assert 'current_list_empty: "The current list is empty"' in html
    assert 'ph_text_search: "Name/path/note"' in html
    assert 'ph_graph_search: "Path/category/tag"' in html


def test_path_and_analysis_action_messages_use_i18n_labels() -> None:
    html = reading_ui.HTML_PAGE

    action_start = html.index("async function pickFolder(targetId)")
    action_end = html.index("function renderAnalysis(payload)", action_start)
    action_body = html[action_start:action_end]

    assert 'tr("pick_failed")' in action_body
    assert 'tr("paths_apply_failed")' in action_body
    assert 'tr("paths_applied")' in action_body
    assert 'tr("need_reading_output")' in action_body
    assert 'tr("reading_output_apply_failed")' in action_body
    assert 'tr("reading_output_applied")' in action_body
    assert 'tr("template_applied")' in action_body
    assert 'tr("analysis_start_failed")' in action_body
    assert 'tr("analysis_started")' in action_body
    assert 'tr("stop_requested")' in action_body
    assert 'tr("stop_failed")' in action_body
    assert 'tr("need_source_output")' in action_body
    assert 'trf("reset_confirm", {output: outputRoot})' in action_body
    assert 'clearGraphState("output_reset")' in action_body
    assert 'tr("status_load_failed")' in action_body

    leaked_action_text = [
        '"选择失败"',
        '"路径应用失败"',
        '"路径已应用"',
        '"请先输入阅读目标输出目录"',
        '"阅读目录应用失败"',
        '"阅读目录已应用"',
        '"已应用模板"',
        '"启动失败"',
        '"已启动分析"',
        '"已请求停止"',
        '"停止失败"',
        '"请先应用源目录和输出目录"',
        '"重置失败"',
        '"状态加载失败"',
    ]
    for text in leaked_action_text:
        assert text not in action_body

    assert 'pick_failed: "Selection failed"' in html
    assert 'reset_confirm: "This will clear logs, status, and relationship results in the output directory:' in html
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

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    summary_payload = build_relationship_payload(AppState(), paths, {})
    detail_payload = build_relationship_payload(AppState(), paths, {"cluster": "0"})

    assert summary_payload["cluster_count"] == 1
    assert summary_payload["decisions_exists"] is True
    assert summary_payload["clusters"][0]["preview_paths"] == ["a.md", "b.md"]
    assert detail_payload["selected_cluster"]["edge_count"] == 1
    assert detail_payload["selected_cluster"]["files"][0]["summary"] == "A summary"
    assert detail_payload["selected_cluster"]["files"][0]["status"] == "read"
    assert detail_payload["selected_cluster"]["files"][0]["target_path"] == ""
    assert detail_payload["selected_cluster"]["edges"][0]["signals"] == ["path", "citation"]


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
    assert payload["activity"]["latest_activity"]["label"] == "已规划"


def test_latest_log_activity_suppresses_progress_detail() -> None:
    log_tail = (
        "2026-06-05 10:00:00,000 [INFO] doctriage - "
        "Progress 5/30174 (0.0%), rate=7.06 files/min, ETA=71h13m, submitted=9, completed=5\n"
    )

    payload = latest_log_activity(log_tail)

    assert payload["label"] == "进度写入"
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


def test_analysis_status_redacts_plan_only_target_paths(tmp_path: Path) -> None:
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
    append_run_history(
        output_root,
        {"pid": 1, "command": ["python", "main.py", "--plan-only"]},
    )
    (log_dir / "doctriage.log").write_text(
        f"2026-06-02 19:23:29,991 [INFO] doctriage - Planned doc.md -> {target_path} [quality=80 category=Design]\n",
        encoding="utf-8",
    )

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["plan_only"] is True
    assert "HQ" not in payload["log_tail"]
    assert str(target_path) not in payload["log_tail"]
    assert payload["activity"]["latest_activity"]["detail"] == (
        "doc.md [quality=80 category=Design]"
    )
    assert str(target_path) not in payload["activity"]["latest_activity"]["line"]


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
        f"2026-06-02 19:23:29,991 [INFO] doctriage - Planned doc.md -> {target_path} [quality=80 category=Design]\n",
        encoding="utf-8",
    )

    payload = analysis_status(
        AppState(paths=ReadingPaths(source_dir=source_dir, output_root=output_root))
    )

    assert payload["plan_only"] is True
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
