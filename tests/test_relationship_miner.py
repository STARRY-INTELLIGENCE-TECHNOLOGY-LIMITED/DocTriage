import json
import threading
import time
from pathlib import Path

import pytest

from config import Settings
import relationship_miner
from relationship_miner import (
    build_candidate_relations,
    collect_candidate_pairs,
    collect_citation_pairs,
    load_or_build_embeddings,
    load_records,
    mine_relationships,
    resolve_embedding_workers,
    resolve_relationship_workers,
    write_clusters,
)
from relationship_strategies.embedding import EmbeddingPairCollector


def test_mine_relationships_without_embeddings(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)

    first = source_dir / "Project Alpha v1 Design.pdf"
    second = source_dir / "Project Alpha v2 Design.pdf"
    third = source_dir / "Unrelated Notes.pdf"
    for path in (first, second, third):
        path.write_text("placeholder", encoding="utf-8")

    decisions = [
        {
            "source_path": str(first),
            "relative_path": first.name,
            "target_path": str(output_root / "HQ" / "Design" / first.name),
            "quality": 85,
            "category": "Design",
            "reason": "design document",
            "summary": "project alpha service design",
        },
        {
            "source_path": str(second),
            "relative_path": second.name,
            "target_path": str(output_root / "HQ" / "Design" / second.name),
            "quality": 88,
            "category": "Design",
            "reason": "updated design document",
            "summary": "project alpha service design update",
        },
        {
            "source_path": str(third),
            "relative_path": third.name,
            "target_path": str(output_root / "HQ" / "Thinking" / third.name),
            "quality": 75,
            "category": "Thinking",
            "reason": "notes",
            "summary": "unrelated reflections",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for item in decisions:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_USE_EMBEDDINGS=False,
        RELATIONSHIP_MIN_SCORE=0.5,
    )

    mine_relationships(settings)

    relations_path = output_root / "_relationships" / "relations.jsonl"
    clusters_path = output_root / "_relationships" / "clusters.json"
    assert relations_path.exists()
    assert clusters_path.exists()
    assert "Project Alpha" in relations_path.read_text(encoding="utf-8")

    clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    assert clusters["clusters"]


def test_mine_relationships_with_embeddings_releases_scoring_model_first(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    file_path = source_dir / "doc.md"
    file_path.write_text("placeholder", encoding="utf-8")
    (state_dir / "decisions.jsonl").write_text(
        json.dumps(
            {
                "source_path": str(file_path),
                "relative_path": file_path.name,
                "quality": 90,
                "category": "Design",
                "summary": "design notes",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    events: list[str] = []

    monkeypatch.setattr(
        relationship_miner,
        "prepare_embedding_model_for_relationships",
        lambda settings: events.append("prepare_embedding"),
    )

    def fake_load_or_build_embeddings(records, settings):
        events.append("embeddings")
        return {}

    monkeypatch.setattr(
        relationship_miner,
        "load_or_build_embeddings",
        fake_load_or_build_embeddings,
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_USE_EMBEDDINGS=True,
        EMBEDDING_MODEL="nomic-embed-text",
    )

    mine_relationships(settings)

    assert events == ["prepare_embedding", "embeddings"]


def test_mine_relationships_requires_embedding_model_when_embeddings_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    (state_dir / "decisions.jsonl").write_text("", encoding="utf-8")
    prepared = {"value": False}

    monkeypatch.setattr(
        relationship_miner,
        "prepare_embedding_model_for_relationships",
        lambda settings: prepared.update(value=True),
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_USE_EMBEDDINGS=True,
    )

    with pytest.raises(ValueError, match="EMBEDDING_MODEL must be configured"):
        mine_relationships(settings)

    assert prepared["value"] is False


def test_embedding_generation_uses_configured_concurrency(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    records = []
    for index in range(4):
        path = source_dir / f"doc{index}.md"
        path.write_text("placeholder", encoding="utf-8")
        record = relationship_miner.RelationshipRecord(
            source_path=path,
            relative_path=path.name,
            target_path="",
            quality=90,
            category="Design",
            document_kind="Unknown",
            topic_tags=[],
            reason="",
            summary=f"summary {index}",
            modified_epoch=float(index),
            normalized_name=relationship_miner.normalize_name(path.stem),
        )
        record.embedding_text = relationship_miner.build_embedding_text(
            record,
            Settings(
                LLM_ENDPOINT="http://localhost:11434/api/generate",
                LLM_MODEL="gemma4:e4b",
                SOURCE_DIR=source_dir,
                OUTPUT_ROOT=output_root,
            ),
        )
        records.append(record)

    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_embed_records_chunk(settings, work_items):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return [
            (index, cache_key, [float(len(record.embedding_text))])
            for index, record, cache_key in work_items
        ]

    monkeypatch.setattr(
        relationship_miner,
        "embed_records_chunk",
        fake_embed_records_chunk,
    )
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        CONCURRENCY_LIMIT=3,
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_CACHE_ENABLED=False,
    )

    embeddings = load_or_build_embeddings(records, settings)

    assert sorted(embeddings) == [0, 1, 2, 3]
    assert max_active == 3
    assert resolve_embedding_workers(settings, 4) == 3


def test_embedding_progress_and_cache_resume_are_relationship_scoped(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    records = []
    for index in range(3):
        path = source_dir / f"doc{index}.md"
        path.write_text("placeholder", encoding="utf-8")
        record = relationship_miner.RelationshipRecord(
            source_path=path,
            relative_path=path.name,
            target_path="",
            quality=90,
            category="Design",
            document_kind="Unknown",
            topic_tags=[],
            reason="",
            summary=f"summary {index}",
            modified_epoch=float(index),
            normalized_name=relationship_miner.normalize_name(path.stem),
        )
        record.embedding_text = f"embedding text {index}"
        records.append(record)

    class FakeEmbeddingClient:
        def __init__(self, settings):
            self.endpoint = "http://localhost:11434/api/embeddings"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return

        def embed(self, text):
            return [float(text.rsplit(" ", 1)[-1])]

    monkeypatch.setattr(relationship_miner, "OllamaEmbeddingClient", FakeEmbeddingClient)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        CONCURRENCY_LIMIT=1,
        RELATIONSHIP_USE_EMBEDDINGS=True,
        EMBEDDING_MODEL="nomic-embed-text",
    )
    cache_path = settings.embedding_cache_path
    progress_path = settings.embedding_progress_path
    cache_path.parent.mkdir(parents=True)
    legacy_cache_path = output_root / "_state" / "embedding_cache.jsonl"
    relationship_miner.append_embedding_cache(
        legacy_cache_path,
        relationship_miner.embedding_cache_key(records[0]),
        [10.0],
    )

    embeddings = load_or_build_embeddings(records, settings)

    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert cache_path == output_root / "_relationships" / "embedding_cache.jsonl"
    assert progress_path == output_root / "_relationships" / "embedding_progress.json"
    assert embeddings == {0: [10.0], 1: [1.0], 2: [2.0]}
    assert progress["phase"] == "complete"
    assert progress["total"] == 3
    assert progress["cached"] == 1
    assert progress["generated"] == 2
    assert progress["missing"] == 0
    assert progress["percent"] == 100.0
    new_cache_text = cache_path.read_text(encoding="utf-8")
    assert "embedding text 1" not in new_cache_text
    assert len(new_cache_text.strip().splitlines()) == 2
    assert legacy_cache_path.exists()


def test_embedding_client_reuses_http_client(monkeypatch, tmp_path: Path) -> None:
    created_clients: list[object] = []
    posts: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return

        def json(self):
            return {"embedding": [1, 2, 3]}

    class FakeHttpClient:
        def __init__(self):
            self.closed = False
            created_clients.append(self)

        def post(self, endpoint, *, json, timeout):
            posts.append({"endpoint": endpoint, "json": json, "timeout": timeout})
            return FakeResponse()

        def close(self):
            self.closed = True

    monkeypatch.setattr(relationship_miner.httpx, "Client", FakeHttpClient)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
        EMBEDDING_MODEL="nomic-embed-text",
    )

    with relationship_miner.OllamaEmbeddingClient(settings) as client:
        assert client.embed("first") == [1.0, 2.0, 3.0]
        assert client.embed("second") == [1.0, 2.0, 3.0]

    assert len(created_clients) == 1
    assert len(posts) == 2
    assert created_clients[0].closed is True


def test_embedding_client_requires_explicit_embedding_model(tmp_path: Path) -> None:
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
    )

    with pytest.raises(ValueError, match="EMBEDDING_MODEL must be configured"):
        relationship_miner.OllamaEmbeddingClient(settings)


def test_api_embed_batches_inputs_per_worker(monkeypatch, tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    records = []
    for index in range(4):
        path = source_dir / f"doc{index}.md"
        path.write_text("placeholder", encoding="utf-8")
        record = relationship_miner.RelationshipRecord(
            source_path=path,
            relative_path=path.name,
            target_path="",
            quality=90,
            category="Design",
            document_kind="Unknown",
            topic_tags=[],
            reason="",
            summary=f"summary {index}",
            modified_epoch=float(index),
            normalized_name=relationship_miner.normalize_name(path.stem),
        )
        record.embedding_text = f"embedding text {index}"
        records.append(record)

    posts: list[dict[str, object]] = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return

        def json(self):
            inputs = self.payload["input"]
            assert isinstance(inputs, list)
            return {"embeddings": [[float(len(text))] for text in inputs]}

    class FakeHttpClient:
        def post(self, endpoint, *, json, timeout):
            posts.append({"endpoint": endpoint, "json": json, "timeout": timeout})
            return FakeResponse(json)

        def close(self):
            return

    monkeypatch.setattr(relationship_miner.httpx, "Client", FakeHttpClient)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_ENDPOINT="http://localhost:11434/api/embed",
        EMBEDDING_MODEL="nomic-embed-text",
        CONCURRENCY_LIMIT=2,
        EMBEDDING_CACHE_ENABLED=False,
    )

    embeddings = load_or_build_embeddings(records, settings)

    assert sorted(embeddings) == [0, 1, 2, 3]
    assert len(posts) == 2
    assert sorted(len(post["json"]["input"]) for post in posts) == [2, 2]


def test_api_embed_batches_inputs_with_single_worker(monkeypatch, tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    records = []
    for index in range(3):
        path = source_dir / f"doc{index}.md"
        path.write_text("placeholder", encoding="utf-8")
        record = relationship_miner.RelationshipRecord(
            source_path=path,
            relative_path=path.name,
            target_path="",
            quality=90,
            category="Design",
            document_kind="Unknown",
            topic_tags=[],
            reason="",
            summary=f"summary {index}",
            modified_epoch=float(index),
            normalized_name=relationship_miner.normalize_name(path.stem),
        )
        record.embedding_text = f"embedding text {index}"
        records.append(record)

    posts: list[dict[str, object]] = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self) -> None:
            return

        def json(self):
            inputs = self.payload["input"]
            assert isinstance(inputs, list)
            return {"embeddings": [[float(len(text))] for text in inputs]}

    class FakeHttpClient:
        def post(self, endpoint, *, json, timeout):
            posts.append({"endpoint": endpoint, "json": json, "timeout": timeout})
            return FakeResponse(json)

        def close(self):
            return

    monkeypatch.setattr(relationship_miner.httpx, "Client", FakeHttpClient)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_ENDPOINT="http://localhost:11434/api/embed",
        EMBEDDING_MODEL="nomic-embed-text",
        CONCURRENCY_LIMIT=1,
        EMBEDDING_CACHE_ENABLED=False,
    )

    embeddings = load_or_build_embeddings(records, settings)

    assert sorted(embeddings) == [0, 1, 2]
    assert len(posts) == 1
    assert len(posts[0]["json"]["input"]) == 3


def test_embedding_cache_disabled_skips_cache_read(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    path = source_dir / "doc.md"
    path.write_text("placeholder", encoding="utf-8")
    record = relationship_miner.RelationshipRecord(
        source_path=path,
        relative_path=path.name,
        target_path="",
        quality=90,
        category="Design",
        document_kind="Unknown",
        topic_tags=[],
        reason="",
        summary="summary",
        normalized_name=relationship_miner.normalize_name(path.stem),
    )
    record.embedding_text = "fresh embedding text"

    def fail_cache_read(path):
        raise AssertionError("cache should not be read when disabled")

    class FakeEmbeddingClient:
        def __init__(self, settings):
            self.endpoint = "http://localhost:11434/api/embeddings"
            return

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return

        def embed(self, text):
            return [float(len(text))]

    monkeypatch.setattr(relationship_miner, "load_embedding_cache", fail_cache_read)
    monkeypatch.setattr(relationship_miner, "OllamaEmbeddingClient", FakeEmbeddingClient)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_CACHE_ENABLED=False,
    )

    embeddings = load_or_build_embeddings([record], settings)

    assert embeddings == {0: [20.0]}


def test_embedding_pair_collector_keeps_only_top_k_neighbors(tmp_path: Path) -> None:
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
        RELATIONSHIP_EMBEDDING_TOP_K=1,
    )
    embeddings = {
        0: [1.0, 0.0],
        1: [0.9, 0.1],
        2: [0.0, 1.0],
        3: [0.1, 0.9],
    }

    pairs = EmbeddingPairCollector().collect([], embeddings, settings)

    assert pairs == {(0, 1), (2, 3)}


def test_clusters_ignore_weak_time_path_chain_edges(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    files = []
    for name in ("2026-01.md", "2026-02.md", "2026-03.md"):
        path = source_dir / name
        path.write_text(name, encoding="utf-8")
        files.append(path)
    records = [
        relationship_miner.RelationshipRecord(
            source_path=path,
            relative_path=path.name,
            target_path="",
            quality=65,
            category="Thinking",
            document_kind="MeetingNotes",
            topic_tags=[],
            reason="",
            summary="",
            normalized_name=relationship_miner.normalize_name(path.stem),
        )
        for path in files
    ]
    weak = [
        relationship_miner.CandidateRelation(
            left=0,
            right=1,
            relation_score=0.86,
            filename_similarity=0.5,
            time_proximity=1.0,
            path_proximity=1.0,
            type_compatibility=1.0,
            signals=["time", "path", "category"],
        ),
        relationship_miner.CandidateRelation(
            left=1,
            right=2,
            relation_score=0.86,
            filename_similarity=0.5,
            time_proximity=1.0,
            path_proximity=1.0,
            type_compatibility=1.0,
            signals=["time", "path", "category"],
        ),
    ]
    clusters_path = output_root / "_relationships" / "clusters.json"

    write_clusters(weak, records, clusters_path, cluster_min_score=0.88)

    clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    assert clusters["cluster_min_score"] == 0.88
    assert clusters["clusters"] == []

    strong = [
        relationship_miner.CandidateRelation(
            left=0,
            right=1,
            relation_score=0.9,
            filename_similarity=0.92,
            time_proximity=1.0,
            path_proximity=1.0,
            type_compatibility=1.0,
            signals=["filename", "time", "path", "category"],
        )
    ]
    write_clusters(strong, records, clusters_path, cluster_min_score=0.88)
    clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    assert clusters["clusters"][0]["size"] == 2


def test_clusters_ignore_cross_directory_periodic_reports(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    records = [
        relationship_miner.RelationshipRecord(
            source_path=source_dir / "a.md",
            relative_path="alice/2025-01 月报.md",
            target_path="",
            quality=65,
            category="Business",
            document_kind="MeetingNotes",
            topic_tags=[],
            reason="",
            summary="",
            normalized_name=relationship_miner.normalize_name("2025-01 月报"),
        ),
        relationship_miner.RelationshipRecord(
            source_path=source_dir / "b.md",
            relative_path="bob/2025-01 月报.md",
            target_path="",
            quality=65,
            category="Business",
            document_kind="MeetingNotes",
            topic_tags=[],
            reason="",
            summary="",
            normalized_name=relationship_miner.normalize_name("2025-01 月报"),
        ),
    ]
    candidate = relationship_miner.CandidateRelation(
        left=0,
        right=1,
        relation_score=0.95,
        filename_similarity=1.0,
        time_proximity=1.0,
        path_proximity=0.0,
        type_compatibility=1.0,
        citation_count=1,
        signals=["filename", "time", "category", "citation", "version_or_sequence"],
    )
    clusters_path = output_root / "_relationships" / "clusters.json"

    write_clusters([candidate], records, clusters_path, cluster_min_score=0.88)

    clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    assert clusters["clusters"] == []


def test_relationship_records_use_latest_decision(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    file_path = source_dir / "doc.md"
    file_path.write_text("placeholder", encoding="utf-8")

    decisions_path = state_dir / "decisions.jsonl"
    with decisions_path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "source_path": str(file_path),
                    "relative_path": file_path.name,
                    "target_path": "old",
                    "quality": 30,
                    "category": "LowQuality",
                },
                ensure_ascii=False,
            )
            + "\n"
        )
        handle.write(
            json.dumps(
                {
                    "source_path": str(file_path),
                    "relative_path": file_path.name,
                    "target_path": "new",
                    "quality": 90,
                    "category": "Design",
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    records = load_records(decisions_path, settings)

    assert len(records) == 1
    assert records[0].quality == 90
    assert records[0].category == "Design"


def test_text_citation_signal_links_explicit_title_mentions(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    design = source_dir / "Payment Architecture.md"
    review = source_dir / "Engineering Review.md"
    design.write_text("# Payment Architecture\n\nDesign body", encoding="utf-8")
    review.write_text(
        "This review follows Payment Architecture and captures lessons.",
        encoding="utf-8",
    )

    decisions = [
        {
            "source_path": str(design),
            "relative_path": design.name,
            "target_path": "",
            "quality": 90,
            "category": "Architecture",
            "summary": "payment design",
        },
        {
            "source_path": str(review),
            "relative_path": review.name,
            "target_path": "",
            "quality": 88,
            "category": "Thinking",
            "summary": "mentions Payment Architecture",
        },
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for item in decisions:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_USE_TEXT_CITATIONS=True,
        RELATIONSHIP_MIN_SCORE=0.05,
    )
    records = load_records(state_dir / "decisions.jsonl", settings)
    citation_pairs = collect_citation_pairs(records)

    assert citation_pairs == {(0, 1): 1}

    mine_relationships(settings)
    relation_line = (output_root / "_relationships" / "relations.jsonl").read_text(
        encoding="utf-8"
    )

    assert '"citation"' in relation_line
    assert '"citation_count": 1' in relation_line


def test_candidate_pairs_are_collected_by_registered_strategies(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    first = source_dir / "Alpha Plan v1.md"
    second = source_dir / "Alpha Plan v2.md"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for path in (first, second):
            handle.write(
                json.dumps(
                    {
                        "source_path": str(path),
                        "relative_path": path.name,
                        "quality": 90,
                        "category": "Design",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    records = load_records(state_dir / "decisions.jsonl", settings)

    assert collect_candidate_pairs(records, {}, settings) == {(0, 1)}


def test_parallel_relationship_scoring_path_matches_serial(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)

    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(16):
            path = source_dir / f"Alpha Plan v{index}.md"
            path.write_text(f"alpha {index}", encoding="utf-8")
            handle.write(
                json.dumps(
                    {
                        "source_path": str(path),
                        "relative_path": path.name,
                        "quality": 90,
                        "category": "Design",
                        "summary": "alpha plan",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    base_settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_MIN_SCORE=0.0,
        RELATIONSHIP_MAX_CANDIDATES_PER_FILE=16,
    )
    records = load_records(state_dir / "decisions.jsonl", base_settings)
    serial = build_candidate_relations(
        records, {}, base_settings.model_copy(update={"RELATIONSHIP_WORKERS": 1})
    )
    monkeypatch.setattr(relationship_miner, "MIN_PARALLEL_RELATION_RECORDS", 1)
    monkeypatch.setattr(relationship_miner, "MIN_PARALLEL_RELATION_PAIRS", 1)
    called = {"workers": 0}

    def fake_parallel(sorted_pairs, records, embeddings, settings, citation_pairs, worker_count):
        called["workers"] = worker_count
        return relationship_miner.score_candidate_pairs_chunk(
            sorted_pairs, records, embeddings, settings, citation_pairs
        )

    monkeypatch.setattr(
        relationship_miner, "score_candidate_pairs_parallel", fake_parallel
    )
    parallel = build_candidate_relations(
        records, {}, base_settings.model_copy(update={"RELATIONSHIP_WORKERS": 2})
    )

    assert called["workers"] == 2
    assert parallel == serial


def test_relationship_workers_are_inferred_from_cpu_count(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(relationship_miner.os, "cpu_count", lambda: 12)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
    )

    assert resolve_relationship_workers(settings, 1000) == 8


def test_relationship_workers_keep_small_runs_serial(tmp_path: Path) -> None:
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
    )

    assert resolve_relationship_workers(settings, 999) == 1


def test_relationship_cli_concurrency_sets_embedding_worker_limit(
    tmp_path: Path,
) -> None:
    args = relationship_miner.build_parser().parse_args(
        [
            "--source-dir",
            str(tmp_path / "source"),
            "--output-root",
            str(tmp_path / "output"),
            "--llm-endpoint",
            "http://localhost:11434/api/generate",
            "--llm-model",
            "gemma4:e4b",
            "--concurrency",
            "4",
            "--use-embeddings",
            "--embedding-model",
            "nomic-embed-text",
        ]
    )

    settings = relationship_miner.build_settings_from_args(args)

    assert settings.CONCURRENCY_LIMIT == 4
    assert settings.RELATIONSHIP_USE_EMBEDDINGS is True
    assert settings.EMBEDDING_MODEL == "nomic-embed-text"


def test_relationship_cli_requires_embedding_model_for_embeddings(
    tmp_path: Path,
) -> None:
    args = relationship_miner.build_parser().parse_args(
        [
            "--source-dir",
            str(tmp_path / "source"),
            "--output-root",
            str(tmp_path / "output"),
            "--llm-endpoint",
            "http://localhost:11434/api/generate",
            "--llm-model",
            "gemma4:e4b",
            "--use-embeddings",
        ]
    )

    with pytest.raises(ValueError, match="--embedding-model is required"):
        relationship_miner.build_settings_from_args(args)
