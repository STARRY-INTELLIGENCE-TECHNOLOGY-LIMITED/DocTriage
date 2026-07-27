from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_RAG_VECTOR_STORE_TYPE = "local_jsonl"
DEFAULT_QDRANT_COLLECTION = "doctriage_rag"
QDRANT_POINT_NAMESPACE = uuid.UUID("1ae2698d-f785-55cf-b327-7f68e8be2058")
QDRANT_PAYLOAD_KEYS = (
    "chunk_id",
    "document_id",
    "relative_path",
    "source_path",
    "title",
    "category",
    "document_kind",
    "topic_tags",
    "quality",
    "summary",
    "text",
    "text_chars",
    "chunk_index",
    "text_sha256",
    "redaction_enabled",
)


def normalize_vector_store_type(value: str | None) -> str:
    normalized = str(value or DEFAULT_RAG_VECTOR_STORE_TYPE).strip().lower()
    aliases = {
        "local": "local_jsonl",
        "jsonl": "local_jsonl",
        "local-jsonl": "local_jsonl",
        "qdrant-local": "qdrant_local",
        "local_qdrant": "qdrant_local",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in {"local_jsonl", "qdrant_local"}:
        raise ValueError(
            f"Unsupported RAG vector store type: {value}. "
            "Use local_jsonl or qdrant_local."
        )
    return normalized


def qdrant_point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(QDRANT_POINT_NAMESPACE, str(chunk_id)))


def sync_qdrant_local_index(
    path: Path,
    collection: str,
    chunks: Sequence[dict[str, Any]],
    vectors: dict[str, list[float]],
) -> dict[str, Any]:
    QdrantClient, models = _qdrant_api()
    resolved_path = Path(path).expanduser().resolve()
    resolved_path.mkdir(parents=True, exist_ok=True)
    collection_name = _collection_name(collection)
    chunk_by_id = {
        str(chunk.get("chunk_id") or ""): chunk
        for chunk in chunks
        if str(chunk.get("chunk_id") or "")
    }
    indexed = [
        (chunk_id, vector, chunk_by_id[chunk_id])
        for chunk_id, vector in vectors.items()
        if chunk_id in chunk_by_id and vector
    ]
    dimensions = {len(vector) for _, vector, _ in indexed}
    if len(dimensions) > 1:
        raise ValueError("Qdrant Local vectors must all have the same dimension.")

    client = QdrantClient(path=str(resolved_path))
    try:
        collection_exists = bool(client.collection_exists(collection_name))
        existing_ids: set[str | int] = set()
        if collection_exists:
            info = client.get_collection(collection_name)
            existing_dimension = _vector_dimension(info)
            expected_dimension = next(iter(dimensions), existing_dimension)
            if existing_dimension and expected_dimension != existing_dimension:
                raise ValueError(
                    f"Qdrant Local collection '{collection_name}' uses dimension "
                    f"{existing_dimension}, but the current embedding model returned "
                    f"{expected_dimension}. Use a new collection name."
                )
            existing_ids = _scroll_point_ids(client, collection_name)
        if not indexed:
            if existing_ids:
                client.delete(
                    collection_name,
                    points_selector=models.PointIdsList(points=list(existing_ids)),
                    wait=True,
                )
            return {
                "ok": True,
                "reachable": True,
                "store_type": "qdrant_local",
                "path": str(resolved_path),
                "collection": collection_name,
                "collection_exists": collection_exists,
                "vector_count": 0,
                "vector_dimension": 0,
            }

        dimension = dimensions.pop()
        if not collection_exists:
            client.create_collection(
                collection_name,
                vectors_config=models.VectorParams(
                    size=dimension,
                    distance=models.Distance.COSINE,
                ),
            )
        current_ids: set[str] = set()
        for batch in _batches(indexed, 128):
            points = [
                models.PointStruct(
                    id=qdrant_point_id(chunk_id),
                    vector=vector,
                    payload={key: chunk.get(key) for key in QDRANT_PAYLOAD_KEYS},
                )
                for chunk_id, vector, chunk in batch
            ]
            current_ids.update(str(point.id) for point in points)
            client.upsert(collection_name, points=points, wait=True)
        stale_ids = {
            point_id for point_id in existing_ids if str(point_id) not in current_ids
        }
        if stale_ids:
            client.delete(
                collection_name,
                points_selector=models.PointIdsList(points=list(stale_ids)),
                wait=True,
            )
        count = int(client.count(collection_name, exact=True).count)
        if count != len(indexed):
            raise RuntimeError(
                f"Qdrant Local synchronization expected {len(indexed)} points, "
                f"but collection '{collection_name}' contains {count}."
            )
        return {
            "ok": count == len(indexed),
            "reachable": True,
            "store_type": "qdrant_local",
            "path": str(resolved_path),
            "collection": collection_name,
            "collection_exists": True,
            "vector_count": count,
            "vector_dimension": dimension,
        }
    finally:
        client.close()


def search_qdrant_local_index(
    path: Path,
    collection: str,
    query_vector: Sequence[float],
    *,
    limit: int,
) -> dict[str, Any]:
    QdrantClient, _ = _qdrant_api()
    resolved_path = Path(path).expanduser().resolve()
    collection_name = _collection_name(collection)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Qdrant Local path does not exist: {resolved_path}")
    client = QdrantClient(path=str(resolved_path))
    try:
        if not client.collection_exists(collection_name):
            raise FileNotFoundError(
                f"Qdrant Local collection does not exist: {collection_name}"
            )
        count = int(client.count(collection_name, exact=True).count)
        response = client.query_points(
            collection_name,
            query=[float(value) for value in query_vector],
            limit=max(1, min(int(limit), max(1, count))),
            with_payload=True,
            with_vectors=False,
        )
        scores: dict[str, float] = {}
        for point in response.points:
            payload = point.payload or {}
            chunk_id = str(payload.get("chunk_id") or "")
            if chunk_id:
                scores[chunk_id] = float(point.score)
        info = client.get_collection(collection_name)
        return {
            "scores": scores,
            "vector_count": count,
            "vector_dimension": _vector_dimension(info),
        }
    finally:
        client.close()


def inspect_qdrant_local_index(path: Path, collection: str) -> dict[str, Any]:
    QdrantClient, _ = _qdrant_api()
    resolved_path = Path(path).expanduser().resolve()
    resolved_path.mkdir(parents=True, exist_ok=True)
    collection_name = _collection_name(collection)
    client = QdrantClient(path=str(resolved_path))
    try:
        exists = bool(client.collection_exists(collection_name))
        vector_count = 0
        vector_dimension = 0
        if exists:
            vector_count = int(client.count(collection_name, exact=True).count)
            vector_dimension = _vector_dimension(client.get_collection(collection_name))
        return {
            "ok": exists,
            "reachable": True,
            "store_type": "qdrant_local",
            "path": str(resolved_path),
            "collection": collection_name,
            "collection_checked": True,
            "collection_exists": exists,
            "vector_count": vector_count,
            "vector_dimension": vector_dimension,
            "message": (
                f"Qdrant Local collection '{collection_name}' is ready."
                if exists
                else f"Qdrant Local is ready, but collection '{collection_name}' has not been built."
            ),
        }
    finally:
        client.close()


def _qdrant_api() -> tuple[Any, Any]:
    try:
        from qdrant_client import QdrantClient, models
    except ImportError as exc:
        raise RuntimeError(
            "Qdrant Local requires qdrant-client. Install the project dependencies first."
        ) from exc
    return QdrantClient, models


def _collection_name(value: str) -> str:
    collection = str(value or DEFAULT_QDRANT_COLLECTION).strip()
    if not collection:
        return DEFAULT_QDRANT_COLLECTION
    return collection


def _vector_dimension(collection_info: Any) -> int:
    vectors = collection_info.config.params.vectors
    if hasattr(vectors, "size"):
        return int(vectors.size)
    if isinstance(vectors, dict) and vectors:
        first = next(iter(vectors.values()))
        return int(getattr(first, "size", 0) or 0)
    return 0


def _scroll_point_ids(client: Any, collection: str) -> set[str | int]:
    point_ids: set[str | int] = set()
    offset: Any = None
    while True:
        points, offset = client.scroll(
            collection,
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        point_ids.update(point.id for point in points)
        if offset is None:
            return point_ids


def _batches(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]
