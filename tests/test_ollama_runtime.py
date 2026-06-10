from pathlib import Path
from urllib.error import URLError

from config import Settings
import ollama_runtime


def test_resolve_ollama_runtime_endpoint_uses_api_root() -> None:
    endpoint = ollama_runtime.resolve_ollama_runtime_endpoint(
        "http://localhost:11434/api/chat"
    )

    assert endpoint is not None
    assert endpoint.generate_url == "http://localhost:11434/api/generate"
    assert endpoint.embed_url == "http://localhost:11434/api/embed"
    assert endpoint.ps_url == "http://localhost:11434/api/ps"


def test_wait_for_ollama_model_release_ignores_other_running_models(monkeypatch) -> None:
    calls = {"value": 0}

    def fake_fetch(ps_url: str):
        calls["value"] += 1
        return [{"name": "nomic-embed-text:latest"}]

    monkeypatch.setattr(ollama_runtime, "fetch_ollama_running_models", fake_fetch)

    assert (
        ollama_runtime.wait_for_ollama_model_release(
            "http://localhost:11434/api/ps",
            "gemma4:e4b",
            timeout_seconds=30,
            poll_seconds=1,
        )
        is True
    )
    assert calls["value"] == 1


def test_wait_for_ollama_model_release_is_bounded(monkeypatch) -> None:
    sleeps: list[float] = []
    now = {"value": 0.0}

    monkeypatch.setattr(
        ollama_runtime,
        "fetch_ollama_running_models",
        lambda ps_url: [{"name": "gemma4:e4b"}],
    )
    monkeypatch.setattr(ollama_runtime.time, "monotonic", lambda: now["value"])

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now["value"] += seconds

    monkeypatch.setattr(ollama_runtime.time, "sleep", fake_sleep)

    assert (
        ollama_runtime.wait_for_ollama_model_release(
            "http://localhost:11434/api/ps",
            "gemma4:e4b",
            timeout_seconds=2.5,
            poll_seconds=1,
        )
        is False
    )
    assert sleeps == [1, 1, 0.5]


def test_release_scoring_model_continues_when_unload_request_fails(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        RELATIONSHIP_USE_EMBEDDINGS=True,
        EMBEDDING_MODEL="nomic-embed-text",
    )
    waited = {"value": False}

    def fake_unload(generate_url: str, model: str, *, timeout_seconds: float) -> None:
        raise URLError("offline")

    monkeypatch.setattr(ollama_runtime, "request_ollama_model_unload", fake_unload)
    monkeypatch.setattr(
        ollama_runtime,
        "wait_for_ollama_model_release",
        lambda *args, **kwargs: waited.update(value=True),
    )

    ollama_runtime.release_scoring_model_before_embedding_relationships(settings)

    assert waited["value"] is False


def test_prepare_embedding_model_skips_without_embedding_model(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
    )
    events: list[str] = []

    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_unload",
        lambda *args, **kwargs: events.append("unload"),
    )
    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_embedding_model_preload",
        lambda *args, **kwargs: events.append("embed_preload"),
    )

    ollama_runtime.prepare_embedding_model_for_relationships(settings)

    assert events == []


def test_prepare_embedding_model_switches_from_scoring_to_embedding(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    events: list[tuple[str, str, str]] = []
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_ENDPOINT="http://localhost:11434/api/embeddings",
        EMBEDDING_MODEL="nomic-embed-text",
    )

    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_unload",
        lambda url, model, *, timeout_seconds: events.append(("unload", url, model)),
    )
    monkeypatch.setattr(
        ollama_runtime,
        "wait_for_ollama_model_release",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_embedding_model_preload",
        lambda url, model, *, timeout_seconds: events.append(("embed_preload", url, model)),
    )

    ollama_runtime.prepare_embedding_model_for_relationships(settings)

    assert events == [
        ("unload", "http://localhost:11434/api/generate", "gemma4:e4b"),
        ("embed_preload", "http://localhost:11434/api/embeddings", "nomic-embed-text"),
    ]


def test_prepare_scoring_model_switches_from_embedding_to_scoring(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    events: list[tuple[str, str, str]] = []
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_ENDPOINT="http://localhost:11434/api/embeddings",
        EMBEDDING_MODEL="nomic-embed-text",
    )

    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_unload",
        lambda url, model, *, timeout_seconds: events.append(("unload", url, model)),
    )
    monkeypatch.setattr(
        ollama_runtime,
        "wait_for_ollama_model_release",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_preload",
        lambda url, model, *, timeout_seconds: events.append(("generate_preload", url, model)),
    )

    ollama_runtime.prepare_scoring_model_for_analysis(settings)

    assert events == [
        ("unload", "http://localhost:11434/api/generate", "nomic-embed-text"),
        ("generate_preload", "http://localhost:11434/api/generate", "gemma4:e4b"),
    ]


def test_prepare_scoring_model_skips_without_embedding_model(
    tmp_path: Path, monkeypatch
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    events: list[str] = []
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_MODEL=None,
    )

    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_unload",
        lambda *args, **kwargs: events.append("unload"),
    )
    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_preload",
        lambda *args, **kwargs: events.append("preload"),
    )

    ollama_runtime.prepare_scoring_model_for_analysis(settings)

    assert events == []


def test_model_switch_skips_when_models_match(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    source_dir.mkdir()
    events: list[str] = []
    settings = Settings(
        LLM_ENDPOINT="http://localhost:11434/api/generate",
        LLM_MODEL="gemma4:e4b",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_MODEL="gemma4:e4b",
    )

    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_unload",
        lambda *args, **kwargs: events.append("unload"),
    )
    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_model_preload",
        lambda *args, **kwargs: events.append("preload"),
    )
    monkeypatch.setattr(
        ollama_runtime,
        "request_ollama_embedding_model_preload",
        lambda *args, **kwargs: events.append("embed_preload"),
    )

    ollama_runtime.prepare_embedding_model_for_relationships(settings)
    ollama_runtime.prepare_scoring_model_for_analysis(settings)

    assert events == []
