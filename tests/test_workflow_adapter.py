import json
import argparse
import io
from pathlib import Path

import workflow_adapter
from config import Settings
from ranker_engine import SemanticScore
from workflow_adapter import (
    WorkflowPolicy,
    analyze_document,
    build_dataset_records,
    build_routing,
    iter_input_paths,
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
            summary="This guide explains how to build a RAG workflow with tests and reusable validation steps.",
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


def test_iter_input_paths_does_not_close_stdin(monkeypatch) -> None:
    stdin = io.StringIO('{"path": "a.md"}\nplain.md\n')
    monkeypatch.setattr(workflow_adapter.sys, "stdin", stdin)

    paths = iter_input_paths(argparse.Namespace(file=[], input_jsonl="-"))

    assert [str(path) for path in paths] == ["a.md", "plain.md"]
    assert stdin.closed is False


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
    assert record["text"]["summary"].startswith("This guide explains")
    assert record["workflow"]["routes"]["rag"] is True


def test_analyze_document_closes_owned_llm_client(tmp_path: Path, monkeypatch) -> None:
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
    created_clients: list[object] = []

    class FakeWashedDocument:
        clean_markdown = "# Guide\n\nUse RAG with tests."
        notes: list[str] = []

    class FakeWasher:
        def __init__(self, *, settings):
            self.settings = settings

        def wash(self, path):
            return FakeWashedDocument()

    class FakeProfile:
        def to_llm_payload(self):
            return {}

    class FakeProfiler:
        def __init__(self, *, settings):
            self.settings = settings

        def profile_document(self, path, clean_markdown):
            return FakeProfile()

    class FakeLLMClient:
        def __init__(self, *, settings):
            self.closed = False
            created_clients.append(self)

        def close(self):
            self.closed = True

    class FakeSemanticScoring:
        def __init__(self, *, llm_client):
            self.llm_client = llm_client

        def score_document(self, file_path, clean_markdown, profile, manifest):
            return SemanticScore(
                quality=86,
                category="Implementation",
                document_kind="ImplementationGuide",
                topic_tags=["RAG"],
                summary="This guide explains how to build a RAG workflow.",
                reason="usable",
            )

    monkeypatch.setattr(workflow_adapter, "DocumentWasher", FakeWasher)
    monkeypatch.setattr(workflow_adapter, "MetadataProfiler", FakeProfiler)
    monkeypatch.setattr(workflow_adapter, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(workflow_adapter, "SemanticScoring", FakeSemanticScoring)

    record = analyze_document(
        document,
        settings=settings,
        source_root=source_dir,
    )

    assert record["ok"] is True
    assert len(created_clients) == 1
    assert created_clients[0].closed is True
