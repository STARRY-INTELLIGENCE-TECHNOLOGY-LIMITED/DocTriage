from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

from config import Settings

LOGGER = logging.getLogger("doctriage")


@dataclass(frozen=True, slots=True)
class OllamaRuntimeEndpoint:
    base_url: str
    generate_url: str
    embed_url: str
    ps_url: str


def prepare_embedding_model_for_relationships(settings: Settings) -> None:
    source_model = str(settings.LLM_MODEL or "").strip()
    embedding_model = str(settings.EMBEDDING_MODEL or "").strip()
    if not embedding_model:
        LOGGER.info(
            "Skipping model switch before embedding relationships: embedding model is not configured"
        )
        return
    if source_model and embedding_model and models_are_same(source_model, embedding_model):
        LOGGER.info(
            "Skipping model switch before embedding relationships: scoring and embedding model are both %s",
            embedding_model,
        )
        return
    release_ollama_model_for_settings(
        settings,
        model=source_model,
        model_role="scoring",
        target_role="embedding relationship mining",
        endpoint_setting=settings.LLM_ENDPOINT,
    )
    preload_ollama_model_for_settings(
        settings,
        model=embedding_model,
        model_role="embedding",
        target_role="embedding relationship mining",
        endpoint_setting=settings.EMBEDDING_ENDPOINT,
        operation="embed",
    )


def prepare_scoring_model_for_analysis(settings: Settings) -> None:
    embedding_model = str(settings.EMBEDDING_MODEL or "").strip()
    scoring_model = str(settings.LLM_MODEL or "").strip()
    if not embedding_model:
        LOGGER.info(
            "Skipping model switch before analysis: embedding model is not configured"
        )
        return
    if embedding_model and scoring_model and models_are_same(embedding_model, scoring_model):
        LOGGER.info(
            "Skipping model switch before analysis: embedding and scoring model are both %s",
            scoring_model,
        )
        return
    release_ollama_model_for_settings(
        settings,
        model=embedding_model,
        model_role="embedding",
        target_role="document analysis",
        endpoint_setting=settings.EMBEDDING_ENDPOINT,
    )
    preload_ollama_model_for_settings(
        settings,
        model=scoring_model,
        model_role="scoring",
        target_role="document analysis",
        endpoint_setting=settings.LLM_ENDPOINT,
        operation="generate",
    )


def release_scoring_model_before_embedding_relationships(settings: Settings) -> None:
    prepare_embedding_model_for_relationships(settings)


def release_ollama_model_for_settings(
    settings: Settings,
    *,
    model: str,
    model_role: str,
    target_role: str,
    endpoint_setting: str,
) -> None:
    if not model:
        LOGGER.info(
            "Skipping %s model release before %s: model is not configured",
            model_role,
            target_role,
        )
        return

    endpoint = resolve_ollama_runtime_endpoint(endpoint_setting)
    if endpoint is None:
        LOGGER.info(
            "Skipping %s model release before %s: endpoint is not an Ollama /api endpoint",
            model_role,
            target_role,
        )
        return

    LOGGER.info(
        "Requesting %s model unload before %s: %s",
        model_role,
        target_role,
        model,
    )
    try:
        request_ollama_model_unload(
            endpoint.generate_url,
            model,
            timeout_seconds=min(max(float(settings.LLM_TIMEOUT_SECONDS), 5.0), 30.0),
        )
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        LOGGER.warning(
            "Could not request %s model unload before %s: %s",
            model_role,
            target_role,
            exc,
        )
        return

    if settings.RELATIONSHIP_EMBEDDING_LLM_UNLOAD_TIMEOUT_SECONDS <= 0:
        return

    try:
        released = wait_for_ollama_model_release(
            endpoint.ps_url,
            model,
            timeout_seconds=settings.RELATIONSHIP_EMBEDDING_LLM_UNLOAD_TIMEOUT_SECONDS,
            poll_seconds=settings.RELATIONSHIP_EMBEDDING_LLM_UNLOAD_POLL_SECONDS,
        )
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        LOGGER.warning(
            "Could not verify %s model release before %s: %s",
            model_role,
            target_role,
            exc,
        )
        return

    if released:
        LOGGER.info(
            "%s model is no longer listed by Ollama; continuing with %s",
            model_role.capitalize(),
            target_role,
        )
    else:
        LOGGER.warning(
            "%s model %s is still listed by Ollama after %.1f seconds; continuing to avoid waiting indefinitely",
            model_role.capitalize(),
            model,
            settings.RELATIONSHIP_EMBEDDING_LLM_UNLOAD_TIMEOUT_SECONDS,
        )


def preload_ollama_model_for_settings(
    settings: Settings,
    *,
    model: str,
    model_role: str,
    target_role: str,
    endpoint_setting: str,
    operation: str,
) -> None:
    if not model:
        LOGGER.info(
            "Skipping %s model preload before %s: model is not configured",
            model_role,
            target_role,
        )
        return

    endpoint = resolve_ollama_runtime_endpoint(endpoint_setting)
    if endpoint is None:
        LOGGER.info(
            "Skipping %s model preload before %s: endpoint is not an Ollama /api endpoint",
            model_role,
            target_role,
        )
        return

    LOGGER.info(
        "Requesting %s model preload before %s: %s",
        model_role,
        target_role,
        model,
    )
    try:
        if operation == "embed":
            request_ollama_embedding_model_preload(
                endpoint.embed_url,
                model,
                timeout_seconds=min(
                    max(float(settings.EMBEDDING_TIMEOUT_SECONDS), 5.0), 30.0
                ),
            )
        else:
            request_ollama_model_preload(
                endpoint.generate_url,
                model,
                timeout_seconds=min(max(float(settings.LLM_TIMEOUT_SECONDS), 5.0), 30.0),
            )
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        LOGGER.warning(
            "Could not request %s model preload before %s: %s",
            model_role,
            target_role,
            exc,
        )


def resolve_ollama_runtime_endpoint(llm_endpoint: str) -> OllamaRuntimeEndpoint | None:
    parsed = urlparse(llm_endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    path = parsed.path.rstrip("/")
    lower_path = path.lower()
    marker = "/api/"
    marker_index = lower_path.rfind(marker)
    if marker_index < 0:
        return None
    operation = lower_path[marker_index + len(marker) :]
    if operation not in {"generate", "chat", "embeddings", "embed"}:
        return None

    api_root_path = path[:marker_index] + "/api"
    base_url = urlunparse(
        (parsed.scheme, parsed.netloc, api_root_path.rstrip("/"), "", "", "")
    )
    return OllamaRuntimeEndpoint(
        base_url=base_url,
        generate_url=base_url + "/generate",
        embed_url=base_url + ("/embeddings" if operation == "embeddings" else "/embed"),
        ps_url=base_url + "/ps",
    )


def request_ollama_model_unload(
    generate_url: str, model: str, *, timeout_seconds: float
) -> None:
    body = json.dumps(
        {"model": model, "prompt": "", "stream": False, "keep_alive": 0}
    ).encode("utf-8")
    request = urllib.request.Request(
        generate_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response.read()


def request_ollama_model_preload(
    generate_url: str, model: str, *, timeout_seconds: float
) -> None:
    body = json.dumps(
        {"model": model, "prompt": "", "stream": False}
    ).encode("utf-8")
    request = urllib.request.Request(
        generate_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response.read()


def request_ollama_embedding_model_preload(
    embed_url: str, model: str, *, timeout_seconds: float
) -> None:
    payload = (
        {"model": model, "input": "doctriage preload"}
        if embed_url.rstrip("/").lower().endswith("/api/embed")
        else {"model": model, "prompt": "doctriage preload"}
    )
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        embed_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response.read()


def wait_for_ollama_model_release(
    ps_url: str,
    model: str,
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while True:
        running_models = fetch_ollama_running_models(ps_url)
        if not any(ollama_model_matches(model, running) for running in running_models):
            return True

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return False
        time.sleep(min(poll_seconds, remaining))


def fetch_ollama_running_models(ps_url: str) -> list[dict[str, Any]]:
    with urllib.request.urlopen(ps_url, timeout=5.0) as response:
        payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    return [item for item in models if isinstance(item, dict)]


def ollama_model_matches(configured_model: str, running_model: dict[str, Any]) -> bool:
    configured = normalize_ollama_model_name(configured_model)
    if not configured:
        return False

    for key in ("name", "model"):
        running = normalize_ollama_model_name(str(running_model.get(key) or ""))
        if not running:
            continue
        if configured == running:
            return True
        if ":" not in configured and running == f"{configured}:latest":
            return True
        if ":" not in running and configured == f"{running}:latest":
            return True
    return False


def normalize_ollama_model_name(value: str) -> str:
    return value.strip().lower()


def models_are_same(left: str, right: str) -> bool:
    normalized_left = normalize_ollama_model_name(left)
    normalized_right = normalize_ollama_model_name(right)
    if not normalized_left or not normalized_right:
        return False
    if normalized_left == normalized_right:
        return True
    if ":" not in normalized_left and normalized_right == f"{normalized_left}:latest":
        return True
    if ":" not in normalized_right and normalized_left == f"{normalized_right}:latest":
        return True
    return False
