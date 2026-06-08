from pathlib import Path

import ranker_engine
from config import Settings
from meta_profiler import DocumentProfile
from ranker_engine import (
    LLMClient,
    ManifestAnalysis,
    SemanticScoring,
    build_output_language_policy,
    infer_primary_language,
)


def test_semantic_score_accepts_structured_summary() -> None:
    score = SemanticScoring._validate_score(
        {
            "quality": 85,
            "category": "Architecture",
            "document_kind": "ArchitectureDecision",
            "topic_tags": ["DistributedSystems"],
            "summary": [
                "本文梳理支付链路的核心瓶颈。",
                "方案通过异步化和缓存隔离降低峰值压力。",
            ],
            "knowledge_density": 80,
            "implementation_specificity": 75,
            "logical_structure": 85,
            "reason": "test",
        }
    )

    assert score.summary == "本文梳理支付链路的核心瓶颈。 方案通过异步化和缓存隔离降低峰值压力。"


def test_llm_client_reuses_http_client(monkeypatch, tmp_path: Path) -> None:
    created_clients: list[object] = []
    posts: list[dict[str, object]] = []

    class FakeResponse:
        def raise_for_status(self) -> None:
            return

        def json(self):
            return {"response": '{"quality": 80}'}

    class FakeHttpClient:
        def __init__(self):
            self.closed = False
            created_clients.append(self)

        def post(self, endpoint, *, headers, json, timeout):
            posts.append(
                {
                    "endpoint": endpoint,
                    "headers": headers,
                    "json": json,
                    "timeout": timeout,
                }
            )
            return FakeResponse()

        def close(self):
            self.closed = True

    monkeypatch.setattr(ranker_engine.httpx, "Client", FakeHttpClient)
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=tmp_path / "source",
        OUTPUT_ROOT=tmp_path / "output",
    )

    with LLMClient(settings=settings) as client:
        client.complete_json("system", "first")
        client.complete_json("system", "second")

    assert len(created_clients) == 1
    assert len(posts) == 2
    assert created_clients[0].closed is True


def test_manifest_analysis_reuses_file_stats(monkeypatch, tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    directory = source_dir / "docs"
    directory.mkdir(parents=True)
    first = directory / "a.md"
    second = directory / "b.md"
    first.write_text("a", encoding="utf-8")
    second.write_text("b", encoding="utf-8")
    target_paths = {first.resolve(), second.resolve()}
    stat_calls = 0
    original_stat = Path.stat

    def counting_stat(path, *args, **kwargs):
        nonlocal stat_calls
        if path in target_paths:
            stat_calls += 1
        return original_stat(path, *args, **kwargs)

    class FakeClient:
        class Settings:
            MANIFEST_MAX_FILES = 20

        settings = Settings()

        def complete_json(self, system_prompt, user_prompt):
            return {"series_files": [], "series_groups": []}

    monkeypatch.setattr(Path, "stat", counting_stat)

    ManifestAnalysis(llm_client=FakeClient()).analyze_directory(
        directory, [first, second], source_dir
    )

    assert stat_calls == 2


def test_output_language_auto_infers_document_body_language() -> None:
    assert infer_primary_language("本文介绍订单链路隔离设计，通过缓存分层降低风险。") == "zh-CN"
    assert infer_primary_language("This document explains RAG evaluation and test strategy.") == "en"

    policy = build_output_language_policy("auto", "本文介绍订单链路隔离设计。")

    assert policy["requested"] == "auto"
    assert policy["resolved_language"] == "zh-CN"


def test_semantic_scoring_prompt_carries_forced_output_language(tmp_path: Path) -> None:
    class FakeClient:
        class Settings:
            OUTPUT_LANGUAGE = "en"

        settings = Settings()

        def complete_json(self, system_prompt, user_prompt):
            self.user_prompt = user_prompt
            return {
                "quality": 80,
                "category": "Design",
                "document_kind": "ArchitectureDecision",
                "summary": "A concise English summary.",
                "reason": "useful",
            }

    document = tmp_path / "doc.md"
    document.write_text("x", encoding="utf-8")
    profile = DocumentProfile(
        file_name="doc.md",
        file_suffix=".md",
        file_size_bytes=1,
        created_at="2026-01-01T00:00:00+00:00",
        modified_at="2026-01-01T00:00:00+00:00",
        ctime_mtime_span_seconds=0,
        header_density=0,
        header_count=0,
        non_empty_lines=1,
        code_to_text_ratio=0,
        code_block_count=0,
    )
    client = FakeClient()

    SemanticScoring(llm_client=client).score_document(
        document,
        "中文正文介绍架构方案。",
        profile,
        manifest=__import__("ranker_engine").ManifestResult(),
        output_language="en",
    )

    assert '"requested": "en"' in client.user_prompt
    assert '"resolved_language": "en"' in client.user_prompt
