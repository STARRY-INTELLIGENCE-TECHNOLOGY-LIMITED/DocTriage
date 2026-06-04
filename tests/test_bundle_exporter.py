import json
from pathlib import Path

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
    assert payload["schema_version"] == "doctriage_bundle.v1"
    assert payload["statistics"]["document_count"] == 2
    assert payload["statistics"]["relation_count"] == 1
    assert [item["relative_path"] for item in payload["documents"]] == [
        "first.md",
        "second.md",
    ]


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
