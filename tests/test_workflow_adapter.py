import json
from pathlib import Path

from config import Settings
from ranker_engine import SemanticScore
from workflow_adapter import (
    WorkflowPolicy,
    analyze_document,
    build_dataset_records,
    build_routing,
    selection_for_purpose,
)


class StubScorer:
    def score_document(self, file_path, clean_markdown, profile, manifest):
        return SemanticScore(
            quality=86,
            category="Implementation",
            document_kind="ImplementationGuide",
            topic_tags=["RAG"],
            knowledge_density=80,
            implementation_specificity=78,
            logical_structure=70,
            evidence_richness=75,
            actionability=82,
            strategic_value=65,
            freshness=60,
            uniqueness=72,
            sensitivity_risk=18,
            public_writing_suitability=84,
            reason="usable",
        )


def test_build_routing_marks_purposes() -> None:
    routing = build_routing(
        {
            "quality": 88,
            "actionability": 80,
            "evidence_richness": 75,
            "uniqueness": 70,
            "sensitivity_risk": 20,
            "public_writing_suitability": 85,
        },
        WorkflowPolicy(),
    )

    assert routing["routes"]["rag"] is True
    assert routing["routes"]["pretraining"] is True
    assert routing["routes"]["sft"] is True
    assert routing["routes"]["public_writing"] is True
    assert routing["recommended_uses"] == [
        "rag",
        "pretraining",
        "sft",
        "public_writing",
    ]


def test_build_routing_blocks_sensitive_public_uses() -> None:
    routing = build_routing(
        {
            "quality": 92,
            "actionability": 90,
            "evidence_richness": 90,
            "uniqueness": 90,
            "sensitivity_risk": 80,
            "public_writing_suitability": 90,
        },
        WorkflowPolicy(),
    )

    assert routing["routes"]["rag"] is False
    assert routing["routes"]["pretraining"] is False
    assert routing["routes"]["sft"] is False
    assert routing["routes"]["public_writing"] is False


def test_selection_for_public_writing_uses_public_thresholds() -> None:
    policy = WorkflowPolicy(public_max_sensitivity_risk=25, public_min_writing_suitability=75)

    selection = selection_for_purpose("public_writing", policy)

    assert selection.max_sensitivity_risk == 25
    assert selection.min_public_writing_suitability == 75


def test_build_dataset_records_filters_by_purpose(tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    state_dir.mkdir(parents=True)
    decisions_path = state_dir / "decisions.jsonl"
    rows = [
        {
            "source_path": str(tmp_path / "public.md"),
            "relative_path": "public.md",
            "status": "planned",
            "quality": 90,
            "category": "Architecture",
            "actionability": 80,
            "evidence_richness": 80,
            "uniqueness": 70,
            "sensitivity_risk": 20,
            "public_writing_suitability": 90,
        },
        {
            "source_path": str(tmp_path / "sensitive.md"),
            "relative_path": "sensitive.md",
            "status": "planned",
            "quality": 95,
            "category": "Architecture",
            "actionability": 90,
            "evidence_richness": 90,
            "uniqueness": 90,
            "sensitivity_risk": 90,
            "public_writing_suitability": 95,
        },
    ]
    with decisions_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    records = build_dataset_records(decisions_path, purpose="public_writing")

    assert len(records) == 1
    assert records[0]["relative_path"] == "public.md"
    assert records[0]["include"] is True
    assert records[0]["workflow"]["routes"]["public_writing"] is True


def test_analyze_document_returns_machine_readable_record(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "guide.md"
    document.write_text("# Guide\n\nUse RAG with tests.", encoding="utf-8")
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="stub",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        OCR_ENABLED=False,
        DOCUMENT_SUMMARY_ENABLED=True,
    )

    record = analyze_document(
        document,
        settings=settings,
        source_root=source_dir,
        scorer=StubScorer(),
    )

    assert record["schema_version"] == "doctriage_file_analysis.v1"
    assert record["ok"] is True
    assert record["relative_path"] == "guide.md"
    assert record["triage"]["quality"] == 86
    assert record["workflow"]["routes"]["rag"] is True
