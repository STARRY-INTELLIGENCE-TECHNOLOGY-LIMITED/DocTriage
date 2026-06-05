import json
from pathlib import Path

from reading_tracker import (
    ReadingPaths,
    append_reading_event,
    build_reading_rows,
    filter_rows,
    load_latest_decisions,
    load_latest_reading_events,
)


def test_reading_tracker_marks_read_without_moving_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    document = source_dir / "architecture.md"
    document.write_text("# Architecture", encoding="utf-8")

    decision = {
        "source_path": str(document),
        "relative_path": "architecture.md",
        "status": "planned",
        "quality": 91,
        "category": "Architecture",
        "document_kind": "ArchitectureDecision",
        "topic_tags": ["DistributedSystems"],
        "summary": "Architecture summary",
        "reason": "Dense architectural reasoning",
        "knowledge_density": 86,
        "implementation_specificity": 78,
        "logical_structure": 82,
        "evidence_richness": 74,
        "actionability": 80,
        "strategic_value": 76,
        "freshness": 68,
        "uniqueness": 71,
        "target_path": str(output_root / "HQ" / "Architecture" / "architecture.md"),
        "fingerprint": {"size_bytes": 14, "mtime_ns": 1},
    }
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(decision, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    decisions = load_latest_decisions(paths.decisions_path)
    append_reading_event(
        paths,
        decisions,
        requested_path="architecture.md",
        status="read",
        note="good",
    )

    rows = build_reading_rows(
        decisions,
        load_latest_reading_events(paths.reading_status_path),
    )

    assert document.exists()
    assert rows[0]["status"] == "read"
    assert rows[0]["quality"] == 91
    assert rows[0]["display_name"] == "architecture.md"
    assert rows[0]["target_path"] == ""
    assert rows[0]["summary"] == "Architecture summary"
    assert rows[0]["reason"] == "Dense architectural reasoning"
    assert rows[0]["knowledge_density"] == 86
    assert rows[0]["implementation_specificity"] == 78
    assert rows[0]["logical_structure"] == 82
    assert rows[0]["evidence_richness"] == 74
    assert rows[0]["actionability"] == 80
    assert rows[0]["strategic_value"] == 76
    assert rows[0]["freshness"] == 68
    assert rows[0]["uniqueness"] == 71
    assert rows[0]["topic_tags"] == ["DistributedSystems"]


def test_reading_tracker_flags_reread_when_decision_fingerprint_changes(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    document = source_dir / "doc.md"
    document.write_text("first", encoding="utf-8")

    decisions_path = state_dir / "decisions.jsonl"
    old_decision = {
        "source_path": str(document),
        "relative_path": "doc.md",
        "status": "planned",
        "quality": 80,
        "category": "Design",
        "fingerprint": {"size_bytes": 5, "mtime_ns": 1},
    }
    new_decision = {
        **old_decision,
        "quality": 88,
        "fingerprint": {"size_bytes": 6, "mtime_ns": 2},
    }
    with decisions_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(old_decision, ensure_ascii=False) + "\n")

    paths = ReadingPaths(source_dir=source_dir, output_root=output_root)
    decisions = load_latest_decisions(paths.decisions_path)
    append_reading_event(
        paths,
        decisions,
        requested_path=str(document),
        status="read",
    )

    with decisions_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(new_decision, ensure_ascii=False) + "\n")

    rows = build_reading_rows(
        load_latest_decisions(paths.decisions_path),
        load_latest_reading_events(paths.reading_status_path),
    )

    assert rows[0]["status"] == "reread_needed"
    assert rows[0]["quality"] == 88


def test_filter_unread_high_quality_public_candidates(tmp_path: Path) -> None:
    rows = [
        {
            "relative_path": "a.md",
            "status": "unread",
            "quality": 90,
            "category": "CaseStudy",
            "sensitivity_risk": 20,
            "public_writing_suitability": 85,
        },
        {
            "relative_path": "b.md",
            "status": "read",
            "quality": 95,
            "category": "CaseStudy",
            "sensitivity_risk": 10,
            "public_writing_suitability": 90,
        },
        {
            "relative_path": "c.md",
            "status": "unread",
            "quality": 92,
            "category": "CaseStudy",
            "sensitivity_risk": 80,
            "public_writing_suitability": 30,
        },
    ]

    filtered = filter_rows(
        rows,
        status="unread",
        min_quality=85,
        categories={"CaseStudy"},
        max_sensitivity_risk=35,
        min_public_writing_suitability=70,
    )

    assert [row["relative_path"] for row in filtered] == ["a.md"]
