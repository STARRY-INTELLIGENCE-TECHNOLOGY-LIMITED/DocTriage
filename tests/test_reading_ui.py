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
    build_relationship_payload,
    build_state_payload,
    config_payload,
    infer_source_dir_from_decisions,
    load_run_history,
    mark_document,
    mark_documents,
    reset_analysis_output,
    run_lock_path,
    row_matches_query,
    set_reading_output,
    sort_rows,
    start_analysis,
    stop_analysis,
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
            "document_kind": "ArchitectureDecision",
            "topic_tags": ["DistributedSystems"],
            "sensitivity_risk": 20,
            "public_writing_suitability": 80,
            "summary": "Alpha architecture summary",
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
    assert payload["rows"][0]["summary"] == "Alpha architecture summary"


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


def test_row_matches_query_checks_path_kind_tags_and_note() -> None:
    row = {
        "relative_path": "foo/bar.pdf",
        "category": "Research",
        "document_kind": "ResearchReport",
        "topic_tags": ["Agent", "RAG"],
        "note": "great for writing",
    }

    assert row_matches_query(row, "agent")
    assert row_matches_query(row, "researchreport")
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
        },
        tmp_path / "source",
        tmp_path / "output",
    )

    assert "--source-dir" in command
    assert "--output-root" in command
    assert "--llm-model" in command
    assert "local-model" in command
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


def test_reading_table_uses_name_column_with_summary_tooltip() -> None:
    html = reading_ui.HTML_PAGE

    assert 'setSort(\'path\')">名称' in html
    assert "doc-name" in html
    assert '${escapeHtml(row.relative_path || "")}</span>' in html
    assert 'data-tip="${escapeAttrValue(row.summary || "")}"' in html
    assert "bindSummaryTooltips();" in html


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
