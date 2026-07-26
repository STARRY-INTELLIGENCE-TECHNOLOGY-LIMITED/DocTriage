import json
from pathlib import Path

import pytest

from bundle_exporter import BundleSelection, export_bundle, load_latest_decisions
from config import Settings


def test_export_bundle_filters_and_includes_relations(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    first = source_dir / "first.md"
    second = source_dir / "second.md"
    low = source_dir / "low.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    low.write_text("low", encoding="utf-8")

    decisions = [
        {
            "source_path": str(first),
            "relative_path": "first.md",
            "target_path": str(output_root / "HQ" / "Architecture" / "first.md"),
            "status": "planned",
            "quality": 92,
            "category": "Architecture",
            "knowledge_density": 90,
            "implementation_specificity": 80,
            "logical_structure": 85,
            "reason": "useful",
            "summary": "first summary",
        },
        {
            "source_path": str(second),
            "relative_path": "second.md",
            "target_path": str(output_root / "HQ" / "Thinking" / "second.md"),
            "status": "planned",
            "quality": 88,
            "category": "Thinking",
            "summary": "second summary",
        },
        {
            "source_path": str(low),
            "relative_path": "low.md",
            "target_path": str(output_root / "LQ_Archive" / "low.md"),
            "status": "planned",
            "quality": 30,
            "category": "LowQuality",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    relation = {
        "left": {"relative_path": "first.md"},
        "right": {"relative_path": "second.md"},
        "relation_score": 0.9,
        "signals": ["filename", "category"],
    }
    (relationship_dir / "relations.jsonl").write_text(
        json.dumps(relation, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )

    output_path = export_bundle(
        settings,
        title="Selected",
        selection=BundleSelection(
            min_quality=80,
            categories={"Architecture", "Thinking"},
        ),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "doctriage_bundle.v2"
    assert payload["statistics"]["document_count"] == 2
    assert payload["statistics"]["relation_count"] == 1
    assert [item["paths"]["relative"] for item in payload["documents"]] == [
        "first.md",
        "second.md",
    ]
    assert payload["documents"][0]["classification"]["category"] == "Architecture"
    assert payload["documents"][0]["scores"]["quality"] == 92
    assert payload["documents"][0]["text"]["summary"] == "first summary"
    assert payload["relations"][0]["left_document_id"] == payload["documents"][0]["id"]
    assert payload["relations"][0]["right_document_id"] == payload["documents"][1]["id"]
    assert payload["relations"][0]["score"] == 0.9
    assert payload["relations"][0]["signals"] == ["filename", "category"]


def test_bundle_ignores_non_terminal_decisions_and_dedupes_by_relative_path(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    state_dir.mkdir(parents=True)
    decisions_path = state_dir / "decisions.jsonl"
    decisions = [
        {
            "source_path": str(tmp_path / "old-source" / "doc.md"),
            "relative_path": "doc.md",
            "status": "copy_candidate",
            "quality": 20,
            "category": "LowQuality",
        },
        {
            "source_path": str(tmp_path / "first-source" / "doc.md"),
            "relative_path": "doc.md",
            "status": "planned",
            "quality": 80,
            "category": "Design",
        },
        {
            "source_path": str(tmp_path / "second-source" / "doc.md"),
            "relative_path": "doc.md",
            "status": "planned",
            "quality": 90,
            "category": "Architecture",
        },
    ]
    with decisions_path.open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    latest = load_latest_decisions(decisions_path)

    assert len(latest) == 1
    assert latest[0]["quality"] == 90
    assert latest[0]["category"] == "Architecture"


def test_bundle_includes_low_quality_unless_explicitly_excluded(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    state_dir.mkdir(parents=True)
    source_dir.mkdir()
    decisions = [
        {
            "source_path": str(source_dir / "good.md"),
            "relative_path": "good.md",
            "status": "planned",
            "quality": 20,
            "category": "Thinking",
            "summary": "keep this metadata",
        },
        {
            "source_path": str(source_dir / "low.md"),
            "relative_path": "low.md",
            "status": "planned",
            "quality": 99,
            "category": "LowQuality",
            "summary": "exclude by category",
        },
    ]
    (state_dir / "decisions.jsonl").write_text(
        "\n".join(json.dumps(item) for item in decisions),
        encoding="utf-8",
    )

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    payload = json.loads(export_bundle(settings).read_text(encoding="utf-8"))

    assert {
        item["paths"]["relative"] for item in payload["documents"]
    } == {"good.md", "low.md"}
    assert payload["selection_policy"]["exclude_categories"] == []

    filtered_path = export_bundle(
        settings,
        selection=BundleSelection(exclude_categories={"LowQuality"}),
    )
    filtered = json.loads(filtered_path.read_text(encoding="utf-8"))
    assert [item["paths"]["relative"] for item in filtered["documents"]] == [
        "good.md"
    ]
    assert filtered["selection_policy"]["exclude_categories"] == ["LowQuality"]


def test_bundle_reports_failed_relationship_phase_as_optional_advisory(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    relationship_dir = output_root / "_relationships"
    state_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)
    source_dir.mkdir()
    decision = {
        "source_path": str(source_dir / "note.md"),
        "relative_path": "note.md",
        "status": "planned",
        "quality": 90,
        "category": "Thinking",
        "summary": "summary",
    }
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(decision), encoding="utf-8"
    )
    (relationship_dir / "progress.json").write_text(
        json.dumps({"phase": "error", "error": "embedding unavailable"}),
        encoding="utf-8",
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )

    output_path = export_bundle(settings)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["pipeline_status"]["relations"] == "error"
    assert payload["is_partial"] is False
    assert payload["warnings"] == []
    assert any("failed" in item.lower() for item in payload["advisories"])
    assert payload["artifacts"]["relations"]["exists"] is False


def test_bundle_payload_exposes_pipeline_and_artifact_metadata(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    state_dir.mkdir(parents=True)
    source_dir.mkdir()
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(source_dir / "note.md"),
                "relative_path": "note.md",
                "status": "planned",
                "quality": 90,
                "category": "Thinking",
                "summary": "summary",
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    payload = json.loads(export_bundle(settings).read_text(encoding="utf-8"))

    assert set(payload) >= {
        "pipeline_status",
        "is_partial",
        "warnings",
        "advisories",
        "artifacts",
    }
    assert payload["pipeline_status"] == {
        "analysis": "unknown",
        "relations": "not_run",
        "rag": "not_run",
    }
    assert payload["is_partial"] is False
    assert any("RAG" in item for item in payload["advisories"])
    assert payload["artifacts"]["decisions"]["exists"] is True


def test_bundle_marks_analysis_partial_when_failures_remain(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    state_dir.mkdir(parents=True)
    source_dir.mkdir()
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(source_dir / "note.md"),
                "relative_path": "note.md",
                "status": "planned",
                "quality": 90,
                "category": "Thinking",
                "summary": "summary",
            }
        ),
        encoding="utf-8",
    )
    (state_dir / "run_summary.json").write_text(
        json.dumps({"failed": 149, "unresolved_failures": 149}),
        encoding="utf-8",
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )

    payload = json.loads(export_bundle(settings).read_text(encoding="utf-8"))

    assert payload["pipeline_status"]["analysis"] == "partial"
    assert payload["is_partial"] is True
    assert any("149 unresolved" in warning for warning in payload["warnings"])
