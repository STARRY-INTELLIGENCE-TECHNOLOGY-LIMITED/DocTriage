from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Sequence, TypeVar
from urllib.parse import urlparse

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Settings, get_settings
from relationship_strategies import (
    DEFAULT_PAIR_COLLECTORS,
    collect_citation_pairs,
    collect_pairs,
)
from relationship_strategies.citation import (
    build_alias_index,
    build_aliases,
    build_citation_text,
    is_usable_alias,
    read_plain_citation_text,
)
from relationship_strategies.common import (
    cosine_similarity,
    normalize_citation_text,
    normalize_pair,
    tokenize,
)

VERSION_PATTERN = re.compile(
    r"(?i)(?:^|[\s._-])(v?\d+(?:\.\d+){0,3}|part\s*\d+|第\s*\d+\s*[篇章节]|上篇|下篇|续篇|完结篇|总结篇)(?:$|[\s._-])"
)
TERMINAL_DECISION_STATUSES = {
    "planned",
    "success",
    "success_overwritten_changed_target",
    "skipped_existing_target",
}
MIN_PARALLEL_RELATION_RECORDS = 1000
MIN_PARALLEL_RELATION_PAIRS = 5000
MIN_PARALLEL_CITATION_RECORDS = 1000
PARALLEL_BATCH_TARGET = 8
T = TypeVar("T")


@dataclass(slots=True)
class RelationshipRecord:
    source_path: Path
    relative_path: str
    target_path: str
    quality: int
    category: str
    document_kind: str
    topic_tags: list[str]
    reason: str
    summary: str
    file_size_bytes: int = 0
    created_epoch: float = 0.0
    modified_epoch: float = 0.0
    normalized_name: str = ""
    embedding_text: str = ""
    citation_text: str = ""


@dataclass(slots=True)
class CandidateRelation:
    left: int
    right: int
    relation_score: float
    filename_similarity: float = 0.0
    time_proximity: float = 0.0
    path_proximity: float = 0.0
    embedding_similarity: float = 0.0
    type_compatibility: float = 0.0
    citation_count: int = 0
    signals: list[str] = field(default_factory=list)


_CITATION_ALIAS_INDEX: dict[str, int] = {}
_SCORE_RECORDS: list[RelationshipRecord] = []
_SCORE_EMBEDDINGS: dict[int, list[float]] = {}
_SCORE_SETTINGS: Settings | None = None
_SCORE_CITATION_PAIRS: dict[tuple[int, int], int] = {}


class OllamaEmbeddingClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.endpoint = settings.EMBEDDING_ENDPOINT.rstrip("/")
        self.model = settings.EMBEDDING_MODEL or settings.LLM_MODEL
        if not self.model:
            raise ValueError("EMBEDDING_MODEL or LLM_MODEL must be configured for embeddings.")

    def embed(self, text: str) -> list[float]:
        payload = self._build_payload(text)
        response = httpx.post(
            self.endpoint,
            json=payload,
            timeout=self.settings.EMBEDDING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        response_json = response.json()

        vector = response_json.get("embedding")
        if vector is None and isinstance(response_json.get("embeddings"), list):
            embeddings = response_json["embeddings"]
            vector = embeddings[0] if embeddings else None
        if not isinstance(vector, list):
            raise ValueError("Embedding response did not contain a vector.")
        return [float(value) for value in vector]

    def _build_payload(self, text: str) -> dict[str, Any]:
        if self.endpoint.lower().endswith("/api/embed"):
            return {"model": self.model, "input": text}
        return {"model": self.model, "prompt": text}


def mine_relationships(settings: Settings | None = None) -> None:
    current_settings = settings or get_settings()
    validate_relationship_settings(current_settings)

    decisions_path = current_settings.processed_log_path.parent / "decisions.jsonl"
    records = load_records(decisions_path, current_settings)
    if current_settings.RELATIONSHIP_MAX_RECORDS:
        records = records[: current_settings.RELATIONSHIP_MAX_RECORDS]

    current_settings.relationship_dir.mkdir(parents=True, exist_ok=True)
    embeddings = (
        load_or_build_embeddings(records, current_settings)
        if current_settings.RELATIONSHIP_USE_EMBEDDINGS
        else {}
    )

    candidates = build_candidate_relations(records, embeddings, current_settings)
    write_relations(candidates, records, current_settings.relationship_relations_path)
    write_clusters(candidates, records, current_settings.relationship_clusters_path)


def validate_relationship_settings(settings: Settings) -> None:
    if not settings.RELATIONSHIP_USE_EMBEDDINGS:
        return

    if settings.REQUIRE_LOCAL_LLM:
        parsed = urlparse(settings.EMBEDDING_ENDPOINT)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError(
                f"REQUIRE_LOCAL_LLM is enabled but embedding endpoint is not local: {settings.EMBEDDING_ENDPOINT}"
            )


def load_records(path: Path, settings: Settings) -> list[RelationshipRecord]:
    if not path.exists():
        raise FileNotFoundError(f"Decision log does not exist: {path}")

    records_by_identity: dict[str, RelationshipRecord] = {}

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

            source_path = Path(str(payload.get("source_path", "")))
            relative_path = str(payload.get("relative_path") or source_path.name)
            identity = relative_path or str(source_path)
            if not identity:
                continue

            stat = safe_stat(source_path)
            summary = sanitize_text(str(payload.get("summary", "")))
            reason = sanitize_text(str(payload.get("reason", "")))
            record = RelationshipRecord(
                source_path=source_path,
                relative_path=relative_path,
                target_path=str(payload.get("target_path", "")),
                quality=coerce_int(payload.get("quality"), 0),
                category=str(payload.get("category", "")),
                document_kind=str(payload.get("document_kind") or "Unknown"),
                topic_tags=coerce_string_list(payload.get("topic_tags")),
                reason=reason,
                summary=summary,
                file_size_bytes=stat.get("size", 0),
                created_epoch=stat.get("created", 0.0),
                modified_epoch=stat.get("modified", 0.0),
                normalized_name=normalize_name(Path(relative_path).stem),
            )
            record.embedding_text = build_embedding_text(record, settings)
            record.citation_text = build_citation_text(record)
            records_by_identity[identity] = record

    return list(records_by_identity.values())


def safe_stat(path: Path) -> dict[str, float]:
    try:
        stat = path.stat()
    except OSError:
        return {"size": 0, "created": 0.0, "modified": 0.0}
    return {
        "size": float(stat.st_size),
        "created": float(stat.st_ctime),
        "modified": float(stat.st_mtime),
    }


def build_embedding_text(record: RelationshipRecord, settings: Settings) -> str:
    parts = [
        f"path: {record.relative_path}",
        f"title: {Path(record.relative_path).stem}",
        f"category: {record.category}",
        f"document_kind: {record.document_kind}",
        f"topic_tags: {', '.join(record.topic_tags)}",
        f"reason: {record.reason}",
        f"summary: {record.summary}",
    ]
    text = "\n".join(part for part in parts if part)
    return sanitize_text(text)[: settings.EMBEDDING_TEXT_MAX_CHARS]


def load_or_build_embeddings(
    records: list[RelationshipRecord], settings: Settings
) -> dict[int, list[float]]:
    cache = load_embedding_cache(settings.embedding_cache_path)
    client = OllamaEmbeddingClient(settings)
    embeddings: dict[int, list[float]] = {}

    for index, record in enumerate(records):
        cache_key = embedding_cache_key(record)
        vector = cache.get(cache_key)
        if vector is None:
            vector = client.embed(record.embedding_text)
            cache[cache_key] = vector
            if settings.EMBEDDING_CACHE_ENABLED:
                append_embedding_cache(settings.embedding_cache_path, cache_key, vector)
            time.sleep(0.01)
        embeddings[index] = vector

    return embeddings


def load_embedding_cache(path: Path) -> dict[str, list[float]]:
    cache: dict[str, list[float]] = {}
    if not path.exists():
        return cache

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = payload.get("key")
            vector = payload.get("embedding")
            if isinstance(key, str) and isinstance(vector, list):
                cache[key] = [float(value) for value in vector]
    return cache


def append_embedding_cache(path: Path, key: str, vector: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"key": key, "embedding": vector}
    with path.open("a", encoding="utf-8", errors="ignore") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def embedding_cache_key(record: RelationshipRecord) -> str:
    digest = hashlib.sha256(record.embedding_text.encode("utf-8", errors="ignore")).hexdigest()
    return f"{record.source_path}|{record.modified_epoch}|{digest}"


def build_candidate_relations(
    records: list[RelationshipRecord],
    embeddings: dict[int, list[float]],
    settings: Settings,
) -> list[CandidateRelation]:
    worker_count = resolve_relationship_workers(settings, len(records))
    citation_pairs = (
        collect_citation_pairs_parallel(records, worker_count)
        if settings.RELATIONSHIP_USE_TEXT_CITATIONS
        else {}
    )
    candidate_pairs = collect_candidate_pairs(records, embeddings, settings)
    candidate_pairs.update(citation_pairs)
    sorted_pairs = sorted(candidate_pairs)

    if should_parallelize_pairs(worker_count, len(sorted_pairs)):
        relations = score_candidate_pairs_parallel(
            sorted_pairs,
            records,
            embeddings,
            settings,
            citation_pairs,
            worker_count,
        )
    else:
        relations = [
            relation
            for relation in (
                score_pair(
                    records[left],
                    records[right],
                    left,
                    right,
                    embeddings,
                    settings,
                    citation_count=citation_pairs.get((left, right), 0),
                )
                for left, right in sorted_pairs
            )
            if relation.relation_score >= settings.RELATIONSHIP_MIN_SCORE
        ]

    relations.sort(key=lambda item: item.relation_score, reverse=True)
    return relations


def resolve_relationship_workers(settings: Settings, record_count: int) -> int:
    if record_count < MIN_PARALLEL_RELATION_RECORDS:
        return 1

    configured_workers = settings.RELATIONSHIP_WORKERS
    if configured_workers is not None:
        return max(1, configured_workers)

    cpu_count = os.cpu_count() or 1
    inferred_workers = cpu_count - 1 if cpu_count > 1 else 1
    return max(1, min(8, inferred_workers))


def should_parallelize_pairs(worker_count: int, pair_count: int) -> bool:
    return worker_count > 1 and pair_count >= MIN_PARALLEL_RELATION_PAIRS


def collect_citation_pairs_parallel(
    records: list[RelationshipRecord], worker_count: int
) -> dict[tuple[int, int], int]:
    if worker_count <= 1 or len(records) < MIN_PARALLEL_CITATION_RECORDS:
        return collect_citation_pairs(records)

    alias_index = build_alias_index(records)
    if not alias_index:
        return {}

    citation_payloads = [
        (index, record.citation_text)
        for index, record in enumerate(records)
        if record.citation_text
    ]
    if not citation_payloads:
        return {}

    chunks = chunk_sequence(
        citation_payloads,
        chunk_size_for(len(citation_payloads), worker_count),
    )
    citation_pairs: dict[tuple[int, int], int] = defaultdict(int)
    with ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=init_citation_worker,
        initargs=(alias_index,),
    ) as executor:
        for partial in executor.map(
            collect_citation_pairs_chunk_worker,
            chunks,
        ):
            for pair, count in partial.items():
                citation_pairs[pair] += count
    return dict(citation_pairs)


def init_citation_worker(alias_index: dict[str, int]) -> None:
    global _CITATION_ALIAS_INDEX
    _CITATION_ALIAS_INDEX = alias_index


def collect_citation_pairs_chunk_worker(
    citation_payloads: Sequence[tuple[int, str]],
) -> dict[tuple[int, int], int]:
    return collect_citation_pairs_chunk(citation_payloads, _CITATION_ALIAS_INDEX)


def collect_citation_pairs_chunk(
    citation_payloads: Sequence[tuple[int, str]],
    alias_index: dict[str, int],
) -> dict[tuple[int, int], int]:
    citation_pairs: dict[tuple[int, int], int] = defaultdict(int)
    for source_index, citation_text in citation_payloads:
        for alias, target_index in alias_index.items():
            if source_index == target_index:
                continue
            if alias in citation_text:
                citation_pairs[normalize_pair(source_index, target_index)] += 1
    return dict(citation_pairs)


def score_candidate_pairs_parallel(
    sorted_pairs: list[tuple[int, int]],
    records: list[RelationshipRecord],
    embeddings: dict[int, list[float]],
    settings: Settings,
    citation_pairs: dict[tuple[int, int], int],
    worker_count: int,
) -> list[CandidateRelation]:
    chunks = chunk_sequence(
        sorted_pairs,
        chunk_size_for(len(sorted_pairs), worker_count),
    )
    with ProcessPoolExecutor(
        max_workers=worker_count,
        initializer=init_score_worker,
        initargs=(records, embeddings, settings, citation_pairs),
    ) as executor:
        relation_chunks = executor.map(
            score_candidate_pairs_chunk_worker,
            chunks,
        )
    return [relation for chunk in relation_chunks for relation in chunk]


def init_score_worker(
    records: list[RelationshipRecord],
    embeddings: dict[int, list[float]],
    settings: Settings,
    citation_pairs: dict[tuple[int, int], int],
) -> None:
    global _SCORE_RECORDS
    global _SCORE_EMBEDDINGS
    global _SCORE_SETTINGS
    global _SCORE_CITATION_PAIRS
    _SCORE_RECORDS = records
    _SCORE_EMBEDDINGS = embeddings
    _SCORE_SETTINGS = settings
    _SCORE_CITATION_PAIRS = citation_pairs


def score_candidate_pairs_chunk_worker(
    pairs: Sequence[tuple[int, int]]
) -> list[CandidateRelation]:
    if _SCORE_SETTINGS is None:
        raise RuntimeError("Relationship scoring worker was not initialized.")
    return score_candidate_pairs_chunk(
        pairs,
        _SCORE_RECORDS,
        _SCORE_EMBEDDINGS,
        _SCORE_SETTINGS,
        _SCORE_CITATION_PAIRS,
    )


def score_candidate_pairs_chunk(
    pairs: Sequence[tuple[int, int]],
    records: list[RelationshipRecord],
    embeddings: dict[int, list[float]],
    settings: Settings,
    citation_pairs: dict[tuple[int, int], int],
) -> list[CandidateRelation]:
    relations: list[CandidateRelation] = []
    for left, right in pairs:
        relation = score_pair(
            records[left],
            records[right],
            left,
            right,
            embeddings,
            settings,
            citation_count=citation_pairs.get((left, right), 0),
        )
        if relation.relation_score >= settings.RELATIONSHIP_MIN_SCORE:
            relations.append(relation)
    return relations


def chunk_size_for(item_count: int, worker_count: int) -> int:
    if item_count <= 0:
        return 1
    return max(1, math.ceil(item_count / max(1, worker_count * PARALLEL_BATCH_TARGET)))


def chunk_sequence(items: Sequence[T], chunk_size: int) -> list[Sequence[T]]:
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def collect_candidate_pairs(
    records: list[RelationshipRecord],
    embeddings: dict[int, list[float]],
    settings: Settings,
) -> set[tuple[int, int]]:
    return collect_pairs(DEFAULT_PAIR_COLLECTORS, records, embeddings, settings)


def score_pair(
    left_record: RelationshipRecord,
    right_record: RelationshipRecord,
    left: int,
    right: int,
    embeddings: dict[int, list[float]],
    settings: Settings,
    citation_count: int = 0,
) -> CandidateRelation:
    filename = filename_similarity(left_record, right_record)
    time_score = time_proximity(left_record, right_record, settings)
    path_score = path_proximity(left_record, right_record)
    embedding_score = (
        cosine_similarity(embeddings[left], embeddings[right])
        if left in embeddings and right in embeddings
        else 0.0
    )
    type_score = type_compatibility(left_record, right_record)
    citation_score = min(1.0, citation_count / 2) if citation_count else 0.0

    if embeddings:
        relation_score = (
            filename * 0.27
            + time_score * 0.15
            + path_score * 0.10
            + embedding_score * 0.33
            + type_score * 0.10
            + citation_score * 0.05
        )
    else:
        relation_score = (
            filename * 0.40
            + time_score * 0.20
            + path_score * 0.20
            + type_score * 0.15
            + citation_score * 0.05
        )

    signals = build_signals(
        left_record,
        right_record,
        filename,
        time_score,
        path_score,
        embedding_score,
        type_score,
        citation_count,
        embeddings_enabled=bool(embeddings),
    )
    return CandidateRelation(
        left=left,
        right=right,
        relation_score=round(relation_score, 4),
        filename_similarity=round(filename, 4),
        time_proximity=round(time_score, 4),
        path_proximity=round(path_score, 4),
        embedding_similarity=round(embedding_score, 4),
        type_compatibility=round(type_score, 4),
        citation_count=citation_count,
        signals=signals,
    )


def filename_similarity(left: RelationshipRecord, right: RelationshipRecord) -> float:
    sequence_score = SequenceMatcher(
        None, left.normalized_name, right.normalized_name
    ).ratio()
    left_tokens = set(tokenize(left.normalized_name))
    right_tokens = set(tokenize(right.normalized_name))
    token_score = jaccard(left_tokens, right_tokens)
    version_bonus = 0.12 if has_version_signal(left.normalized_name, right.normalized_name) else 0.0
    return min(1.0, max(sequence_score, token_score) + version_bonus)


def time_proximity(
    left: RelationshipRecord, right: RelationshipRecord, settings: Settings
) -> float:
    left_time = left.modified_epoch or left.created_epoch
    right_time = right.modified_epoch or right.created_epoch
    if not left_time or not right_time:
        return 0.0

    delta_days = abs(left_time - right_time) / 86400
    return math.exp(-delta_days / settings.RELATIONSHIP_TIME_DECAY_DAYS)


def path_proximity(left: RelationshipRecord, right: RelationshipRecord) -> float:
    left_parts = Path(left.relative_path).parent.parts
    right_parts = Path(right.relative_path).parent.parts
    if not left_parts and not right_parts:
        return 1.0

    common = 0
    for left_part, right_part in zip(left_parts, right_parts):
        if left_part != right_part:
            break
        common += 1
    return common / max(len(left_parts), len(right_parts), 1)


def type_compatibility(left: RelationshipRecord, right: RelationshipRecord) -> float:
    if left.category == right.category:
        return 1.0
    complementary = {
        frozenset({"Architecture", "Design"}),
        frozenset({"Design", "Implementation"}),
        frozenset({"Architecture", "Implementation"}),
        frozenset({"Architecture", "Research"}),
        frozenset({"Design", "Business"}),
        frozenset({"Implementation", "Operations"}),
        frozenset({"Implementation", "CaseStudy"}),
        frozenset({"Operations", "CaseStudy"}),
        frozenset({"Research", "Thinking"}),
        frozenset({"Business", "Thinking"}),
        frozenset({"Thinking", "Series"}),
    }
    if frozenset({left.category, right.category}) in complementary:
        return 0.65
    return 0.25


def build_signals(
    left: RelationshipRecord,
    right: RelationshipRecord,
    filename: float,
    time_score: float,
    path_score: float,
    embedding_score: float,
    type_score: float,
    citation_count: int,
    embeddings_enabled: bool,
) -> list[str]:
    signals: list[str] = []
    if filename >= 0.72:
        signals.append("filename")
    if time_score >= 0.72:
        signals.append("time")
    if path_score >= 0.8:
        signals.append("path")
    if type_score >= 0.8:
        signals.append("category")
    if embeddings_enabled and embedding_score >= 0.78:
        signals.append("embedding")
    if citation_count:
        signals.append("citation")
    if has_version_signal(left.normalized_name, right.normalized_name):
        signals.append("version_or_sequence")
    return signals


def write_relations(
    candidates: Iterable[CandidateRelation],
    records: list[RelationshipRecord],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", errors="ignore") as handle:
        for candidate in candidates:
            left = records[candidate.left]
            right = records[candidate.right]
            payload = {
                "left": redacted_record(left),
                "right": redacted_record(right),
                "relation_score": candidate.relation_score,
                "filename_similarity": candidate.filename_similarity,
                "time_proximity": candidate.time_proximity,
                "path_proximity": candidate.path_proximity,
                "embedding_similarity": candidate.embedding_similarity,
                "type_compatibility": candidate.type_compatibility,
                "citation_count": candidate.citation_count,
                "signals": candidate.signals,
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_clusters(
    candidates: list[CandidateRelation],
    records: list[RelationshipRecord],
    path: Path,
) -> None:
    parent = list(range(len(records)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for candidate in candidates:
        union(candidate.left, candidate.right)

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(records)):
        grouped[find(index)].append(index)

    clusters = []
    for indexes in grouped.values():
        if len(indexes) < 2:
            continue
        cluster_records = [records[index] for index in indexes]
        clusters.append(
            {
                "size": len(cluster_records),
                "categories": sorted({record.category for record in cluster_records}),
                "files": [redacted_record(record) for record in cluster_records],
            }
        )

    clusters.sort(key=lambda item: item["size"], reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", errors="ignore") as handle:
        json.dump({"clusters": clusters}, handle, ensure_ascii=False, indent=2)


def redacted_record(record: RelationshipRecord) -> dict[str, Any]:
    return {
        "relative_path": record.relative_path,
        "quality": record.quality,
        "category": record.category,
        "document_kind": record.document_kind,
        "topic_tags": record.topic_tags,
    }


def normalize_name(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\[[^\]]+\]|\([^)]*\)|【[^】]+】", " ", value)
    value = re.sub(r"(?i)\b(sample|ppt|pdf|docx|final|copy|副本)\b", " ", value)
    value = re.sub(r"[_\-—–:：|]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def has_version_signal(left: str, right: str) -> bool:
    return bool(VERSION_PATTERN.search(left) or VERSION_PATTERN.search(right))


def sanitize_text(value: str) -> str:
    return value.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-relationships",
        description="Mine filename/time/path/optional-embedding relationships from DocTriage decisions.",
    )
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--llm-endpoint")
    parser.add_argument("--llm-model")
    parser.add_argument("--embedding-endpoint")
    parser.add_argument("--embedding-model")
    parser.add_argument("--relationship-min-score", type=float)
    parser.add_argument("--relationship-max-records", type=int)
    parser.add_argument("--relationship-workers", type=int)
    parser.add_argument("--embedding-text-max-chars", type=int)
    parser.add_argument("--use-embeddings", action="store_true")
    parser.add_argument("--use-text-citations", action="store_true")
    parser.add_argument("--require-local-llm", action="store_true")
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
    if args.embedding_endpoint is not None:
        overrides["EMBEDDING_ENDPOINT"] = args.embedding_endpoint
    if args.embedding_model is not None:
        overrides["EMBEDDING_MODEL"] = args.embedding_model
    if args.relationship_min_score is not None:
        overrides["RELATIONSHIP_MIN_SCORE"] = args.relationship_min_score
    if args.relationship_max_records is not None:
        overrides["RELATIONSHIP_MAX_RECORDS"] = args.relationship_max_records
    if args.relationship_workers is not None:
        overrides["RELATIONSHIP_WORKERS"] = args.relationship_workers
    if args.embedding_text_max_chars is not None:
        overrides["EMBEDDING_TEXT_MAX_CHARS"] = args.embedding_text_max_chars
    if args.use_embeddings:
        overrides["RELATIONSHIP_USE_EMBEDDINGS"] = True
    if args.use_text_citations:
        overrides["RELATIONSHIP_USE_TEXT_CITATIONS"] = True
    if args.require_local_llm:
        overrides["REQUIRE_LOCAL_LLM"] = True

    if overrides:
        return Settings(**overrides)
    return get_settings()


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    mine_relationships(build_settings_from_args(args))


if __name__ == "__main__":
    main()
