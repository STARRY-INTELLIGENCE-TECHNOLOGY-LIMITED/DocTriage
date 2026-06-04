import json
from pathlib import Path

from config import Settings
import relationship_miner
from relationship_miner import (
    build_candidate_relations,
    collect_candidate_pairs,
    collect_citation_pairs,
    load_records,
    mine_relationships,
    resolve_relationship_workers,
)


def test_mine_relationships_without_embeddings(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)

    first = source_dir / "Project Alpha v1 Design.pdf"
    second = source_dir / "Project Alpha v2 Design.pdf"
    third = source_dir / "Unrelated Notes.pdf"
    for path in (first, second, third):
        path.write_text("placeholder", encoding="utf-8")

    decisions = [
        {
            "source_path": str(first),
            "relative_path": first.name,
            "target_path": str(output_root / "HQ" / "Design" / first.name),
            "quality": 85,
            "category": "Design",
            "reason": "design document",
            "summary": "project alpha service design",
        },
        {
            "source_path": str(second),
            "relative_path": second.name,
            "target_path": str(output_root / "HQ" / "Design" / second.name),
            "quality": 88,
            "category": "Design",
            "reason": "updated design document",
            "summary": "project alpha service design update",
        },
        {
            "source_path": str(third),
            "relative_path": third.name,
            "target_path": str(output_root / "HQ" / "Thinking" / third.name),
            "quality": 75,
            "category": "Thinking",
            "reason": "notes",
            "summary": "unrelated reflections",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for item in decisions:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_USE_EMBEDDINGS=False,
        RELATIONSHIP_MIN_SCORE=0.5,
    )

    mine_relationships(settings)

    relations_path = output_root / "_relationships" / "relations.jsonl"
    clusters_path = output_root / "_relationships" / "clusters.json"
    assert relations_path.exists()
    assert clusters_path.exists()
    assert "Project Alpha" in relations_path.read_text(encoding="utf-8")

    clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    assert clusters["clusters"]


def test_relationship_records_use_latest_decision(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    file_path = source_dir / "doc.md"
    file_path.write_text("placeholder", encoding="utf-8")

    decisions_path = state_dir / "decisions.jsonl"
    with decisions_path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "source_path": str(file_path),
                    "relative_path": file_path.name,
                    "target_path": "old",
                    "quality": 30,
                    "category": "LowQuality",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        handle.write(
            json.dumps(
                {
                    "source_path": str(file_path),
                    "relative_path": file_path.name,
                    "target_path": "new",
                    "quality": 90,
                    "category": "Design",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    records = load_records(decisions_path, settings)

    assert len(records) == 1
    assert records[0].quality == 90
    assert records[0].category == "Design"


def test_text_citation_signal_links_explicit_title_mentions(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    design = source_dir / "Payment Architecture.md"
    review = source_dir / "Engineering Review.md"
    design.write_text("# Payment Architecture\n\nDesign body", encoding="utf-8")
    review.write_text(
        "This review follows Payment Architecture and captures lessons.",
        encoding="utf-8",
    )

    decisions = [
        {
            "source_path": str(design),
            "relative_path": design.name,
            "target_path": "",
            "quality": 90,
            "category": "Architecture",
            "summary": "payment design",
        },
        {
            "source_path": str(review),
            "relative_path": review.name,
            "target_path": "",
            "quality": 88,
            "category": "Thinking",
            "summary": "mentions Payment Architecture",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for item in decisions:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_USE_TEXT_CITATIONS=True,
        RELATIONSHIP_MIN_SCORE=0.05,
    )
    records = load_records(state_dir / "decisions.jsonl", settings)
    citation_pairs = collect_citation_pairs(records)

    assert citation_pairs == {(0, 1): 1}

    mine_relationships(settings)
    relation_line = (output_root / "_relationships" / "relations.jsonl").read_text(
        encoding="utf-8"
    )

    assert '"citation"' in relation_line
    assert '"citation_count": 1' in relation_line


def test_candidate_pairs_are_collected_by_registered_strategies(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    first = source_dir / "Alpha Plan v1.md"
    second = source_dir / "Alpha Plan v2.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for path in (first, second):
            handle.write(
                json.dumps(
                    {
                        "source_path": str(path),
                        "relative_path": path.name,
                        "quality": 90,
                        "category": "Design",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    records = load_records(state_dir / "decisions.jsonl", settings)

    assert collect_candidate_pairs(records, {}, settings) == {(0, 1)}


def test_parallel_relationship_scoring_path_matches_serial(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)

    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(16):
            path = source_dir / f"Alpha Plan v{index}.md"
            path.write_text(f"alpha {index}", encoding="utf-8")
            handle.write(
                json.dumps(
                    {
                        "source_path": str(path),
                        "relative_path": path.name,
                        "quality": 90,
                        "category": "Design",
                        "summary": "alpha plan",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    base_settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_MIN_SCORE=0.0,
        RELATIONSHIP_MAX_CANDIDATES_PER_FILE=16,
    )
    records = load_records(state_dir / "decisions.jsonl", base_settings)
    serial = build_candidate_relations(
        records, {}, base_settings.model_copy(update={"RELATIONSHIP_WORKERS": 1})
    )
    monkeypatch.setattr(relationship_miner, "MIN_PARALLEL_RELATION_RECORDS", 1)
    monkeypatch.setattr(relationship_miner, "MIN_PARALLEL_RELATION_PAIRS", 1)
    called = {"workers": 0}

    def fake_parallel(sorted_pairs, records, embeddings, settings, citation_pairs, worker_count):
        called["workers"] = worker_count
        return relationship_miner.score_candidate_pairs_chunk(
            sorted_pairs, records, embeddings, settings, citation_pairs
        )

    monkeypatch.setattr(
        relationship_miner, "score_candidate_pairs_parallel", fake_parallel
    )
    parallel = build_candidate_relations(
        records, {}, base_settings.model_copy(update={"RELATIONSHIP_WORKERS": 2})
    )

    assert called["workers"] == 2
    assert parallel == serial


def test_relationship_workers_are_inferred_from_cpu_count(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(relationship_miner.os, "cpu_count", lambda: 12)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
    )

    assert resolve_relationship_workers(settings, 1000) == 8


def test_relationship_workers_keep_small_runs_serial(tmp_path: Path) -> None:
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
    )

    assert resolve_relationship_workers(settings, 999) == 1
