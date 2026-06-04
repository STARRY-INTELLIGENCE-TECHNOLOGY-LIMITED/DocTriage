from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Settings, get_settings

SCHEMA_VERSION = "doctriage_bundle.v1"
TERMINAL_DECISION_STATUSES = {
    "planned",
    "success",
    "success_overwritten_changed_target",
    "skipped_existing_target",
}


@dataclass(slots=True)
class BundleSelection:
    min_quality: int = 0
    categories: set[str] = field(default_factory=set)
    max_sensitivity_risk: int | None = None
    min_public_writing_suitability: int | None = None
    limit: int | None = None
    prefer_target_path: bool = False
    include_summaries: bool = True


def export_bundle(
    settings: Settings | None = None,
    *,
    title: str = "DocTriage Bundle",
    output_path: Path | None = None,
    selection: BundleSelection | None = None,
) -> Path:
    current_settings = settings or get_settings()
    current_selection = selection or BundleSelection()
    decisions_path = current_settings.processed_log_path.parent / "decisions.jsonl"
    relations_path = current_settings.relationship_relations_path
    decisions = load_latest_decisions(decisions_path)
    documents = select_documents(decisions, current_selection)
    relations = load_relations_for_documents(relations_path, documents)
    payload = build_bundle_payload(
        title=title,
        settings=current_settings,
        selection=current_selection,
        documents=documents,
        relations=relations,
    )
    resolved_output = output_path or (
        current_settings.relationship_dir / "doctriage_bundle.json"
    )
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return resolved_output


def load_latest_decisions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Decision log does not exist: {path}")

    decisions_by_identity: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            status = str(payload.get("status") or "")
            if status and status not in TERMINAL_DECISION_STATUSES:
                continue
            identity = decision_identity(payload)
            if not identity:
                continue
            decisions_by_identity[identity] = payload
    return list(decisions_by_identity.values())


def select_documents(
    decisions: list[dict[str, Any]],
    selection: BundleSelection,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for decision in decisions:
        quality = coerce_int(decision.get("quality"), 0)
        category = str(decision.get("category") or "")
        if quality < selection.min_quality:
            continue
        if selection.categories and category not in selection.categories:
            continue
        sensitivity_risk = coerce_int(decision.get("sensitivity_risk"), 0)
        public_writing_suitability = coerce_int(
            decision.get("public_writing_suitability"), 0
        )
        if (
            selection.max_sensitivity_risk is not None
            and sensitivity_risk > selection.max_sensitivity_risk
        ):
            continue
        if (
            selection.min_public_writing_suitability is not None
            and public_writing_suitability < selection.min_public_writing_suitability
        ):
            continue
        source_path = str(decision.get("source_path") or "")
        target_path = str(decision.get("target_path") or "")
        selected.append(
            {
                "id": document_id(decision),
                "source_path": source_path,
                "target_path": target_path,
                "preferred_path": choose_preferred_path(
                    source_path,
                    target_path,
                    selection.prefer_target_path,
                ),
                "relative_path": str(decision.get("relative_path") or ""),
                "title": Path(str(decision.get("relative_path") or source_path)).stem,
                "category": category,
                "document_kind": str(decision.get("document_kind") or "Unknown"),
                "topic_tags": coerce_string_list(decision.get("topic_tags")),
                "quality": quality,
                "knowledge_density": coerce_int(decision.get("knowledge_density"), 0),
                "implementation_specificity": coerce_int(
                    decision.get("implementation_specificity"), 0
                ),
                "logical_structure": coerce_int(decision.get("logical_structure"), 0),
                "evidence_richness": coerce_int(decision.get("evidence_richness"), 0),
                "actionability": coerce_int(decision.get("actionability"), 0),
                "strategic_value": coerce_int(decision.get("strategic_value"), 0),
                "freshness": coerce_int(decision.get("freshness"), 0),
                "uniqueness": coerce_int(decision.get("uniqueness"), 0),
                "sensitivity_risk": sensitivity_risk,
                "public_writing_suitability": public_writing_suitability,
                "reason": str(decision.get("reason") or ""),
                "summary": (
                    str(decision.get("summary") or "")
                    if selection.include_summaries
                    else ""
                ),
                "status": str(decision.get("status") or ""),
                "media_type": guess_media_type(
                    Path(str(decision.get("relative_path") or source_path))
                ),
            }
        )

    selected.sort(
        key=lambda item: (
            -item["quality"],
            item["category"],
            item["relative_path"],
        )
    )
    if selection.limit is not None:
        return selected[: selection.limit]
    return selected


def load_relations_for_documents(
    path: Path,
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not path.exists() or not documents:
        return []

    document_paths = {str(document["relative_path"]) for document in documents}
    relations: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            left_path = str(payload.get("left", {}).get("relative_path") or "")
            right_path = str(payload.get("right", {}).get("relative_path") or "")
            if left_path not in document_paths or right_path not in document_paths:
                continue
            relations.append(
                {
                    "left_relative_path": left_path,
                    "right_relative_path": right_path,
                    "relation_score": coerce_float(
                        payload.get("relation_score"), 0.0
                    ),
                    "signals": list(payload.get("signals") or []),
                    "filename_similarity": coerce_float(
                        payload.get("filename_similarity"), 0.0
                    ),
                    "time_proximity": coerce_float(
                        payload.get("time_proximity"), 0.0
                    ),
                    "path_proximity": coerce_float(
                        payload.get("path_proximity"), 0.0
                    ),
                    "embedding_similarity": coerce_float(
                        payload.get("embedding_similarity"), 0.0
                    ),
                    "citation_count": coerce_int(payload.get("citation_count"), 0),
                }
            )
    relations.sort(key=lambda item: item["relation_score"], reverse=True)
    return relations


def build_bundle_payload(
    *,
    title: str,
    settings: Settings,
    selection: BundleSelection,
    documents: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "title": title,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": build_source_metadata(settings),
        "selection_policy": {
            "min_quality": selection.min_quality,
            "categories": sorted(selection.categories),
            "max_sensitivity_risk": selection.max_sensitivity_risk,
            "min_public_writing_suitability": selection.min_public_writing_suitability,
            "limit": selection.limit,
            "prefer_target_path": selection.prefer_target_path,
            "include_summaries": selection.include_summaries,
        },
        "statistics": {
            "document_count": len(documents),
            "relation_count": len(relations),
            "category_counts": count_by(documents, "category"),
            "document_kind_counts": count_by(documents, "document_kind"),
        },
        "documents": documents,
        "relations": relations,
    }


def document_id(decision: dict[str, Any]) -> str:
    identity = decision_identity(decision)
    digest = stable_hash(identity)
    return f"doc-{digest[:12]}"


def decision_identity(decision: dict[str, Any]) -> str:
    return str(decision.get("relative_path") or decision.get("source_path") or "")


def stable_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def build_source_metadata(settings: Settings) -> dict[str, str]:
    return {
        "source_dir": str(settings.SOURCE_DIR),
        "output_root": str(settings.OUTPUT_ROOT),
        "decisions_path": str(settings.processed_log_path.parent / "decisions.jsonl"),
        "relations_path": str(settings.relationship_relations_path),
    }


def choose_preferred_path(
    source_path: str,
    target_path: str,
    prefer_target_path: bool,
) -> str:
    if prefer_target_path and target_path and Path(target_path).exists():
        return target_path
    return source_path or target_path


def guess_media_type(path: Path) -> str:
    mapping = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
        ".csv": "text/csv",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".bmp": "image/bmp",
        ".epub": "application/epub+zip",
    }
    return mapping.get(path.suffix.lower(), "unknown")


def count_by(documents: list[dict[str, Any]], field_name: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for document in documents:
        counts[str(document.get(field_name) or "")] += 1
    return dict(sorted(counts.items()))


def coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        values = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        values = [str(item).strip() for item in value]
    else:
        return []
    return [item for item in values if item]


def parse_categories(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-bundle",
        description="Export selected DocTriage decisions as a low-coupling bundle for downstream tools.",
    )
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--llm-endpoint")
    parser.add_argument("--llm-model")
    parser.add_argument("--title", default="DocTriage Bundle")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--min-quality", type=int, default=0)
    parser.add_argument(
        "--categories",
        help="Comma-separated category allow-list, for example Architecture,Thinking,Series.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--max-sensitivity-risk",
        type=int,
        help="Exclude documents above this sensitivity risk score.",
    )
    parser.add_argument(
        "--min-public-writing-suitability",
        type=int,
        help="Exclude documents below this public writing suitability score.",
    )
    parser.add_argument(
        "--prefer-target-path",
        action="store_true",
        help="Use copied target paths when they exist; otherwise keep source paths.",
    )
    parser.add_argument(
        "--no-summaries",
        action="store_true",
        help="Do not include persisted local summaries in the bundle.",
    )
    return parser


def build_settings_from_args(args: argparse.Namespace) -> Settings:
    overrides: dict[str, Any] = {}
    if args.source_dir is not None:
        overrides["SOURCE_DIR"] = args.source_dir
    if args.output_root is not None:
        overrides["OUTPUT_ROOT"] = args.output_root
    if args.llm_endpoint is not None:
        overrides["LLM_ENDPOINT"] = args.llm_endpoint
    if args.llm_model is not None:
        overrides["LLM_MODEL"] = args.llm_model
    if overrides:
        return Settings(**overrides)
    return get_settings()


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    selection = BundleSelection(
        min_quality=args.min_quality,
        categories=parse_categories(args.categories),
        max_sensitivity_risk=args.max_sensitivity_risk,
        min_public_writing_suitability=args.min_public_writing_suitability,
        limit=args.limit,
        prefer_target_path=args.prefer_target_path,
        include_summaries=not args.no_summaries,
    )
    output_path = export_bundle(
        build_settings_from_args(args),
        title=args.title,
        output_path=args.output,
        selection=selection,
    )
    print(output_path)


if __name__ == "__main__":
    main()
