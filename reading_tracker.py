from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

StatusName = Literal[
    "unread",
    "reading",
    "read",
    "skipped",
    "deferred",
    "reread_needed",
]
MARKABLE_STATUSES = {"unread", "reading", "read", "skipped", "deferred"}
TERMINAL_DECISION_STATUSES = {
    "planned",
    "success",
    "success_overwritten_changed_target",
    "skipped_existing_target",
}


@dataclass(slots=True)
class ReadingPaths:
    source_dir: Path
    output_root: Path

    @property
    def state_dir(self) -> Path:
        return self.output_root / "_state"

    @property
    def log_dir(self) -> Path:
        return self.output_root / "_logs"

    @property
    def decisions_path(self) -> Path:
        return self.state_dir / "decisions.jsonl"

    @property
    def reading_status_path(self) -> Path:
        return self.state_dir / "reading_status.jsonl"

    @property
    def progress_path(self) -> Path:
        return self.state_dir / "progress.json"

    @property
    def application_log_path(self) -> Path:
        return self.log_dir / "doctriage.log"


def load_latest_decisions(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Decision log does not exist: {path}")

    decisions: dict[str, dict[str, Any]] = {}
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
            if identity:
                decisions[identity] = payload
    return decisions


def load_latest_reading_events(path: Path) -> dict[str, dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return events

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            relative_path = str(payload.get("relative_path") or "")
            if relative_path:
                events[relative_path] = payload
    return events


def build_reading_rows(
    decisions: dict[str, dict[str, Any]],
    reading_events: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for relative_path, decision in decisions.items():
        event = reading_events.get(relative_path)
        effective_status = infer_effective_status(decision, event)
        rows.append(
            {
                "relative_path": relative_path,
                "display_name": Path(relative_path).name,
                "source_path": str(decision.get("source_path") or ""),
                "target_path": str(decision.get("target_path") or ""),
                "status": effective_status,
                "marked_status": str(event.get("status") if event else "unread"),
                "updated_at": str(event.get("updated_at") if event else ""),
                "quality": coerce_int(decision.get("quality"), 0),
                "category": str(decision.get("category") or ""),
                "document_kind": str(decision.get("document_kind") or "Unknown"),
                "topic_tags": coerce_string_list(decision.get("topic_tags")),
                "sensitivity_risk": coerce_int(decision.get("sensitivity_risk"), 0),
                "public_writing_suitability": coerce_int(
                    decision.get("public_writing_suitability"), 0
                ),
                "summary": str(decision.get("summary") or ""),
                "note": str(event.get("note") if event else ""),
            }
        )
    return rows


def infer_effective_status(
    decision: dict[str, Any], event: dict[str, Any] | None
) -> StatusName:
    if not event:
        return "unread"

    status = str(event.get("status") or "unread")
    if status not in MARKABLE_STATUSES:
        status = "unread"

    if status == "read" and fingerprint_changed(decision, event):
        return "reread_needed"
    return status  # type: ignore[return-value]


def fingerprint_changed(decision: dict[str, Any], event: dict[str, Any]) -> bool:
    decision_fingerprint = decision.get("fingerprint")
    event_fingerprint = event.get("fingerprint")
    if not decision_fingerprint or not event_fingerprint:
        return False
    return decision_fingerprint != event_fingerprint


def append_reading_event(
    paths: ReadingPaths,
    decisions: dict[str, dict[str, Any]],
    *,
    requested_path: str,
    status: str,
    note: str = "",
) -> dict[str, Any]:
    if status not in MARKABLE_STATUSES:
        raise ValueError(f"Unsupported reading status: {status}")

    relative_path = resolve_relative_path(requested_path, paths.source_dir, decisions)
    decision = decisions.get(relative_path, {})
    event = {
        "relative_path": relative_path,
        "source_path": str(decision.get("source_path") or ""),
        "status": status,
        "note": note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "fingerprint": decision.get("fingerprint"),
        "quality": decision.get("quality"),
        "category": decision.get("category"),
    }
    paths.reading_status_path.parent.mkdir(parents=True, exist_ok=True)
    with paths.reading_status_path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def resolve_relative_path(
    requested_path: str,
    source_dir: Path,
    decisions: dict[str, dict[str, Any]],
) -> str:
    text = requested_path.strip()
    if text in decisions:
        return text

    path = Path(text)
    if path.is_absolute():
        try:
            return path.resolve().relative_to(source_dir.resolve()).as_posix()
        except ValueError:
            pass

    matches = [
        relative_path
        for relative_path in decisions
        if relative_path.endswith(text.replace("\\", "/"))
        or Path(relative_path).name == text
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"Could not resolve document path: {requested_path}")
    raise ValueError(
        f"Ambiguous document path: {requested_path}; matched {len(matches)} documents."
    )


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    status: str | None,
    min_quality: int,
    categories: set[str],
    max_sensitivity_risk: int | None,
    min_public_writing_suitability: int | None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if status and row["status"] != status:
            continue
        if row["quality"] < min_quality:
            continue
        if categories and row["category"] not in categories:
            continue
        if (
            max_sensitivity_risk is not None
            and row["sensitivity_risk"] > max_sensitivity_risk
        ):
            continue
        if (
            min_public_writing_suitability is not None
            and row["public_writing_suitability"] < min_public_writing_suitability
        ):
            continue
        filtered.append(row)

    filtered.sort(
        key=lambda item: (
            item["status"],
            -item["quality"],
            item["category"],
            item["relative_path"],
        )
    )
    return filtered


def print_rows(rows: list[dict[str, Any]], *, output_jsonl: bool) -> None:
    if output_jsonl:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
        return

    for row in rows:
        tags = ",".join(row["topic_tags"])
        print(
            f"{row['status']:14} q={row['quality']:3} "
            f"{row['category']:14} {row['document_kind']:22} "
            f"{row['relative_path']} {tags}"
        )


def print_stats(rows: list[dict[str, Any]]) -> None:
    by_status = Counter(row["status"] for row in rows)
    by_category = Counter(row["category"] for row in rows)
    print("status")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")
    print("category")
    for category, count in sorted(by_category.items()):
        print(f"  {category}: {count}")


def decision_identity(decision: dict[str, Any]) -> str:
    return str(decision.get("relative_path") or decision.get("source_path") or "")


def coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
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


def load_rows(paths: ReadingPaths) -> list[dict[str, Any]]:
    decisions = load_latest_decisions(paths.decisions_path)
    events = load_latest_reading_events(paths.reading_status_path)
    return build_reading_rows(decisions, events)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-reading",
        description="Track manual reading state without moving source documents.",
    )
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stats_parser = subparsers.add_parser("stats", help="Show reading status counts.")
    stats_parser.set_defaults(command="stats")

    list_parser = subparsers.add_parser("list", help="List documents by reading state.")
    list_parser.add_argument(
        "--status",
        choices=["unread", "reading", "read", "skipped", "deferred", "reread_needed"],
    )
    list_parser.add_argument("--min-quality", type=int, default=0)
    list_parser.add_argument("--categories")
    list_parser.add_argument("--max-sensitivity-risk", type=int)
    list_parser.add_argument("--min-public-writing-suitability", type=int)
    list_parser.add_argument("--limit", type=int)
    list_parser.add_argument("--jsonl", action="store_true")

    mark_parser = subparsers.add_parser("mark", help="Mark one document read state.")
    mark_parser.add_argument("--path", required=True)
    mark_parser.add_argument(
        "--status",
        choices=sorted(MARKABLE_STATUSES),
        required=True,
    )
    mark_parser.add_argument("--note", default="")
    return parser


def build_paths(args: argparse.Namespace) -> ReadingPaths:
    return ReadingPaths(
        source_dir=args.source_dir.expanduser().resolve(),
        output_root=args.output_root.expanduser().resolve(),
    )


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    paths = build_paths(args)

    if args.command == "mark":
        decisions = load_latest_decisions(paths.decisions_path)
        event = append_reading_event(
            paths,
            decisions,
            requested_path=args.path,
            status=args.status,
            note=args.note,
        )
        print(json.dumps(event, ensure_ascii=False))
        return

    rows = load_rows(paths)
    if args.command == "stats":
        print_stats(rows)
        return

    if args.command == "list":
        filtered = filter_rows(
            rows,
            status=args.status,
            min_quality=args.min_quality,
            categories=parse_categories(args.categories),
            max_sensitivity_risk=args.max_sensitivity_risk,
            min_public_writing_suitability=args.min_public_writing_suitability,
        )
        if args.limit is not None:
            filtered = filtered[: args.limit]
        print_rows(filtered, output_jsonl=args.jsonl)
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
