import copy
import json
from pathlib import Path

from bundle_exporter import BundleSelection, export_bundle
from config import Settings


CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "contracts"
    / "doctriage_bundle.v2.golden.json"
)


def test_exported_bundle_matches_v2_golden_contract(tmp_path: Path) -> None:
    expected = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    decisions_path = output_root / "_state" / "decisions.jsonl"
    relations_path = output_root / "_relationships" / "relations.jsonl"
    decisions_path.parent.mkdir(parents=True)
    relations_path.parent.mkdir(parents=True)

    decisions = [
        _decision(
            source_dir,
            output_root,
            relative_path="office/组织协作方法.md",
            quality=96,
            topic_tags=["组织协作", "沟通"],
            summary="介绍跨团队协作、职责边界和沟通机制。",
            reason="适合作为组织协作的一般方法资料。",
            scores={
                "knowledge_density": 88,
                "implementation_specificity": 72,
                "logical_structure": 91,
                "evidence_richness": 75,
                "actionability": 86,
                "strategic_value": 84,
                "freshness": 70,
                "uniqueness": 74,
                "sensitivity_risk": 10,
                "public_writing_suitability": 90,
            },
        ),
        _decision(
            source_dir,
            output_root,
            relative_path="office/怎么成为嫡系.pdf",
            quality=72,
            topic_tags=["办公室政治", "组织关系"],
            summary="讨论办公室政治中的信任建立、关键任务交付、边界意识与长期合作。",
            reason="标题和内容直接覆盖如何成为核心协作成员的问题。",
            scores={
                "knowledge_density": 82,
                "implementation_specificity": 68,
                "logical_structure": 79,
                "evidence_richness": 64,
                "actionability": 81,
                "strategic_value": 78,
                "freshness": 66,
                "uniqueness": 83,
                "sensitivity_risk": 35,
                "public_writing_suitability": 55,
            },
        ),
    ]
    decisions_path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in decisions),
        encoding="utf-8",
    )
    relations_path.write_text(
        json.dumps(
            {
                "left": {"relative_path": "office/组织协作方法.md"},
                "right": {"relative_path": "office/怎么成为嫡系.pdf"},
                "relation_score": 0.77,
                "signals": ["topic_tags", "citation"],
                "filename_similarity": 0.12,
                "time_proximity": 0.2,
                "path_proximity": 1.0,
                "embedding_similarity": 0.71,
                "citation_count": 1,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    settings = Settings(
        LLM_ENDPOINT="http://127.0.0.1:11434/api/generate",
        LLM_MODEL="contract-model",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )

    output_path = export_bundle(
        settings,
        title=expected["title"],
        selection=BundleSelection(),
    )
    actual = json.loads(output_path.read_text(encoding="utf-8"))

    assert _normalize_volatile_fields(actual, expected) == expected


def _decision(
    source_dir: Path,
    output_root: Path,
    *,
    relative_path: str,
    quality: int,
    topic_tags: list[str],
    summary: str,
    reason: str,
    scores: dict[str, int],
) -> dict[str, object]:
    source_path = source_dir / relative_path
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(relative_path, encoding="utf-8")
    return {
        "source_path": str(source_path),
        "relative_path": relative_path,
        "target_path": str(output_root / "HQ" / "Thinking" / source_path.name),
        "status": "planned",
        "quality": quality,
        "category": "Thinking",
        "document_kind": "Article",
        "topic_tags": topic_tags,
        "summary": summary,
        "reason": reason,
        **scores,
    }


def _normalize_volatile_fields(
    payload: dict[str, object],
    expected: dict[str, object],
) -> dict[str, object]:
    normalized = copy.deepcopy(payload)
    normalized["generated_at"] = expected["generated_at"]
    normalized["source"] = copy.deepcopy(expected["source"])

    expected_documents = {
        item["id"]: item
        for item in expected["documents"]
    }
    for document in normalized["documents"]:
        document["paths"] = copy.deepcopy(expected_documents[document["id"]]["paths"])

    expected_artifacts = expected["artifacts"]
    for name, artifact in normalized["artifacts"].items():
        artifact["path"] = expected_artifacts[name]["path"]
        artifact["size_bytes"] = 0
    return normalized
