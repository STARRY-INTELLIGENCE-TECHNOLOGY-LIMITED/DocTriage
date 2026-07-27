from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bundle_exporter import BundleSelection, load_latest_decisions, select_documents
from cleaner import DocumentWashError, DocumentWasher
from config import Settings, get_settings
from ollama_runtime import (
    models_are_same,
    preload_ollama_model_for_settings,
    release_ollama_model_for_settings,
)
from relationship_miner import OllamaEmbeddingClient
from rag_vector_store import (
    normalize_vector_store_type,
    search_qdrant_local_index,
    sync_qdrant_local_index,
)
from runtime_encoding import configure_utf8_runtime

RAG_PROGRESS_VERSION = "doctriage_rag_progress.v1"
RAG_MANIFEST_VERSION = "doctriage_rag_manifest.v1"
RAG_DOCUMENTS_VERSION = "doctriage_rag_documents.v1"
RAG_CHUNKS_VERSION = "doctriage_rag_chunks.v1"
RAG_VECTORS_VERSION = "doctriage_rag_vectors.v1"
TERMINAL_DECISION_STATUSES = {
    "planned",
    "success",
    "success_overwritten_changed_target",
    "skipped_existing_target",
}
WHITESPACE_PATTERN = re.compile(r"[ \t]+")
TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)
DEFAULT_RAG_REDACTION_PLACEHOLDER = "[REDACTED]"
RAG_REDACTION_TERMS_ENV = "DOCTRIAGE_RAG_REDACT_TERMS"
RAG_REDACTION_MAPPINGS_ENV = "DOCTRIAGE_RAG_REDACT_MAPPINGS"
RAG_REDACTION_PLACEHOLDER_ENV = "DOCTRIAGE_RAG_REDACT_PLACEHOLDER"
RAG_REDACTION_DROP_ENV = "DOCTRIAGE_RAG_REDACT_DROP_MATCHED_DOCUMENTS"


@dataclass(slots=True)
class RagIndexSelection:
    min_quality: int = 75
    categories: set[str] = field(default_factory=set)
    limit: int | None = None
    max_sensitivity_risk: int | None = None
    min_public_writing_suitability: int | None = None
    prefer_target_path: bool = False


@dataclass(slots=True)
class RagRedactionRule:
    pattern: str
    replacement: str
    regex: bool = False
    case_sensitive: bool = False


@dataclass(slots=True)
class RagRedactionPolicy:
    enabled: bool = False
    drop_matched_documents: bool = False
    placeholder: str = DEFAULT_RAG_REDACTION_PLACEHOLDER
    terms: tuple[str, ...] = ()
    mappings: tuple[RagRedactionRule, ...] = ()

    @property
    def active(self) -> bool:
        return self.enabled and (bool(self.terms) or bool(self.mappings))


def build_rag_index(
    settings: Settings | None = None,
    *,
    selection: RagIndexSelection | None = None,
    redaction_policy: RagRedactionPolicy | None = None,
    embeddings_enabled: bool | None = None,
    force: bool = False,
) -> dict[str, Any]:
    current_settings = settings or get_settings()
    current_selection = selection or RagIndexSelection(
        min_quality=current_settings.RAG_MIN_QUALITY,
        limit=current_settings.RAG_MAX_DOCUMENTS,
    )
    use_embeddings = (
        bool(str(current_settings.EMBEDDING_MODEL or "").strip())
        if embeddings_enabled is None
        else embeddings_enabled
    )
    if use_embeddings and not str(current_settings.EMBEDDING_MODEL or "").strip():
        raise ValueError("EMBEDDING_MODEL must be configured when RAG embeddings are enabled.")
    vector_store_type = normalize_vector_store_type(
        current_settings.RAG_VECTOR_STORE_TYPE
    )
    if vector_store_type == "qdrant_local" and not use_embeddings:
        raise ValueError(
            "Qdrant Local requires an embedding model. Configure EMBEDDING_MODEL "
            "or select local_jsonl."
        )

    decisions_path = current_settings.state_dir / "decisions.jsonl"
    current_settings.rag_dir.mkdir(parents=True, exist_ok=True)
    write_rag_progress(
        current_settings.rag_progress_path,
        phase="loading_decisions",
        total_documents=0,
        indexed_documents=0,
        failed_documents=0,
        total_chunks=0,
        cached_vectors=0,
        generated_vectors=0,
        embedded_chunks=0,
        missing_vectors=0,
        embeddings_enabled=use_embeddings,
        embedding_model=str(current_settings.EMBEDDING_MODEL or "").strip(),
    )

    try:
        decisions = load_latest_decisions(decisions_path)
        selected_documents = select_documents(
            decisions,
            BundleSelection(
                min_quality=current_selection.min_quality,
                categories=current_selection.categories,
                max_sensitivity_risk=current_selection.max_sensitivity_risk,
                min_public_writing_suitability=current_selection.min_public_writing_suitability,
                limit=current_selection.limit,
                prefer_target_path=current_selection.prefer_target_path,
                include_summaries=True,
            ),
        )
        if force:
            write_jsonl_atomic(current_settings.rag_documents_path, [])
            write_jsonl_atomic(current_settings.rag_chunks_path, [])
            write_jsonl_atomic(current_settings.rag_vectors_path, [])

        documents, chunks, failures = build_documents_and_chunks(
            current_settings,
            selected_documents,
            embeddings_enabled=use_embeddings,
            redaction_policy=redaction_policy or RagRedactionPolicy(),
        )
        write_jsonl_atomic(current_settings.rag_documents_path, documents)
        write_jsonl_atomic(current_settings.rag_chunks_path, chunks)

        current_chunk_ids = {str(chunk["chunk_id"]) for chunk in chunks}
        embedding_model = str(current_settings.EMBEDDING_MODEL or "").strip()
        existing_vectors = load_rag_vectors(
            current_settings.rag_vectors_path,
            embedding_model=embedding_model if use_embeddings else None,
        )
        current_vectors = {
            chunk_id: vector
            for chunk_id, vector in existing_vectors.items()
            if chunk_id in current_chunk_ids
        }
        missing_chunks = [
            chunk for chunk in chunks if str(chunk["chunk_id"]) not in current_vectors
        ]

        write_rag_progress(
            current_settings.rag_progress_path,
            phase="embedding" if use_embeddings and missing_chunks else "chunking",
            total_documents=len(documents),
            indexed_documents=len(documents),
            failed_documents=len(failures),
            total_chunks=len(chunks),
            cached_vectors=len(current_vectors),
            generated_vectors=0,
            embedded_chunks=len(current_vectors),
            missing_vectors=len(missing_chunks) if use_embeddings else 0,
            embeddings_enabled=use_embeddings,
            embedding_model=str(current_settings.EMBEDDING_MODEL or "").strip(),
        )

        generated_vectors = 0
        if use_embeddings and missing_chunks:
            prepare_embedding_model_for_rag_index(current_settings)
            generated_vectors = embed_missing_chunks(
                current_settings,
                missing_chunks,
                existing_vectors=current_vectors,
            )
            current_vectors = {
                chunk_id: vector
                for chunk_id, vector in load_rag_vectors(
                    current_settings.rag_vectors_path,
                    embedding_model=embedding_model,
                ).items()
                if chunk_id in current_chunk_ids
            }

        vector_store_status: dict[str, Any] = {
            "store_type": "local_jsonl",
            "vector_count": len(current_vectors),
        }
        if vector_store_type == "qdrant_local":
            vector_store_status = sync_qdrant_local_index(
                current_settings.rag_qdrant_path,
                current_settings.RAG_QDRANT_COLLECTION,
                chunks,
                current_vectors,
            )

        manifest = build_manifest(
            current_settings,
            current_selection,
            documents,
            chunks,
            failures=failures,
            embeddings_enabled=use_embeddings,
            vector_count=len(current_vectors),
            vector_store_status=vector_store_status,
            redaction_policy=redaction_policy or RagRedactionPolicy(),
        )
        write_json_atomic(current_settings.rag_manifest_path, manifest)
        write_rag_progress(
            current_settings.rag_progress_path,
            phase="complete",
            total_documents=len(documents),
            indexed_documents=len(documents),
            failed_documents=len(failures),
            total_chunks=len(chunks),
            cached_vectors=max(0, len(current_vectors) - generated_vectors),
            generated_vectors=generated_vectors,
            embedded_chunks=len(current_vectors),
            missing_vectors=max(0, len(chunks) - len(current_vectors))
            if use_embeddings
            else 0,
            embeddings_enabled=use_embeddings,
            embedding_model=str(current_settings.EMBEDDING_MODEL or "").strip(),
        )
        return load_rag_status(current_settings)
    except Exception as exc:
        existing = read_json_file(current_settings.rag_progress_path)
        write_rag_progress(
            current_settings.rag_progress_path,
            phase="error",
            total_documents=coerce_int(existing.get("total_documents"), 0),
            indexed_documents=coerce_int(existing.get("indexed_documents"), 0),
            failed_documents=coerce_int(existing.get("failed_documents"), 0),
            total_chunks=coerce_int(existing.get("total_chunks"), 0),
            cached_vectors=coerce_int(existing.get("cached_vectors"), 0),
            generated_vectors=coerce_int(existing.get("generated_vectors"), 0),
            embedded_chunks=coerce_int(existing.get("embedded_chunks"), 0),
            missing_vectors=coerce_int(existing.get("missing_vectors"), 0),
            embeddings_enabled=use_embeddings,
            embedding_model=str(current_settings.EMBEDDING_MODEL or "").strip(),
            error=str(exc),
        )
        raise


def build_documents_and_chunks(
    settings: Settings,
    selected_documents: list[dict[str, Any]],
    *,
    embeddings_enabled: bool,
    redaction_policy: RagRedactionPolicy,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    washer = DocumentWasher(settings)
    documents: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    total_documents = len(selected_documents)

    for index, document in enumerate(selected_documents, start=1):
        record, record_chunks, failure = build_document_record(
            document,
            settings,
            washer,
            redaction_policy=redaction_policy,
        )
        documents.append(record)
        chunks.extend(record_chunks)
        if failure is not None:
            failures.append(failure)
        write_rag_progress(
            settings.rag_progress_path,
            phase="extracting_text",
            total_documents=total_documents,
            indexed_documents=index,
            failed_documents=len(failures),
            total_chunks=len(chunks),
            cached_vectors=0,
            generated_vectors=0,
            embedded_chunks=0,
            missing_vectors=len(chunks) if embeddings_enabled else 0,
            embeddings_enabled=embeddings_enabled,
            embedding_model=str(settings.EMBEDDING_MODEL or "").strip(),
        )
    return documents, chunks, failures


def build_document_record(
    document: dict[str, Any],
    settings: Settings,
    washer: DocumentWasher,
    *,
    redaction_policy: RagRedactionPolicy,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]:
    values = flatten_document_payload(document)
    relative_path = str(values.get("relative_path") or "")
    source_path = str(values.get("source_path") or "")
    preferred_path = str(
        values.get("preferred_path") or values.get("target_path") or source_path
    )
    title = str(values.get("title") or Path(relative_path or source_path).stem)
    document_id = stable_id("doc", relative_path or source_path or title)
    extraction_notes: list[str] = []
    text_source = "document"
    failure_payload: dict[str, Any] | None = None

    text = ""
    try:
        if preferred_path:
            washed = washer.wash(preferred_path)
            text = normalize_text(washed.clean_markdown)
            extraction_notes.extend(washed.notes)
        else:
            raise DocumentWashError("No preferred path available for text extraction.")
    except (DocumentWashError, FileNotFoundError, OSError) as exc:
        text_source = "fallback"
        extraction_notes.append(f"fallback: {exc}")
        text = fallback_document_text(values)
        failure_payload = {
            "document_id": document_id,
            "relative_path": relative_path,
            "source_path": source_path,
            "preferred_path": preferred_path,
            "error": str(exc),
        }

    if not text.strip():
        text_source = "fallback"
        text = fallback_document_text(values)
        if not failure_payload:
            failure_payload = {
                "document_id": document_id,
                "relative_path": relative_path,
                "source_path": source_path,
                "preferred_path": preferred_path,
                "error": "Document text is empty after extraction.",
            }

    redaction_notes: list[str] = []
    redaction_blocked = False
    sanitized_text = text
    if redaction_policy.active:
        sanitized_text, redaction_notes, redaction_blocked = apply_redaction_policy(
            text,
            redaction_policy,
        )
        extraction_notes.extend(redaction_notes)
    if redaction_blocked:
        failure_payload = {
            "document_id": document_id,
            "relative_path": relative_path,
            "source_path": source_path,
            "preferred_path": preferred_path,
            "error": "Document blocked by RAG redaction policy.",
        }
        sanitized_text = ""

    chunk_texts = split_text_into_chunks(
        sanitized_text,
        max_chars=settings.RAG_CHUNK_MAX_CHARS,
        overlap_chars=settings.RAG_CHUNK_OVERLAP_CHARS,
    )
    text_sha = stable_hash(sanitized_text)
    sanitized_title = sanitize_metadata_value(title, redaction_policy)
    sanitized_relative_path = sanitize_metadata_value(relative_path, redaction_policy)
    sanitized_source_path = sanitize_metadata_value(source_path, redaction_policy)
    sanitized_preferred_path = sanitize_metadata_value(preferred_path, redaction_policy)
    sanitized_target_path = sanitize_metadata_value(
        str(values.get("target_path") or ""),
        redaction_policy,
    )
    sanitized_summary = sanitize_metadata_value(
        str(values.get("summary") or ""),
        redaction_policy,
    )
    sanitized_reason = sanitize_metadata_value(
        str(values.get("reason") or ""),
        redaction_policy,
    )
    sanitized_category = sanitize_metadata_value(
        str(values.get("category") or ""),
        redaction_policy,
    )
    sanitized_document_kind = sanitize_metadata_value(
        str(values.get("document_kind") or "Unknown"),
        redaction_policy,
    )
    sanitized_topic_tags = [
        sanitize_metadata_value(str(tag), redaction_policy)
        for tag in list(values.get("topic_tags") or [])
    ]
    record = {
        "schema_version": RAG_DOCUMENTS_VERSION,
        "document_id": document_id,
        "relative_path": sanitized_relative_path,
        "source_path": sanitized_source_path,
        "preferred_path": sanitized_preferred_path,
        "target_path": sanitized_target_path,
        "title": sanitized_title,
        "category": sanitized_category,
        "document_kind": sanitized_document_kind,
        "topic_tags": sanitized_topic_tags,
        "quality": coerce_int(values.get("quality"), 0),
        "sensitivity_risk": coerce_int(values.get("sensitivity_risk"), 0),
        "public_writing_suitability": coerce_int(
            values.get("public_writing_suitability"), 0
        ),
        "summary": sanitized_summary,
        "reason": sanitized_reason,
        "status": str(values.get("status") or ""),
        "text_source": text_source,
        "text_sha256": text_sha,
        "text_chars": len(sanitized_text),
        "chunk_count": len(chunk_texts),
        "extraction_notes": extraction_notes,
        "redaction_enabled": bool(redaction_policy.active),
        "redaction_blocked": redaction_blocked,
    }

    chunk_records: list[dict[str, Any]] = []
    for chunk_index, chunk_text in enumerate(chunk_texts):
        chunk_id = stable_id(
            "chunk",
            "\n".join([document_id, str(chunk_index), stable_hash(chunk_text)]),
        )
        chunk_records.append(
            {
                "schema_version": RAG_CHUNKS_VERSION,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "relative_path": sanitized_relative_path,
                "source_path": sanitized_source_path,
                "preferred_path": sanitized_preferred_path,
                "title": sanitized_title,
                "category": sanitized_category,
                "document_kind": sanitized_document_kind,
                "topic_tags": sanitized_topic_tags,
                "quality": coerce_int(values.get("quality"), 0),
                "summary": sanitized_summary,
                "reason": sanitized_reason,
                "text": chunk_text,
                "text_chars": len(chunk_text),
                "chunk_index": chunk_index,
                "text_sha256": stable_hash(chunk_text),
                "redaction_enabled": bool(redaction_policy.active),
            }
        )
    return record, chunk_records, failure_payload


def embed_missing_chunks(
    settings: Settings,
    chunks: list[dict[str, Any]],
    *,
    existing_vectors: dict[str, list[float]],
) -> int:
    generated = 0
    total_chunks = len(chunks) + len(existing_vectors)
    batch_size = resolve_embedding_batch_size(settings)
    generated_entries: list[dict[str, Any]] = []
    base_progress = read_json_file(settings.rag_progress_path)
    total_documents = coerce_int(base_progress.get("total_documents"), 0)
    indexed_documents = coerce_int(base_progress.get("indexed_documents"), 0)
    failed_documents = coerce_int(base_progress.get("failed_documents"), 0)

    with OllamaEmbeddingClient(settings) as client:
        if client.endpoint.lower().endswith("/api/embed"):
            for batch in chunk_sequence(chunks, batch_size):
                vectors = client.embed_many([str(chunk["text"]) for chunk in batch])
                for chunk, vector in zip(batch, vectors, strict=True):
                    generated_entries.append(build_vector_record(settings, chunk, vector))
                append_vector_records(settings.rag_vectors_path, generated_entries)
                generated += len(generated_entries)
                generated_entries.clear()
                write_rag_progress(
                    settings.rag_progress_path,
                    phase="embedding",
                    total_documents=total_documents,
                    indexed_documents=indexed_documents,
                    failed_documents=failed_documents,
                    total_chunks=total_chunks,
                    cached_vectors=len(existing_vectors),
                    generated_vectors=generated,
                    embedded_chunks=len(existing_vectors) + generated,
                    missing_vectors=max(0, len(chunks) - generated),
                    embeddings_enabled=True,
                    embedding_model=str(settings.EMBEDDING_MODEL or "").strip(),
                )
            return generated

        for chunk in chunks:
            vector = client.embed(str(chunk["text"]))
            generated_entries.append(build_vector_record(settings, chunk, vector))
            append_vector_records(settings.rag_vectors_path, generated_entries)
            generated += len(generated_entries)
            generated_entries.clear()
            write_rag_progress(
                settings.rag_progress_path,
                phase="embedding",
                total_documents=total_documents,
                indexed_documents=indexed_documents,
                failed_documents=failed_documents,
                total_chunks=total_chunks,
                cached_vectors=len(existing_vectors),
                generated_vectors=generated,
                embedded_chunks=len(existing_vectors) + generated,
                missing_vectors=max(0, len(chunks) - generated),
                embeddings_enabled=True,
                embedding_model=str(settings.EMBEDDING_MODEL or "").strip(),
            )
    return generated


def prepare_embedding_model_for_rag_index(settings: Settings) -> None:
    scoring_model = str(settings.LLM_MODEL or "").strip()
    embedding_model = str(settings.EMBEDDING_MODEL or "").strip()
    if not embedding_model:
        return
    if scoring_model and embedding_model and models_are_same(scoring_model, embedding_model):
        return
    release_ollama_model_for_settings(
        settings,
        model=scoring_model,
        model_role="scoring",
        target_role="RAG indexing",
        endpoint_setting=settings.LLM_ENDPOINT,
    )
    preload_ollama_model_for_settings(
        settings,
        model=embedding_model,
        model_role="embedding",
        target_role="RAG indexing",
        endpoint_setting=settings.EMBEDDING_ENDPOINT,
        operation="embed",
    )


def build_vector_record(
    settings: Settings, chunk: dict[str, Any], vector: Sequence[float]
) -> dict[str, Any]:
    return {
        "schema_version": RAG_VECTORS_VERSION,
        "chunk_id": str(chunk["chunk_id"]),
        "document_id": str(chunk["document_id"]),
        "embedding_model": str(settings.EMBEDDING_MODEL or ""),
        "embedding": [float(value) for value in vector],
    }


def load_rag_status(settings: Settings | None = None) -> dict[str, Any]:
    current_settings = settings or get_settings()
    manifest = read_json_file(current_settings.rag_manifest_path)
    progress = read_json_file(current_settings.rag_progress_path)
    if not progress and manifest:
        progress = {
            "schema_version": RAG_PROGRESS_VERSION,
            "phase": "complete",
            "total_documents": coerce_int(manifest.get("document_count"), 0),
            "indexed_documents": coerce_int(manifest.get("document_count"), 0),
            "failed_documents": coerce_int(manifest.get("failed_documents"), 0),
            "total_chunks": coerce_int(manifest.get("chunk_count"), 0),
            "cached_vectors": coerce_int(manifest.get("vector_count"), 0),
            "generated_vectors": 0,
            "embedded_chunks": coerce_int(manifest.get("vector_count"), 0),
            "missing_vectors": max(
                0,
                coerce_int(manifest.get("chunk_count"), 0)
                - coerce_int(manifest.get("vector_count"), 0),
            ),
            "embeddings_enabled": bool(manifest.get("embeddings_enabled")),
            "embedding_model": str(manifest.get("embedding_model") or ""),
            "percent": 100.0,
            "updated_epoch": coerce_float(manifest.get("updated_epoch"), time.time()),
        }
    return {
        "available": current_settings.rag_manifest_path.exists(),
        "documents_exists": current_settings.rag_documents_path.exists(),
        "chunks_exists": current_settings.rag_chunks_path.exists(),
        "vectors_exists": current_settings.rag_vectors_path.exists(),
        "manifest": manifest,
        "progress": progress,
    }


def search_rag_index(
    settings: Settings | None,
    query: str,
    *,
    top_k: int | None = None,
    lexical_only: bool = False,
) -> dict[str, Any]:
    current_settings = settings or get_settings()
    normalized_query = normalize_text(query)
    if not normalized_query:
        raise ValueError("Search query is required.")

    chunks = load_jsonl(current_settings.rag_chunks_path)
    if not chunks:
        return {
            "query": normalized_query,
            "mode": "empty",
            "total_chunks": 0,
            "results": [],
        }

    manifest = read_json_file(current_settings.rag_manifest_path)
    embedding_model = str(
        current_settings.EMBEDDING_MODEL or manifest.get("embedding_model") or ""
    ).strip()
    vector_store_type = normalize_vector_store_type(
        current_settings.RAG_VECTOR_STORE_TYPE
    )
    current_vectors: dict[str, list[float]] = {}
    vector_scores: dict[str, float] = {}
    vector_count = 0
    actual_vector_store = vector_store_type
    warnings: list[str] = []
    query_vector: list[float] | None = None
    used_vector_search = False

    if not lexical_only and embedding_model:
        search_settings = (
            current_settings
            if embedding_model == str(current_settings.EMBEDDING_MODEL or "").strip()
            else current_settings.model_copy(update={"EMBEDDING_MODEL": embedding_model})
        )
        if vector_store_type == "qdrant_local":
            try:
                with OllamaEmbeddingClient(search_settings) as client:
                    query_vector = client.embed(normalized_query)
                qdrant_result = search_qdrant_local_index(
                    current_settings.rag_qdrant_path,
                    current_settings.RAG_QDRANT_COLLECTION,
                    query_vector,
                    limit=max(50, (top_k or current_settings.RAG_MAX_SEARCH_RESULTS) * 8),
                )
                vector_scores = dict(qdrant_result.get("scores") or {})
                vector_count = coerce_int(qdrant_result.get("vector_count"), 0)
                used_vector_search = bool(vector_scores)
            except Exception as exc:
                warnings.append(
                    f"Qdrant Local search failed; used JSONL fallback: {exc}"
                )
                actual_vector_store = "local_jsonl"

        if vector_store_type == "local_jsonl" or actual_vector_store == "local_jsonl":
            vectors = load_rag_vectors(
                current_settings.rag_vectors_path,
                embedding_model=embedding_model or None,
            )
            current_vectors = {
                str(chunk["chunk_id"]): vectors[str(chunk["chunk_id"])]
                for chunk in chunks
                if str(chunk.get("chunk_id") or "") in vectors
            }
            vector_count = len(current_vectors)
            if current_vectors:
                if query_vector is None:
                    with OllamaEmbeddingClient(search_settings) as client:
                        query_vector = client.embed(normalized_query)
                vector_scores = {
                    chunk_id: cosine_similarity(query_vector, vector)
                    for chunk_id, vector in current_vectors.items()
                }
                used_vector_search = True

    results: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        lexical_score = score_lexical_match(normalized_query, chunk)
        vector_score = 0.0
        if used_vector_search and chunk_id in vector_scores:
            vector_score = vector_scores[chunk_id]
        if lexical_score <= 0 and vector_score <= 0:
            continue
        combined = (
            vector_score * 0.8 + lexical_score * 0.2
            if used_vector_search
            else lexical_score
        )
        results.append(
            {
                "chunk_id": chunk_id,
                "document_id": str(chunk.get("document_id") or ""),
                "relative_path": str(chunk.get("relative_path") or ""),
                "source_path": str(chunk.get("source_path") or ""),
                "title": str(chunk.get("title") or ""),
                "category": str(chunk.get("category") or ""),
                "quality": coerce_int(chunk.get("quality"), 0),
                "chunk_index": coerce_int(chunk.get("chunk_index"), 0),
                "score": round(combined, 4),
                "vector_score": round(vector_score, 4),
                "lexical_score": round(lexical_score, 4),
                "excerpt": excerpt_for_query(str(chunk.get("text") or ""), normalized_query),
            }
        )

    results.sort(
        key=lambda item: (
            -coerce_float(item.get("score"), 0.0),
            -coerce_int(item.get("quality"), 0),
            str(item.get("relative_path") or ""),
            coerce_int(item.get("chunk_index"), 0),
        )
    )
    resolved_top_k = max(1, min(top_k or current_settings.RAG_MAX_SEARCH_RESULTS, 100))
    return {
        "query": normalized_query,
        "mode": "vector" if used_vector_search else "lexical",
        "vector_store": actual_vector_store,
        "total_chunks": len(chunks),
        "vector_count": vector_count,
        "warnings": warnings,
        "results": results[:resolved_top_k],
    }


def build_manifest(
    settings: Settings,
    selection: RagIndexSelection,
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    failures: list[dict[str, Any]],
    embeddings_enabled: bool,
    vector_count: int,
    vector_store_status: dict[str, Any] | None = None,
    redaction_policy: RagRedactionPolicy | None = None,
) -> dict[str, Any]:
    active_policy = redaction_policy or RagRedactionPolicy()
    return {
        "schema_version": RAG_MANIFEST_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "updated_epoch": time.time(),
        "source_dir": str(settings.SOURCE_DIR),
        "output_root": str(settings.OUTPUT_ROOT),
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "vector_count": vector_count,
        "failed_documents": len(failures),
        "embeddings_enabled": embeddings_enabled,
        "embedding_model": str(settings.EMBEDDING_MODEL or ""),
        "vector_store": vector_store_status
        or {"store_type": "local_jsonl", "vector_count": vector_count},
        "chunk_max_chars": settings.RAG_CHUNK_MAX_CHARS,
        "chunk_overlap_chars": settings.RAG_CHUNK_OVERLAP_CHARS,
        "selection": {
            "min_quality": selection.min_quality,
            "categories": sorted(selection.categories),
            "limit": selection.limit,
            "max_sensitivity_risk": selection.max_sensitivity_risk,
            "min_public_writing_suitability": selection.min_public_writing_suitability,
            "prefer_target_path": selection.prefer_target_path,
        },
        "redaction": {
            "enabled": bool(active_policy.active),
            "drop_matched_documents": bool(active_policy.drop_matched_documents),
            "placeholder": active_policy.placeholder,
            "term_count": len(active_policy.terms),
            "mapping_count": len(active_policy.mappings),
        },
    }


def write_rag_progress(
    path: Path,
    *,
    phase: str,
    total_documents: int,
    indexed_documents: int,
    failed_documents: int,
    total_chunks: int,
    cached_vectors: int,
    generated_vectors: int,
    embedded_chunks: int,
    missing_vectors: int,
    embeddings_enabled: bool,
    embedding_model: str,
    error: str = "",
) -> None:
    percent = calculate_progress_percent(
        phase=phase,
        total_documents=total_documents,
        indexed_documents=indexed_documents,
        total_chunks=total_chunks,
        embedded_chunks=embedded_chunks,
        embeddings_enabled=embeddings_enabled,
    )
    payload = {
        "schema_version": RAG_PROGRESS_VERSION,
        "phase": phase,
        "total_documents": total_documents,
        "indexed_documents": indexed_documents,
        "failed_documents": failed_documents,
        "total_chunks": total_chunks,
        "cached_vectors": cached_vectors,
        "generated_vectors": generated_vectors,
        "embedded_chunks": embedded_chunks,
        "missing_vectors": max(0, missing_vectors),
        "embeddings_enabled": embeddings_enabled,
        "embedding_model": embedding_model,
        "percent": percent,
        "updated_epoch": time.time(),
        "error": error,
    }
    write_json_atomic(path, payload)


def calculate_progress_percent(
    *,
    phase: str,
    total_documents: int,
    indexed_documents: int,
    total_chunks: int,
    embedded_chunks: int,
    embeddings_enabled: bool,
) -> float:
    if phase == "complete":
        return 100.0
    if phase == "error":
        return 0.0
    if phase in {"loading_decisions"}:
        return 0.0
    if phase in {"extracting_text", "chunking"}:
        if total_documents <= 0:
            return 0.0
        multiplier = 50.0 if embeddings_enabled else 100.0
        return round(indexed_documents / total_documents * multiplier, 2)
    if phase == "embedding":
        if total_chunks <= 0:
            return 50.0
        return round(50.0 + embedded_chunks / total_chunks * 50.0, 2)
    return 0.0


def write_jsonl_atomic(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", errors="ignore") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    temp_path.replace(path)


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def append_vector_records(path: Path, records: Iterable[dict[str, Any]]) -> None:
    records = list(records)
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", errors="ignore") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def load_rag_vectors(
    path: Path, *, embedding_model: str | None = None
) -> dict[str, list[float]]:
    vectors: dict[str, list[float]] = {}
    for record in load_jsonl(path):
        chunk_id = str(record.get("chunk_id") or "")
        record_model = str(record.get("embedding_model") or "").strip()
        if embedding_model is not None and record_model != embedding_model:
            continue
        embedding = record.get("embedding")
        if chunk_id and isinstance(embedding, list):
            vectors[chunk_id] = [float(value) for value in embedding]
    return vectors


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def split_text_into_chunks(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    content = normalize_text(text)
    if not content:
        return []
    max_chars = max(200, max_chars)
    overlap_chars = max(0, min(overlap_chars, max_chars - 1))
    if len(content) <= max_chars:
        return [content]

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", content) if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = paragraph
            if overlap_chars:
                overlap = chunks[-1][-overlap_chars:].strip()
                if overlap:
                    current = f"{overlap}\n\n{current}".strip()
        while len(current) > max_chars:
            chunk = current[:max_chars].strip()
            if chunk:
                chunks.append(chunk)
            current = current[max_chars - overlap_chars :].strip()
    if current:
        chunks.append(current)

    deduped: list[str] = []
    for chunk in chunks:
        normalized = chunk.strip()
        if normalized and (not deduped or deduped[-1] != normalized):
            deduped.append(normalized)
    return deduped


def normalize_text(text: str) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [WHITESPACE_PATTERN.sub(" ", line).strip() for line in value.split("\n")]
    normalized = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", normalized).strip()


def apply_redaction_policy(
    text: str, policy: RagRedactionPolicy
) -> tuple[str, list[str], bool]:
    if not policy.active:
        return text, [], False

    value = str(text or "")
    notes: list[str] = []
    matched = False

    for rule in policy.mappings:
        value, count = apply_redaction_rule(value, rule)
        if count:
            matched = True
            notes.append(f"redacted mapping rule ({count})")

    placeholder = policy.placeholder or DEFAULT_RAG_REDACTION_PLACEHOLDER
    for term in policy.terms:
        rule = RagRedactionRule(
            pattern=term,
            replacement=placeholder,
            regex=False,
            case_sensitive=False,
        )
        value, count = apply_redaction_rule(value, rule)
        if count:
            matched = True
            notes.append(f"redacted sensitive term ({count})")

    if matched and policy.drop_matched_documents:
        return "", notes, True
    return normalize_text(value), notes, False


def apply_redaction_rule(text: str, rule: RagRedactionRule) -> tuple[str, int]:
    if not rule.pattern:
        return text, 0
    flags = 0 if rule.case_sensitive else re.IGNORECASE
    replacement = str(rule.replacement)
    if rule.regex:
        try:
            return re.subn(rule.pattern, replacement, text, flags=flags)
        except re.error:
            return text, 0
    pattern = re.escape(rule.pattern)
    return re.subn(pattern, replacement, text, flags=flags)


def sanitize_metadata_value(value: str, policy: RagRedactionPolicy) -> str:
    if not policy.active:
        return str(value or "")
    sanitized, _notes, blocked = apply_redaction_policy(str(value or ""), policy)
    return "" if blocked else sanitized


def parse_redaction_terms(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    terms: list[str] = []
    for raw_line in str(value).replace(",", "\n").splitlines():
        term = raw_line.strip()
        if term:
            terms.append(term)
    return tuple(dict.fromkeys(terms))


def parse_redaction_mappings(value: str | None) -> tuple[RagRedactionRule, ...]:
    if not value:
        return ()
    rules: list[RagRedactionRule] = []
    for raw_line in str(value).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        regex = False
        case_sensitive = False
        if line.startswith("regex:"):
            regex = True
            line = line[len("regex:") :].strip()
        if line.startswith("case:"):
            case_sensitive = True
            line = line[len("case:") :].strip()
        if "=>" in line:
            pattern, replacement = line.split("=>", 1)
        elif "=" in line:
            pattern, replacement = line.split("=", 1)
        else:
            continue
        pattern = pattern.strip()
        replacement = replacement.strip()
        if pattern:
            rules.append(
                RagRedactionRule(
                    pattern=pattern,
                    replacement=replacement,
                    regex=regex,
                    case_sensitive=case_sensitive,
                )
            )
    return tuple(rules)


def redaction_policy_from_sources(args: argparse.Namespace) -> RagRedactionPolicy:
    terms = str(args.redact_terms or os.environ.get(RAG_REDACTION_TERMS_ENV) or "")
    mappings = str(
        args.redact_mappings or os.environ.get(RAG_REDACTION_MAPPINGS_ENV) or ""
    )
    placeholder = str(
        args.redact_placeholder
        or os.environ.get(RAG_REDACTION_PLACEHOLDER_ENV)
        or DEFAULT_RAG_REDACTION_PLACEHOLDER
    )
    drop_matched_documents = bool(args.redact_drop_matched_documents) or env_flag(
        os.environ.get(RAG_REDACTION_DROP_ENV)
    )
    return RagRedactionPolicy(
        enabled=bool(terms or mappings),
        drop_matched_documents=drop_matched_documents,
        placeholder=placeholder,
        terms=parse_redaction_terms(terms),
        mappings=parse_redaction_mappings(mappings),
    )


def env_flag(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def fallback_document_text(document: dict[str, Any]) -> str:
    parts = [
        f"title: {document.get('title') or Path(str(document.get('relative_path') or document.get('source_path') or '')).stem}",
        f"path: {document.get('relative_path') or document.get('source_path') or ''}",
        f"category: {document.get('category') or ''}",
        f"document_kind: {document.get('document_kind') or ''}",
        f"topic_tags: {', '.join(str(tag) for tag in document.get('topic_tags') or [])}",
        f"summary: {document.get('summary') or ''}",
        f"reason: {document.get('reason') or ''}",
    ]
    return normalize_text("\n".join(part for part in parts if part.strip()))


def flatten_document_payload(document: dict[str, Any]) -> dict[str, Any]:
    paths = document.get("paths") if isinstance(document.get("paths"), dict) else {}
    classification = (
        document.get("classification")
        if isinstance(document.get("classification"), dict)
        else {}
    )
    scores = document.get("scores") if isinstance(document.get("scores"), dict) else {}
    text = document.get("text") if isinstance(document.get("text"), dict) else {}
    return {
        "title": document.get("title") or Path(str(paths.get("relative") or "")).stem,
        "source_path": document.get("source_path") or paths.get("source") or "",
        "target_path": document.get("target_path") or paths.get("target") or "",
        "preferred_path": document.get("preferred_path") or paths.get("preferred") or "",
        "relative_path": document.get("relative_path") or paths.get("relative") or "",
        "category": document.get("category") or classification.get("category") or "",
        "document_kind": document.get("document_kind")
        or classification.get("document_kind")
        or "Unknown",
        "topic_tags": document.get("topic_tags") or classification.get("topic_tags") or [],
        "status": document.get("status") or classification.get("status") or "",
        "quality": coerce_int(document.get("quality", scores.get("quality")), 0),
        "sensitivity_risk": coerce_int(
            document.get("sensitivity_risk", scores.get("sensitivity_risk")), 0
        ),
        "public_writing_suitability": coerce_int(
            document.get(
                "public_writing_suitability",
                scores.get("public_writing_suitability"),
            ),
            0,
        ),
        "summary": document.get("summary") or text.get("summary") or "",
        "reason": document.get("reason") or text.get("reason") or "",
    }


def resolve_embedding_batch_size(settings: Settings) -> int:
    endpoint = settings.EMBEDDING_ENDPOINT.rstrip("/").lower()
    supports_batch = endpoint.endswith("/api/embed") or (
        endpoint.endswith("/embeddings") and "/v1/" in endpoint
    )
    if not supports_batch:
        return 1
    return max(1, min(32, settings.CONCURRENCY_LIMIT * 4))


def score_lexical_match(query: str, chunk: dict[str, Any]) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    title = normalize_text(str(chunk.get("title") or "")).lower()
    path_text = normalize_text(str(chunk.get("relative_path") or "")).lower()
    body = normalize_text(str(chunk.get("text") or "")).lower()
    haystack = f"{title}\n{path_text}\n{body}"
    matched = 0.0
    for token in query_tokens:
        if token in title:
            matched += 2.0
        elif token in path_text:
            matched += 1.2
        elif token in haystack:
            matched += 1.0
    return round(matched / max(len(query_tokens) * 2.0, 1.0), 4)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def excerpt_for_query(text: str, query: str, *, width: int = 220) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""
    lowered = normalized.lower()
    query_tokens = tokenize(query)
    first_index = -1
    for token in query_tokens:
        first_index = lowered.find(token)
        if first_index >= 0:
            break
    if first_index < 0:
        return normalized[:width].strip()
    start = max(0, first_index - width // 3)
    end = min(len(normalized), start + width)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(normalized) else ""
    return f"{prefix}{normalized[start:end].strip()}{suffix}"


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(float(value) * float(value) for value in left))
    right_norm = math.sqrt(sum(float(value) * float(value) for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def stable_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{stable_hash(value)[:16]}"


def chunk_sequence(items: Sequence[dict[str, Any]], size: int) -> list[Sequence[dict[str, Any]]]:
    if size <= 0:
        size = 1
    return [items[index : index + size] for index in range(0, len(items), size)]


def parse_categories(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


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


def infer_source_dir_from_decisions(output_root: Path) -> Path | None:
    decisions_path = output_root / "_state" / "decisions.jsonl"
    if not decisions_path.exists():
        return None
    decisions = load_latest_decisions(decisions_path)
    for decision in decisions:
        source_path = str(decision.get("source_path") or "")
        relative_path = str(decision.get("relative_path") or "")
        if not source_path:
            continue
        path = Path(source_path).expanduser().resolve()
        if relative_path:
            parent = path
            for _ in Path(relative_path).parts:
                parent = parent.parent
            return parent
        return path.parent
    return None


def build_settings_from_args(args: argparse.Namespace) -> Settings:
    source_dir = args.source_dir
    output_root = args.output_root
    if output_root is None:
        current = get_settings()
        output_root = current.OUTPUT_ROOT
    output_root = Path(output_root).expanduser().resolve()
    if source_dir is None:
        source_dir = infer_source_dir_from_decisions(output_root)
    if source_dir is None:
        current = get_settings()
        source_dir = current.SOURCE_DIR
    source_dir = Path(source_dir).expanduser().resolve()

    overrides: dict[str, Any] = {
        "SOURCE_DIR": source_dir,
        "OUTPUT_ROOT": output_root,
        "LLM_ENDPOINT": args.llm_endpoint
        if getattr(args, "llm_endpoint", None) is not None
        else "http://localhost:11434/api/generate",
    }
    optional_map = {
        "llm_model": "LLM_MODEL",
        "llm_api_key": "LLM_API_KEY",
        "embedding_endpoint": "EMBEDDING_ENDPOINT",
        "embedding_model": "EMBEDDING_MODEL",
        "embedding_api_key": "EMBEDDING_API_KEY",
        "concurrency": "CONCURRENCY_LIMIT",
        "chunk_max_chars": "RAG_CHUNK_MAX_CHARS",
        "chunk_overlap_chars": "RAG_CHUNK_OVERLAP_CHARS",
        "rag_min_quality": "RAG_MIN_QUALITY",
        "rag_max_documents": "RAG_MAX_DOCUMENTS",
        "top_k": "RAG_MAX_SEARCH_RESULTS",
        "vector_store": "RAG_VECTOR_STORE_TYPE",
        "qdrant_path": "RAG_QDRANT_PATH",
        "qdrant_collection": "RAG_QDRANT_COLLECTION",
    }
    for argument_name, setting_name in optional_map.items():
        value = getattr(args, argument_name, None)
        if value is not None:
            overrides[setting_name] = value
    return Settings(**overrides)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doctriage-rag",
        description="Build and search a resumable chunk-level RAG index from DocTriage outputs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build or resume the RAG index.")
    add_common_path_arguments(build_parser)
    build_parser.add_argument("--llm-endpoint")
    build_parser.add_argument("--llm-model")
    build_parser.add_argument("--llm-api-key")
    build_parser.add_argument("--embedding-endpoint")
    build_parser.add_argument("--embedding-model")
    build_parser.add_argument("--embedding-api-key")
    build_parser.add_argument("--concurrency", type=int)
    build_parser.add_argument("--min-quality", dest="rag_min_quality", type=int)
    build_parser.add_argument("--categories")
    build_parser.add_argument("--limit", dest="rag_max_documents", type=int)
    build_parser.add_argument("--chunk-max-chars", type=int)
    build_parser.add_argument("--chunk-overlap-chars", type=int)
    build_parser.add_argument("--max-sensitivity-risk", type=int)
    build_parser.add_argument("--min-public-writing-suitability", type=int)
    build_parser.add_argument("--prefer-target-path", action="store_true")
    build_parser.add_argument("--redact-terms")
    build_parser.add_argument("--redact-mappings")
    build_parser.add_argument("--redact-placeholder")
    build_parser.add_argument("--redact-drop-matched-documents", action="store_true")
    build_parser.add_argument("--no-embeddings", action="store_true")
    build_parser.add_argument("--force", action="store_true")

    search_parser = subparsers.add_parser("search", help="Search the built RAG index.")
    add_common_path_arguments(search_parser)
    search_parser.add_argument("--llm-endpoint")
    search_parser.add_argument("--llm-api-key")
    search_parser.add_argument("--embedding-endpoint")
    search_parser.add_argument("--embedding-model")
    search_parser.add_argument("--embedding-api-key")
    search_parser.add_argument("--top-k", type=int)
    search_parser.add_argument("--lexical-only", action="store_true")
    search_parser.add_argument("query")

    status_parser = subparsers.add_parser("status", help="Read the current RAG index status.")
    add_common_path_arguments(status_parser)
    status_parser.add_argument("--llm-endpoint")
    status_parser.add_argument("--llm-api-key")
    return parser


def add_common_path_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--vector-store",
        choices=("local_jsonl", "qdrant_local"),
        default="local_jsonl",
    )
    parser.add_argument("--qdrant-path", type=Path)
    parser.add_argument("--qdrant-collection", default="doctriage_rag")


def main(argv: list[str] | None = None) -> None:
    configure_utf8_runtime()
    args = build_parser().parse_args(argv)
    settings = build_settings_from_args(args)

    if args.command == "build":
        selection = RagIndexSelection(
            min_quality=args.rag_min_quality
            if args.rag_min_quality is not None
            else settings.RAG_MIN_QUALITY,
            categories=parse_categories(args.categories),
            limit=args.rag_max_documents,
            max_sensitivity_risk=args.max_sensitivity_risk,
            min_public_writing_suitability=args.min_public_writing_suitability,
            prefer_target_path=bool(args.prefer_target_path),
        )
        payload = build_rag_index(
            settings,
            selection=selection,
            redaction_policy=redaction_policy_from_sources(args),
            embeddings_enabled=not bool(args.no_embeddings)
            and bool(str(settings.EMBEDDING_MODEL or "").strip()),
            force=bool(args.force),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "search":
        payload = search_rag_index(
            settings,
            args.query,
            top_k=args.top_k,
            lexical_only=bool(args.lexical_only),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    if args.command == "status":
        print(json.dumps(load_rag_status(settings), ensure_ascii=False, indent=2))
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
