from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bundle_exporter import (
    BundleSelection,
    guess_media_type,
    load_latest_decisions,
    select_documents,
)
from cleaner import DocumentWasher
from config import Settings
from main import build_file_fingerprint, build_local_summary, summary_for_decision
from meta_profiler import MetadataProfiler
from ranker_engine import LLMClient, ManifestResult, SemanticScore, SemanticScoring

ANALYSIS_SCHEMA_VERSION = "doctriage_file_analysis.v1"
DSampleSET_SCHEMA_VERSION = "doctriage_dataset_record.v1"
CAPABILITIES_SCHEMA_VERSION = "doctriage_workflow_capabilities.v1"


@dataclass(slots=True)
class WorkflowPolicy:
    rag_min_quality: int = 70
    pretraining_min_quality: int = 65
    pretraining_min_uniqueness: int = 50
    sft_min_quality: int = 80
    sft_min_actionability: int = 70
    sft_min_evidence_richness: int = 60
    internal_max_sensitivity_risk: int = 70
    public_max_sensitivity_risk: int = 35
    public_min_writing_suitability: int = 70


def analyze_document(
    file_path: str | Path,
    *,
    settings: Settings,
    source_root: str | Path | None = None,
    scorer: SemanticScoring | None = None,
    policy: WorkflowPolicy | None = None,
    include_clean_preview: bool = False,
    clean_preview_chars: int = 1200,
) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    source_root_path = (
        Path(source_root).expanduser().resolve() if source_root is not None else path.parent
    )
    try:
        relative_path = path.relative_to(source_root_path).as_posix()
    except ValueError:
        relative_path = path.name

    washer = DocumentWasher(settings=settings)
    profiler = MetadataProfiler(settings=settings)
    scoring = scorer or SemanticScoring(llm_client=LLMClient(settings=settings))

    washed = washer.wash(path)
    profile = profiler.profile_document(path, washed.clean_markdown)
    score = scoring.score_document(
        path,
        washed.clean_markdown,
        profile,
        ManifestResult(),
    )
    fallback_summary = build_local_summary(
        washed.clean_markdown,
        max_chars=settings.DOCUMENT_SUMMARY_MAX_CHARS,
    )
    summary = summary_for_decision(
        score,
        fallback_summary,
        settings.DOCUMENT_SUMMARY_MAX_CHARS,
    )
    fingerprint = build_file_fingerprint(path, settings)

    payload = build_analysis_record(
        path=path,
        relative_path=relative_path,
        fingerprint=fingerprint,
        score=score,
        profile=profile.to_llm_payload(),
        extraction_notes=washed.notes,
        summary=summary,
        routing=build_routing(score, policy or WorkflowPolicy()),
    )
    if include_clean_preview:
        payload["text"]["clean_preview"] = washed.clean_markdown[:clean_preview_chars]
    return payload


def build_analysis_record(
    *,
    path: Path,
    relative_path: str,
    fingerprint: dict[str, Any],
    score: SemanticScore,
    profile: dict[str, Any],
    extraction_notes: list[str],
    summary: str,
    routing: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(path),
        "relative_path": relative_path,
        "file": {
            "name": path.name,
            "suffix": path.suffix.lower(),
            "media_type": guess_media_type(path),
            "fingerprint": fingerprint,
        },
        "triage": score.model_dump(),
        "profile": profile,
        "text": {
            "summary": summary,
            "extraction_notes": extraction_notes,
        },
        "workflow": routing,
    }


def build_error_record(file_path: str | Path, exc: Exception) -> dict[str, Any]:
    path = Path(file_path).expanduser()
    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "ok": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_path": str(path),
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }


def build_routing(
    score: SemanticScore | dict[str, Any],
    policy: WorkflowPolicy | None = None,
) -> dict[str, Any]:
    active_policy = policy or WorkflowPolicy()
    values = score.model_dump() if isinstance(score, SemanticScore) else score
    quality = coerce_int(values.get("quality"), 0)
    actionability = coerce_int(values.get("actionability"), 0)
    evidence_richness = coerce_int(values.get("evidence_richness"), 0)
    uniqueness = coerce_int(values.get("uniqueness"), 0)
    sensitivity_risk = coerce_int(values.get("sensitivity_risk"), 0)
    public_writing_suitability = coerce_int(
        values.get("public_writing_suitability"), 0
    )

    routes = {
        "rag": (
            quality >= active_policy.rag_min_quality
            and sensitivity_risk <= active_policy.internal_max_sensitivity_risk
        ),
        "pretraining": (
            quality >= active_policy.pretraining_min_quality
            and uniqueness >= active_policy.pretraining_min_uniqueness
            and sensitivity_risk <= active_policy.internal_max_sensitivity_risk
        ),
        "sft": (
            quality >= active_policy.sft_min_quality
            and actionability >= active_policy.sft_min_actionability
            and evidence_richness >= active_policy.sft_min_evidence_richness
            and sensitivity_risk <= active_policy.public_max_sensitivity_risk
        ),
        "public_writing": (
            quality >= active_policy.rag_min_quality
            and sensitivity_risk <= active_policy.public_max_sensitivity_risk
            and public_writing_suitability
            >= active_policy.public_min_writing_suitability
        ),
    }
    return {
        "routes": routes,
        "recommended_uses": [name for name, enabled in routes.items() if enabled],
        "policy": {
            "rag_min_quality": active_policy.rag_min_quality,
            "pretraining_min_quality": active_policy.pretraining_min_quality,
            "pretraining_min_uniqueness": active_policy.pretraining_min_uniqueness,
            "sft_min_quality": active_policy.sft_min_quality,
            "sft_min_actionability": active_policy.sft_min_actionability,
            "sft_min_evidence_richness": active_policy.sft_min_evidence_richness,
            "internal_max_sensitivity_risk": active_policy.internal_max_sensitivity_risk,
            "public_max_sensitivity_risk": active_policy.public_max_sensitivity_risk,
            "public_min_writing_suitability": active_policy.public_min_writing_suitability,
        },
    }


def build_dataset_records(
    decisions_path: Path,
    *,
    purpose: str,
    selection: BundleSelection | None = None,
    policy: WorkflowPolicy | None = None,
) -> list[dict[str, Any]]:
    current_policy = policy or WorkflowPolicy()
    current_selection = selection or selection_for_purpose(purpose, current_policy)
    decisions = load_latest_decisions(decisions_path)
    documents = select_documents(decisions, current_selection)
    records = [
        build_dataset_record(document, purpose=purpose, policy=current_policy)
        for document in documents
    ]
    return [
        record
        for record in records
        if purpose == "all" or record["workflow"]["routes"].get(purpose, False)
    ]


def build_dataset_record(
    document: dict[str, Any],
    *,
    purpose: str,
    policy: WorkflowPolicy,
) -> dict[str, Any]:
    routing = build_routing(document, policy)
    return {
        "schema_version": DSampleSET_SCHEMA_VERSION,
        "id": document["id"],
        "purpose": purpose,
        "include": purpose == "all" or routing["routes"].get(purpose, False),
        "path": document.get("preferred_path") or document.get("source_path") or "",
        "source_path": document.get("source_path") or "",
        "target_path": document.get("target_path") or "",
        "relative_path": document.get("relative_path") or "",
        "media_type": document.get("media_type") or "unknown",
        "metadata": {
            "title": document.get("title") or "",
            "category": document.get("category") or "",
            "document_kind": document.get("document_kind") or "Unknown",
            "topic_tags": document.get("topic_tags") or [],
        },
        "scores": {
            "quality": document.get("quality", 0),
            "knowledge_density": document.get("knowledge_density", 0),
            "implementation_specificity": document.get(
                "implementation_specificity", 0
            ),
            "logical_structure": document.get("logical_structure", 0),
            "evidence_richness": document.get("evidence_richness", 0),
            "actionability": document.get("actionability", 0),
            "strategic_value": document.get("strategic_value", 0),
            "freshness": document.get("freshness", 0),
            "uniqueness": document.get("uniqueness", 0),
            "sensitivity_risk": document.get("sensitivity_risk", 0),
            "public_writing_suitability": document.get(
                "public_writing_suitability", 0
            ),
        },
        "summary": document.get("summary") or "",
        "reason": document.get("reason") or "",
        "workflow": routing,
    }


def selection_for_purpose(purpose: str, policy: WorkflowPolicy) -> BundleSelection:
    if purpose == "rag":
        return BundleSelection(
            min_quality=policy.rag_min_quality,
            max_sensitivity_risk=policy.internal_max_sensitivity_risk,
        )
    if purpose == "pretraining":
        return BundleSelection(
            min_quality=policy.pretraining_min_quality,
            max_sensitivity_risk=policy.internal_max_sensitivity_risk,
        )
    if purpose == "sft":
        return BundleSelection(
            min_quality=policy.sft_min_quality,
            max_sensitivity_risk=policy.public_max_sensitivity_risk,
        )
    if purpose == "public_writing":
        return BundleSelection(
            min_quality=policy.rag_min_quality,
            max_sensitivity_risk=policy.public_max_sensitivity_risk,
            min_public_writing_suitability=policy.public_min_writing_suitability,
        )
    if purpose == "all":
        return BundleSelection()
    raise ValueError(f"Unsupported purpose: {purpose}")


def iter_input_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(item) for item in args.file or []]
    if args.input_jsonl is None:
        return paths

    if str(args.input_jsonl) == "-":
        lines = sys.stdin
    else:
        lines = Path(args.input_jsonl).open("r", encoding="utf-8", errors="ignore")

    with lines:
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                paths.append(Path(line))
                continue
            if isinstance(payload, str):
                paths.append(Path(payload))
            elif isinstance(payload, dict):
                value = payload.get("path") or payload.get("source_path")
                if value:
                    paths.append(Path(str(value)))
    return paths


def build_capabilities_payload() -> dict[str, Any]:
    return {
        "schema_version": CAPABILITIES_SCHEMA_VERSION,
        "commands": {
            "analyze": {
                "input": "file paths via --file or JSONL via --input-jsonl",
                "output": ANALYSIS_SCHEMA_VERSION,
                "use_case": "single or batch document triage inside an LLM/Agent workflow",
            },
            "export-manifest": {
                "input": "existing OUTPUT_ROOT/_state/decisions.jsonl",
                "output": DSampleSET_SCHEMA_VERSION,
                "purposes": ["rag", "pretraining", "sft", "public_writing", "all"],
            },
        },
        "stable_fields": [
            "source_path",
            "relative_path",
            "triage.quality",
            "triage.category",
            "triage.document_kind",
            "triage.topic_tags",
            "triage.sensitivity_risk",
            "triage.public_writing_suitability",
            "workflow.routes",
        ],
    }


def write_payload(payload: Any, *, output: Path | None, jsonl: bool) -> None:
    if jsonl and isinstance(payload, list):
        text = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in payload)
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")


def build_settings_for_analyze(args: argparse.Namespace, paths: list[Path]) -> Settings:
    if not paths:
        raise ValueError("At least one --file or --input-jsonl record is required.")

    resolved_paths = [path.expanduser().resolve() for path in paths]
    source_dir = (
        args.source_dir.expanduser().resolve()
        if args.source_dir is not None
        else common_source_root(resolved_paths)
    )
    output_root = (
        args.output_root.expanduser().resolve()
        if args.output_root is not None
        else Path.cwd().resolve() / ".doctriage_workflow"
    )
    overrides: dict[str, Any] = {
        "SOURCE_DIR": source_dir,
        "OUTPUT_ROOT": output_root,
        "COPY_FILES": False,
        "SKIP_MANIFEST_ANALYSIS": True,
        "DOCUMENT_SUMMARY_ENABLED": True,
        "OCR_ENABLED": not args.no_ocr,
        "PDF_METADSample_ENABLED": args.pdf_metadata,
        "REQUIRE_LOCAL_LLM": args.require_local_llm,
    }
    if args.llm_endpoint is not None:
        overrides["LLM_ENDPOINT"] = args.llm_endpoint
    if args.llm_model is not None:
        overrides["LLM_MODEL"] = args.llm_model
    if args.timeout_seconds is not None:
        overrides["LLM_TIMEOUT_SECONDS"] = args.timeout_seconds
    if args.retry_count is not None:
        overrides["LLM_RETRY_COUNT"] = args.retry_count
    if args.output_language is not None:
        overrides["OUTPUT_LANGUAGE"] = args.output_language
    return Settings(**overrides)


def common_source_root(paths: Iterable[Path]) -> Path:
    parents = [path.parent for path in paths]
    if not parents:
        return Path.cwd().resolve()
    try:
        import os

        common = Path(os.path.commonpath([str(parent) for parent in parents]))
    except ValueError:
        common = parents[0]
    return common.resolve()


def build_policy_from_args(args: argparse.Namespace) -> WorkflowPolicy:
    policy = WorkflowPolicy()
    for field_name in policy.__dataclass_fields__:
        value = getattr(args, field_name, None)
        if value is not None:
            setattr(policy, field_name, value)
    return policy


def coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-workflow",
        description="Machine-readable DocTriage adapter for LLM and dataset workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("capabilities", help="Print JSON capabilities.")

    analyze = subparsers.add_parser("analyze", help="Analyze one or more files.")
    analyze.add_argument("--file", action="append", type=Path)
    analyze.add_argument("--input-jsonl", type=Path)
    analyze.add_argument("--source-dir", type=Path)
    analyze.add_argument("--output-root", type=Path)
    analyze.add_argument("--llm-endpoint")
    analyze.add_argument("--llm-model")
    analyze.add_argument("--timeout-seconds", type=int)
    analyze.add_argument("--retry-count", type=int)
    analyze.add_argument(
        "--output-language",
        choices=["auto", "zh-CN", "en", "ja", "ko", "de", "fr", "es"],
    )
    analyze.add_argument("--no-ocr", action="store_true")
    analyze.add_argument("--pdf-metadata", action="store_true")
    analyze.add_argument("--require-local-llm", action="store_true")
    analyze.add_argument("--include-clean-preview", action="store_true")
    analyze.add_argument("--clean-preview-chars", type=int, default=1200)
    analyze.add_argument("--jsonl", action="store_true")
    analyze.add_argument("--output", type=Path)

    manifest = subparsers.add_parser(
        "export-manifest",
        help="Export JSON/JSONL candidate records from existing DocTriage decisions.",
    )
    manifest.add_argument(
        "--purpose",
        choices=["rag", "pretraining", "sft", "public_writing", "all"],
        default="rag",
    )
    manifest.add_argument("--decisions", type=Path)
    manifest.add_argument("--output-root", type=Path)
    manifest.add_argument("--jsonl", action="store_true")
    manifest.add_argument("--output", type=Path)

    for command in (analyze, manifest):
        add_policy_args(command)

    return parser


def add_policy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--rag-min-quality", type=int)
    parser.add_argument("--pretraining-min-quality", type=int)
    parser.add_argument("--pretraining-min-uniqueness", type=int)
    parser.add_argument("--sft-min-quality", type=int)
    parser.add_argument("--sft-min-actionability", type=int)
    parser.add_argument("--sft-min-evidence-richness", type=int)
    parser.add_argument("--internal-max-sensitivity-risk", type=int)
    parser.add_argument("--public-max-sensitivity-risk", type=int)
    parser.add_argument("--public-min-writing-suitability", type=int)


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "capabilities":
        write_payload(build_capabilities_payload(), output=None, jsonl=False)
        return

    policy = build_policy_from_args(args)
    if args.command == "analyze":
        paths = iter_input_paths(args)
        settings = build_settings_for_analyze(args, paths)
        records = []
        for path in paths:
            try:
                records.append(
                    analyze_document(
                        path,
                        settings=settings,
                        source_root=settings.SOURCE_DIR,
                        policy=policy,
                        include_clean_preview=args.include_clean_preview,
                        clean_preview_chars=args.clean_preview_chars,
                    )
                )
            except Exception as exc:
                records.append(build_error_record(path, exc))
        write_payload(records if args.jsonl else {"records": records}, output=args.output, jsonl=args.jsonl)
        return

    if args.command == "export-manifest":
        if args.decisions is not None:
            decisions_path = args.decisions.expanduser().resolve()
        elif args.output_root is not None:
            decisions_path = (
                args.output_root.expanduser().resolve() / "_state" / "decisions.jsonl"
            )
        else:
            raise SystemExit("--decisions or --output-root is required.")
        records = build_dataset_records(
            decisions_path,
            purpose=args.purpose,
            policy=policy,
        )
        write_payload(records if args.jsonl else {"records": records}, output=args.output, jsonl=args.jsonl)
        return


if __name__ == "__main__":
    main()
