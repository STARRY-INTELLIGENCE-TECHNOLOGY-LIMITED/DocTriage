import json
from pathlib import Path

import pytest

import rag_indexer
from config import Settings
from rag_indexer import (
    RagIndexSelection,
    RagRedactionPolicy,
    RagRedactionRule,
    build_rag_index,
    build_parser,
    load_jsonl,
    redaction_policy_from_sources,
    search_rag_index,
)
from rag_vector_store import (
    inspect_qdrant_local_index,
    search_qdrant_local_index,
    sync_qdrant_local_index,
)


def write_decision(output_root: Path, payload: dict) -> None:
    state_dir = output_root / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "decisions.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def test_build_rag_index_writes_documents_chunks_and_manifest(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "agent-rag.md"
    document.write_text(
        "Agent retrieval design\n\nChunking and citations matter for reliable RAG.",
        encoding="utf-8",
    )
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "agent-rag.md",
            "status": "planned",
            "quality": 92,
            "category": "Architecture",
            "summary": "Agent RAG design",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="local-model",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RAG_CHUNK_MAX_CHARS=200,
        RAG_CHUNK_OVERLAP_CHARS=20,
    )

    status = build_rag_index(
        settings,
        selection=RagIndexSelection(min_quality=80),
        embeddings_enabled=False,
    )

    documents = load_jsonl(output_root / "_rag" / "documents.jsonl")
    chunks = load_jsonl(output_root / "_rag" / "chunks.jsonl")
    manifest = json.loads((output_root / "_rag" / "manifest.json").read_text(encoding="utf-8"))

    assert status["progress"]["phase"] == "complete"
    assert manifest["document_count"] == 1
    assert manifest["chunk_count"] >= 1
    assert manifest["embeddings_enabled"] is False
    assert documents[0]["relative_path"] == "agent-rag.md"
    assert chunks[0]["document_id"] == documents[0]["document_id"]
    assert "reliable RAG" in " ".join(chunk["text"] for chunk in chunks)


def test_rag_index_requires_embedding_model_when_embedding_enabled(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "doc.md"
    document.write_text("body", encoding="utf-8")
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "doc.md",
            "status": "planned",
            "quality": 90,
            "category": "Design",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )

    with pytest.raises(ValueError, match="EMBEDDING_MODEL"):
        build_rag_index(settings, embeddings_enabled=True)


def test_rag_embedding_resume_only_generates_missing_vectors(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "chunks.md"
    document.write_text(
        (
            "alpha retrieval paragraph with detailed notes about chunking and recall.\n\n"
            "beta reranking paragraph with enough extra context to force another chunk in the test fixture.\n\n"
            "gamma citation paragraph with additional structured evidence for resume validation."
        ),
        encoding="utf-8",
    )
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "chunks.md",
            "status": "planned",
            "quality": 95,
            "category": "Research",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="local-model",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_MODEL="fake-embed",
        EMBEDDING_ENDPOINT="http://localhost:11434/api/embeddings",
        RAG_CHUNK_MAX_CHARS=200,
        RAG_CHUNK_OVERLAP_CHARS=0,
    )
    build_rag_index(settings, embeddings_enabled=False)
    chunks = load_jsonl(settings.rag_chunks_path)
    assert len(chunks) > 1
    settings.rag_vectors_path.write_text(
        json.dumps(
            {
                "chunk_id": chunks[0]["chunk_id"],
                "document_id": chunks[0]["document_id"],
                "embedding_model": "fake-embed",
                "embedding": [1.0, 0.0],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    prepared = []
    embedded_texts = []

    class FakeEmbeddingClient:
        endpoint = "http://localhost:11434/api/embeddings"

        def __init__(self, settings):
            self.settings = settings

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def embed(self, text: str):
            embedded_texts.append(text)
            return [float(len(text)), 1.0]

    monkeypatch.setattr(rag_indexer, "OllamaEmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(
        rag_indexer,
        "prepare_embedding_model_for_rag_index",
        lambda settings: prepared.append(settings.EMBEDDING_MODEL),
    )

    status = build_rag_index(settings, embeddings_enabled=True)
    vectors = load_jsonl(settings.rag_vectors_path)

    assert prepared == ["fake-embed"]
    assert len(embedded_texts) == len(chunks) - 1
    assert status["progress"]["missing_vectors"] == 0
    assert {vector["chunk_id"] for vector in vectors} == {
        chunk["chunk_id"] for chunk in chunks
    }


def test_rag_embedding_resume_filters_cache_by_model(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "model.md"
    document.write_text("model-specific vector cache should not be reused", encoding="utf-8")
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "model.md",
            "status": "planned",
            "quality": 95,
            "category": "Research",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="local-model",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_MODEL="new-embed",
        EMBEDDING_ENDPOINT="http://localhost:11434/api/embeddings",
    )
    build_rag_index(settings, embeddings_enabled=False)
    chunk = load_jsonl(settings.rag_chunks_path)[0]
    settings.rag_vectors_path.write_text(
        json.dumps(
            {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "embedding_model": "old-embed",
                "embedding": [1.0, 0.0],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    embedded_texts = []

    class FakeEmbeddingClient:
        endpoint = "http://localhost:11434/api/embeddings"

        def __init__(self, settings):
            self.settings = settings

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def embed(self, text: str):
            embedded_texts.append(text)
            return [2.0, 1.0]

    monkeypatch.setattr(rag_indexer, "OllamaEmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(rag_indexer, "prepare_embedding_model_for_rag_index", lambda settings: None)

    status = build_rag_index(settings, embeddings_enabled=True)

    assert len(embedded_texts) == 1
    assert status["progress"]["embedded_chunks"] == 1
    vectors = load_jsonl(settings.rag_vectors_path)
    assert {vector["embedding_model"] for vector in vectors} == {"old-embed", "new-embed"}


def test_rag_search_falls_back_to_lexical_index(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "retrieval.md"
    document.write_text("Hybrid retrieval needs chunk overlap and citations.", encoding="utf-8")
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "retrieval.md",
            "status": "planned",
            "quality": 91,
            "category": "Implementation",
            "summary": "Hybrid retrieval",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    build_rag_index(settings, embeddings_enabled=False)

    payload = search_rag_index(settings, "chunk overlap", top_k=3)

    assert payload["mode"] == "lexical"
    assert payload["results"][0]["relative_path"] == "retrieval.md"
    assert "chunk overlap" in payload["results"][0]["excerpt"].lower()


def test_qdrant_local_sync_search_and_stale_point_cleanup(tmp_path: Path) -> None:
    qdrant_path = tmp_path / "qdrant"
    chunks = [
        {
            "chunk_id": "alpha",
            "document_id": "doc-alpha",
            "relative_path": "alpha.md",
            "text": "alpha evidence",
            "chunk_index": 0,
        },
        {
            "chunk_id": "beta",
            "document_id": "doc-beta",
            "relative_path": "beta.md",
            "text": "beta evidence",
            "chunk_index": 0,
        },
    ]

    first = sync_qdrant_local_index(
        qdrant_path,
        "rag_test",
        chunks,
        {"alpha": [1.0, 0.0], "beta": [0.0, 1.0]},
    )
    search = search_qdrant_local_index(
        qdrant_path,
        "rag_test",
        [1.0, 0.0],
        limit=2,
    )

    assert first["vector_count"] == 2
    assert first["vector_dimension"] == 2
    assert next(iter(search["scores"])) == "alpha"

    second = sync_qdrant_local_index(
        qdrant_path,
        "rag_test",
        chunks[1:],
        {"beta": [0.0, 1.0]},
    )
    inspected = inspect_qdrant_local_index(qdrant_path, "rag_test")

    assert second["vector_count"] == 1
    assert inspected["collection_exists"] is True
    assert inspected["vector_count"] == 1


def test_rag_build_and_search_use_qdrant_local_with_jsonl_fallback(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "office.md"
    document.write_text(
        "Office succession depends on durable trust and documented delivery.",
        encoding="utf-8",
    )
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "office.md",
            "status": "planned",
            "quality": 96,
            "category": "Business",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_MODEL="fake-embed",
        EMBEDDING_ENDPOINT="http://localhost:11434/api/embeddings",
        RAG_VECTOR_STORE_TYPE="qdrant_local",
        RAG_QDRANT_COLLECTION="rag_e2e",
    )

    class FakeEmbeddingClient:
        endpoint = "http://localhost:11434/api/embeddings"

        def __init__(self, settings):
            self.settings = settings

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def embed(self, text: str):
            return [1.0, 0.0] if "office" in text.lower() else [0.0, 1.0]

    monkeypatch.setattr(rag_indexer, "OllamaEmbeddingClient", FakeEmbeddingClient)
    monkeypatch.setattr(
        rag_indexer,
        "prepare_embedding_model_for_rag_index",
        lambda settings: None,
    )

    status = build_rag_index(settings, embeddings_enabled=True)
    result = search_rag_index(settings, "office trust", top_k=3)

    assert status["manifest"]["vector_store"]["store_type"] == "qdrant_local"
    assert status["manifest"]["vector_store"]["vector_count"] == 1
    assert result["mode"] == "vector"
    assert result["vector_store"] == "qdrant_local"
    assert result["results"][0]["relative_path"] == "office.md"

    monkeypatch.setattr(
        rag_indexer,
        "search_qdrant_local_index",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("locked")),
    )
    fallback = search_rag_index(settings, "office trust", top_k=3)

    assert fallback["mode"] == "vector"
    assert fallback["vector_store"] == "local_jsonl"
    assert fallback["results"][0]["relative_path"] == "office.md"
    assert "Qdrant Local search failed" in fallback["warnings"][0]


def test_build_rag_index_applies_redaction_to_chunks_and_manifest(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "sensitive.md"
    document.write_text(
        "Alice works on SecretProject. Contact 13800138000 for rollout.",
        encoding="utf-8",
    )
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "sensitive.md",
            "status": "planned",
            "quality": 93,
            "category": "SecretProject",
            "document_kind": "InternalAliceDoc",
            "topic_tags": ["Alice", "Confidential"],
            "summary": "Alice summary for SecretProject",
            "reason": "Reach 13800138000 for details",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RAG_CHUNK_MAX_CHARS=200,
        RAG_CHUNK_OVERLAP_CHARS=0,
    )

    build_rag_index(
        settings,
        embeddings_enabled=False,
        redaction_policy=RagRedactionPolicy(
            enabled=True,
            placeholder="[MASKED]",
            terms=("Alice", "SecretProject"),
            mappings=(
                RagRedactionRule(
                    pattern=r"\b1[3-9]\d{9}\b",
                    replacement="[PHONE]",
                    regex=True,
                ),
            ),
        ),
    )

    documents = load_jsonl(output_root / "_rag" / "documents.jsonl")
    chunks = load_jsonl(output_root / "_rag" / "chunks.jsonl")
    manifest = json.loads((output_root / "_rag" / "manifest.json").read_text(encoding="utf-8"))

    assert len(documents) == 1
    assert len(chunks) >= 1
    joined_chunks = " ".join(chunk["text"] for chunk in chunks)
    serialized_document = json.dumps(documents[0], ensure_ascii=False)
    assert "Alice" not in joined_chunks
    assert "SecretProject" not in joined_chunks
    assert "13800138000" not in joined_chunks
    assert "[MASKED]" in joined_chunks
    assert "[PHONE]" in joined_chunks
    assert "Alice" not in serialized_document
    assert "SecretProject" not in serialized_document
    assert "13800138000" not in serialized_document
    assert documents[0]["category"] == "[MASKED]"
    assert documents[0]["document_kind"] == "Internal[MASKED]Doc"
    assert documents[0]["topic_tags"][0] == "[MASKED]"
    assert manifest["redaction"]["enabled"] is True
    assert manifest["redaction"]["term_count"] == 2
    assert manifest["redaction"]["mapping_count"] == 1


def test_build_rag_index_can_drop_matched_documents_from_chunks(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    document = source_dir / "blocked.md"
    document.write_text("Top secret rollout plan for BlackProject.", encoding="utf-8")
    write_decision(
        output_root,
        {
            "source_path": str(document),
            "relative_path": "blocked.md",
            "status": "planned",
            "quality": 90,
            "category": "Restricted",
        },
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )

    status = build_rag_index(
        settings,
        embeddings_enabled=False,
        redaction_policy=RagRedactionPolicy(
            enabled=True,
            drop_matched_documents=True,
            terms=("BlackProject",),
        ),
    )

    documents = load_jsonl(output_root / "_rag" / "documents.jsonl")
    chunks = load_jsonl(output_root / "_rag" / "chunks.jsonl")
    manifest = json.loads((output_root / "_rag" / "manifest.json").read_text(encoding="utf-8"))

    assert len(documents) == 1
    assert documents[0]["redaction_blocked"] is True
    assert documents[0]["chunk_count"] == 0
    assert documents[0]["text_chars"] == 0
    assert chunks == []
    assert manifest["chunk_count"] == 0
    assert manifest["failed_documents"] == 1
    assert status["progress"]["failed_documents"] == 1


def test_redaction_policy_from_sources_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("DOCTRIAGE_RAG_REDACT_TERMS", "Alice,SecretProject")
    monkeypatch.setenv("DOCTRIAGE_RAG_REDACT_MAPPINGS", "13800138000=>[PHONE]")
    monkeypatch.setenv("DOCTRIAGE_RAG_REDACT_PLACEHOLDER", "[MASKED]")
    monkeypatch.setenv("DOCTRIAGE_RAG_REDACT_DROP_MATCHED_DOCUMENTS", "1")
    args = build_parser().parse_args(
        [
            "build",
            "--output-root",
            ".",
            "--no-embeddings",
        ]
    )

    policy = redaction_policy_from_sources(args)

    assert policy.active is True
    assert policy.terms == ("Alice", "SecretProject")
    assert policy.mappings[0].pattern == "13800138000"
    assert policy.mappings[0].replacement == "[PHONE]"
    assert policy.placeholder == "[MASKED]"
    assert policy.drop_matched_documents is True
