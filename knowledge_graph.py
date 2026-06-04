from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import Settings, get_settings

NodeType = Literal[
    "Document",
    "Cluster",
    "Category",
    "Topic",
    "DocumentKind",
    "IngestionPolicy",
]
EdgeType = Literal[
    "RELATED_TO",
    "SAME_SERIES",
    "NEAR_DUPLICATE",
    "EVOLVES_TO",
    "SAME_TOPIC",
    "BELONGS_TO",
    "TAGGED_AS",
    "HAS_KIND",
    "ROUTED_BY",
]
TERMINAL_DECISION_STATUSES = {
    "planned",
    "success",
    "success_overwritten_changed_target",
    "skipped_existing_target",
}


@dataclass(slots=True)
class DocumentNode:
    id: str
    type: NodeType
    relative_path: str
    target_path: str
    title: str
    category: str
    quality: int
    status: str
    document_kind: str = "Unknown"
    topic_tags: list[str] = field(default_factory=list)
    summary: str = ""
    reason: str = ""
    knowledge_density: int = 0
    implementation_specificity: int = 0
    logical_structure: int = 0
    evidence_richness: int = 0
    actionability: int = 0
    strategic_value: int = 0
    freshness: int = 0
    uniqueness: int = 0
    sensitivity_risk: int = 0
    public_writing_suitability: int = 0
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "relative_path": self.relative_path,
            "target_path": self.target_path,
            "title": self.title,
            "category": self.category,
            "document_kind": self.document_kind,
            "topic_tags": self.topic_tags,
            "quality": self.quality,
            "status": self.status,
            "summary": self.summary,
            "reason": self.reason,
            "knowledge_density": self.knowledge_density,
            "implementation_specificity": self.implementation_specificity,
            "logical_structure": self.logical_structure,
            "evidence_richness": self.evidence_richness,
            "actionability": self.actionability,
            "strategic_value": self.strategic_value,
            "freshness": self.freshness,
            "uniqueness": self.uniqueness,
            "sensitivity_risk": self.sensitivity_risk,
            "public_writing_suitability": self.public_writing_suitability,
            "attributes": self.attributes,
        }


@dataclass(slots=True)
class KnowledgeNode:
    id: str
    type: NodeType
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "attributes": self.attributes,
        }


@dataclass(slots=True)
class RelationshipEdge:
    id: str
    type: EdgeType
    source: str
    target: str
    weight: float
    confidence: float
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass(slots=True)
class IngestionPolicy:
    id: str
    action: Literal["ingest", "archive", "review"]
    min_quality: int
    target_collection: str
    rationale: str

    def to_node(self) -> KnowledgeNode:
        return KnowledgeNode(
            id=self.id,
            type="IngestionPolicy",
            label=self.action,
            attributes={
                "action": self.action,
                "min_quality": self.min_quality,
                "target_collection": self.target_collection,
                "rationale": self.rationale,
            },
        )


@dataclass(slots=True)
class KnowledgeGraph:
    schema_version: str
    documents: list[DocumentNode] = field(default_factory=list)
    nodes: list[KnowledgeNode] = field(default_factory=list)
    edges: list[RelationshipEdge] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "metadata": self.metadata,
            "documents": [document.to_dict() for document in self.documents],
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


def build_knowledge_graph(settings: Settings | None = None) -> KnowledgeGraph:
    current_settings = settings or get_settings()
    decisions_path = current_settings.processed_log_path.parent / "decisions.jsonl"
    relations_path = current_settings.relationship_relations_path

    documents = load_document_nodes(decisions_path, current_settings)
    document_by_path = {document.relative_path: document for document in documents}

    nodes: list[KnowledgeNode] = []
    edges: list[RelationshipEdge] = []

    category_nodes = build_category_nodes(documents)
    nodes.extend(category_nodes)
    edges.extend(build_category_edges(documents))

    topic_nodes = build_topic_nodes(documents)
    nodes.extend(topic_nodes)
    edges.extend(build_topic_edges(documents))

    kind_nodes = build_document_kind_nodes(documents)
    nodes.extend(kind_nodes)
    edges.extend(build_document_kind_edges(documents))

    policy_nodes, policy_edges = build_policy_projection(documents, current_settings)
    nodes.extend(policy_nodes)
    edges.extend(policy_edges)

    relation_edges = load_relation_edges(relations_path, document_by_path)
    edges.extend(relation_edges)

    cluster_nodes, cluster_edges = build_cluster_projection(documents, relation_edges)
    nodes.extend(cluster_nodes)
    edges.extend(cluster_edges)
    deduped_edges = deduplicate_edges(edges)

    return KnowledgeGraph(
        schema_version="pre_rag_kg.v1",
        documents=documents,
        nodes=nodes,
        edges=deduped_edges,
        metadata={
            "document_count": len(documents),
            "node_count": len(nodes) + len(documents),
            "edge_count": len(deduped_edges),
            "source": {
                "decisions_path": str(decisions_path),
                "relations_path": str(relations_path),
            },
        },
    )


def load_document_nodes(path: Path, settings: Settings) -> list[DocumentNode]:
    if not path.exists():
        raise FileNotFoundError(f"Decision log does not exist: {path}")

    documents_by_path: dict[str, DocumentNode] = {}
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
            if not relative_path:
                continue
            status = str(payload.get("status") or "")
            if status and status not in TERMINAL_DECISION_STATUSES:
                continue

            category = str(payload.get("category") or "LowQuality")
            quality = coerce_int(payload.get("quality"), 0)
            document = DocumentNode(
                id=document_id(relative_path),
                type="Document",
                relative_path=relative_path,
                target_path=str(payload.get("target_path") or ""),
                title=Path(relative_path).stem,
                category=category,
                document_kind=str(payload.get("document_kind") or "Unknown"),
                topic_tags=coerce_string_list(payload.get("topic_tags")),
                quality=quality,
                status=status,
                summary=str(payload.get("summary") or ""),
                reason=str(payload.get("reason") or ""),
                knowledge_density=coerce_int(payload.get("knowledge_density"), 0),
                implementation_specificity=coerce_int(
                    payload.get("implementation_specificity"), 0
                ),
                logical_structure=coerce_int(payload.get("logical_structure"), 0),
                evidence_richness=coerce_int(payload.get("evidence_richness"), 0),
                actionability=coerce_int(payload.get("actionability"), 0),
                strategic_value=coerce_int(payload.get("strategic_value"), 0),
                freshness=coerce_int(payload.get("freshness"), 0),
                uniqueness=coerce_int(payload.get("uniqueness"), 0),
                sensitivity_risk=coerce_int(payload.get("sensitivity_risk"), 0),
                public_writing_suitability=coerce_int(
                    payload.get("public_writing_suitability"), 0
                ),
                attributes={
                    "source_path": str(payload.get("source_path") or ""),
                    "ingestion_action": infer_ingestion_action(quality, settings),
                },
            )
            documents_by_path[relative_path] = document
    return list(documents_by_path.values())


def build_category_nodes(documents: list[DocumentNode]) -> list[KnowledgeNode]:
    category_counts = Counter(document.category for document in documents)
    return [
        KnowledgeNode(
            id=category_id(category),
            type="Category",
            label=category,
            attributes={"document_count": count},
        )
        for category, count in sorted(category_counts.items())
    ]


def build_category_edges(documents: list[DocumentNode]) -> list[RelationshipEdge]:
    edges: list[RelationshipEdge] = []
    for document in documents:
        edges.append(
            RelationshipEdge(
                id=edge_id(document.id, category_id(document.category), "BELONGS_TO"),
                type="BELONGS_TO",
                source=document.id,
                target=category_id(document.category),
                weight=1.0,
                confidence=1.0,
                evidence={"category": document.category},
            )
        )
    return edges


def build_topic_nodes(documents: list[DocumentNode]) -> list[KnowledgeNode]:
    topic_counts = Counter(
        topic for document in documents for topic in document.topic_tags if topic
    )
    return [
        KnowledgeNode(
            id=topic_id(topic),
            type="Topic",
            label=topic,
            attributes={"document_count": count},
        )
        for topic, count in sorted(topic_counts.items())
    ]


def build_topic_edges(documents: list[DocumentNode]) -> list[RelationshipEdge]:
    edges: list[RelationshipEdge] = []
    for document in documents:
        for topic in document.topic_tags:
            if not topic:
                continue
            edges.append(
                RelationshipEdge(
                    id=edge_id(document.id, topic_id(topic), "TAGGED_AS"),
                    type="TAGGED_AS",
                    source=document.id,
                    target=topic_id(topic),
                    weight=1.0,
                    confidence=1.0,
                    evidence={"topic": topic},
                )
            )
    return edges


def build_document_kind_nodes(documents: list[DocumentNode]) -> list[KnowledgeNode]:
    kind_counts = Counter(document.document_kind or "Unknown" for document in documents)
    return [
        KnowledgeNode(
            id=document_kind_id(kind),
            type="DocumentKind",
            label=kind,
            attributes={"document_count": count},
        )
        for kind, count in sorted(kind_counts.items())
    ]


def build_document_kind_edges(documents: list[DocumentNode]) -> list[RelationshipEdge]:
    edges: list[RelationshipEdge] = []
    for document in documents:
        kind = document.document_kind or "Unknown"
        edges.append(
            RelationshipEdge(
                id=edge_id(document.id, document_kind_id(kind), "HAS_KIND"),
                type="HAS_KIND",
                source=document.id,
                target=document_kind_id(kind),
                weight=1.0,
                confidence=1.0,
                evidence={"document_kind": kind},
            )
        )
    return edges


def build_policy_projection(
    documents: list[DocumentNode], settings: Settings
) -> tuple[list[KnowledgeNode], list[RelationshipEdge]]:
    policies = [
        IngestionPolicy(
            id="policy:ingest_hq",
            action="ingest",
            min_quality=settings.QUALITY_THRESHOLD,
            target_collection="HQ",
            rationale="High-quality documents are eligible for RAG ingestion.",
        ),
        IngestionPolicy(
            id="policy:archive_lq",
            action="archive",
            min_quality=0,
            target_collection="LQ_Archive",
            rationale="Low-quality documents should be archived or reviewed before ingestion.",
        ),
    ]
    policy_nodes = [policy.to_node() for policy in policies]
    edges: list[RelationshipEdge] = []

    for document in documents:
        policy = policies[0] if document.quality >= settings.QUALITY_THRESHOLD else policies[1]
        edges.append(
            RelationshipEdge(
                id=edge_id(document.id, policy.id, "ROUTED_BY"),
                type="ROUTED_BY",
                source=document.id,
                target=policy.id,
                weight=1.0,
                confidence=1.0,
                evidence={
                    "quality": document.quality,
                    "threshold": settings.QUALITY_THRESHOLD,
                },
            )
        )
    return policy_nodes, edges


def load_relation_edges(
    path: Path, document_by_path: dict[str, DocumentNode]
) -> list[RelationshipEdge]:
    if not path.exists():
        return []

    edges: list[RelationshipEdge] = []
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
            left = document_by_path.get(left_path)
            right = document_by_path.get(right_path)
            if not left or not right:
                continue

            relation_type = infer_relation_type(payload)
            score = coerce_float(payload.get("relation_score"), 0.0)
            edges.append(
                RelationshipEdge(
                    id=edge_id(left.id, right.id, relation_type),
                    type=relation_type,
                    source=left.id,
                    target=right.id,
                    weight=score,
                    confidence=score,
                    evidence={
                        "signals": payload.get("signals", []),
                        "filename_similarity": payload.get("filename_similarity", 0),
                        "time_proximity": payload.get("time_proximity", 0),
                        "path_proximity": payload.get("path_proximity", 0),
                        "embedding_similarity": payload.get("embedding_similarity", 0),
                        "citation_count": payload.get("citation_count", 0),
                        "type_compatibility": payload.get("type_compatibility", 0),
                    },
                )
            )
    return edges


def build_cluster_projection(
    documents: list[DocumentNode], relation_edges: list[RelationshipEdge]
) -> tuple[list[KnowledgeNode], list[RelationshipEdge]]:
    if not relation_edges:
        return [], []

    document_ids = [document.id for document in documents]
    parent = {node_id: node_id for node_id in document_ids}

    def find(node_id: str) -> str:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for edge in relation_edges:
        if edge.source in parent and edge.target in parent:
            union(edge.source, edge.target)

    grouped: dict[str, list[str]] = defaultdict(list)
    for node_id in document_ids:
        grouped[find(node_id)].append(node_id)

    cluster_nodes: list[KnowledgeNode] = []
    cluster_edges: list[RelationshipEdge] = []
    for index, members in enumerate(
        [members for members in grouped.values() if len(members) > 1], start=1
    ):
        cluster_node = KnowledgeNode(
            id=f"cluster:{index}",
            type="Cluster",
            label=f"Cluster {index}",
            attributes={"size": len(members)},
        )
        cluster_nodes.append(cluster_node)
        for member_id in members:
            cluster_edges.append(
                RelationshipEdge(
                    id=edge_id(member_id, cluster_node.id, "BELONGS_TO"),
                    type="BELONGS_TO",
                    source=member_id,
                    target=cluster_node.id,
                    weight=1.0,
                    confidence=1.0,
                    evidence={"projection": "relation_connected_component"},
                )
            )
    return cluster_nodes, cluster_edges


def infer_relation_type(payload: dict[str, Any]) -> EdgeType:
    signals = set(payload.get("signals") or [])
    filename_similarity = coerce_float(payload.get("filename_similarity"), 0.0)
    embedding_similarity = coerce_float(payload.get("embedding_similarity"), 0.0)

    if "version_or_sequence" in signals:
        return "EVOLVES_TO"
    if filename_similarity >= 0.92 and embedding_similarity >= 0.90:
        return "NEAR_DUPLICATE"
    if "filename" in signals and "time" in signals:
        return "SAME_SERIES"
    if "embedding" in signals:
        return "SAME_TOPIC"
    return "RELATED_TO"


def infer_ingestion_action(quality: int, settings: Settings) -> str:
    if quality >= settings.QUALITY_THRESHOLD:
        return "ingest"
    return "archive"


def export_knowledge_graph(settings: Settings | None = None) -> Path:
    current_settings = settings or get_settings()
    graph = build_knowledge_graph(current_settings)
    output_path = current_settings.relationship_dir / "knowledge_graph.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", errors="ignore") as handle:
        json.dump(graph.to_dict(), handle, ensure_ascii=False, indent=2)
    return output_path


def deduplicate_edges(edges: list[RelationshipEdge]) -> list[RelationshipEdge]:
    deduped: dict[str, RelationshipEdge] = {}
    for edge in edges:
        deduped[edge.id] = edge
    return list(deduped.values())


def document_id(relative_path: str) -> str:
    return "doc:" + stable_hash(relative_path)


def category_id(category: str) -> str:
    return f"category:{category}"


def topic_id(topic: str) -> str:
    return "topic:" + stable_hash(topic)


def document_kind_id(kind: str) -> str:
    return "document_kind:" + stable_hash(kind)


def edge_id(source: str, target: str, edge_type: str) -> str:
    return "edge:" + stable_hash(f"{edge_type}|{source}|{target}")


def stable_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-graph",
        description="Export DocTriage decisions and mined relations as a Pre-RAG knowledge graph.",
    )
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--llm-endpoint")
    parser.add_argument("--llm-model")
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
    output_path = export_knowledge_graph(build_settings_from_args(args))
    print(output_path)


if __name__ == "__main__":
    main()
