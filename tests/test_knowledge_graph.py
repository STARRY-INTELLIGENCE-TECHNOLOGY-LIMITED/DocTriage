import json
from pathlib import Path

from config import Settings
from knowledge_graph import build_knowledge_graph, export_knowledge_graph


def test_export_knowledge_graph_from_decisions_and_relations(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    relationship_dir = output_root / "_relationships"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    relationship_dir.mkdir(parents=True)

    decisions = [
        {
            "source_path": str(source_dir / "alpha-v1.pdf"),
            "relative_path": "alpha-v1.pdf",
            "target_path": str(output_root / "HQ" / "Design" / "alpha-v1.pdf"),
            "status": "planned",
            "quality": 85,
            "category": "Design",
            "knowledge_density": 80,
            "implementation_specificity": 60,
            "logical_structure": 90,
            "reason": "structured design",
            "summary": "alpha design v1",
        },
        {
            "source_path": str(source_dir / "alpha-v2.pdf"),
            "relative_path": "alpha-v2.pdf",
            "target_path": str(output_root / "HQ" / "Design" / "alpha-v2.pdf"),
            "status": "planned",
            "quality": 88,
            "category": "Design",
            "knowledge_density": 82,
            "implementation_specificity": 62,
            "logical_structure": 92,
            "reason": "structured design update",
            "summary": "alpha design v2",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    relation = {
        "left": {"relative_path": "alpha-v1.pdf", "quality": 85, "category": "Design"},
        "right": {"relative_path": "alpha-v2.pdf", "quality": 88, "category": "Design"},
        "relation_score": 0.9,
        "filename_similarity": 0.8,
        "time_proximity": 0.7,
        "path_proximity": 1.0,
        "embedding_similarity": 0,
        "type_compatibility": 1.0,
        "signals": ["filename", "version_or_sequence"],
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

    graph = build_knowledge_graph(settings)
    assert len(graph.documents) == 2
    assert any(edge.type == "EVOLVES_TO" for edge in graph.edges)
    assert any(node.type == "Category" for node in graph.nodes)
    assert any(node.type == "Cluster" for node in graph.nodes)
    assert any(node.type == "IngestionPolicy" for node in graph.nodes)

    output_path = export_knowledge_graph(settings)
    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "pre_rag_kg.v1"
    assert exported["documents"]
    assert exported["edges"]
    assert exported["metadata"]["edge_count"] == len(exported["edges"])


def test_knowledge_graph_uses_latest_decision(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)

    decisions = [
        {
            "source_path": str(source_dir / "doc.md"),
            "relative_path": "doc.md",
            "target_path": "old",
            "status": "planned",
            "quality": 20,
            "category": "LowQuality",
        },
        {
            "source_path": str(source_dir / "doc.md"),
            "relative_path": "doc.md",
            "target_path": "new",
            "status": "planned",
            "quality": 91,
            "category": "Architecture",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for decision in decisions:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )

    graph = build_knowledge_graph(settings)

    assert len(graph.documents) == 1
    assert graph.documents[0].quality == 91
    assert graph.documents[0].category == "Architecture"
