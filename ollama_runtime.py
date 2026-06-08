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
    ps_url: str


def release_scoring_model_before_embedding_relationships(settings: Settings) -> None:
    model = str(settings.LLM_MODEL or "").strip()
    if not model:
        LOGGER.info(
            "Skipping scoring model release before embedding relationships: LLM_MODEL is not configured"
        )
        return

    endpoint = resolve_ollama_runtime_endpoint(settings.LLM_ENDPOINT)
    if endpoint is None:
        LOGGER.info(
            "Skipping scoring model release before embedding relationships: LLM_ENDPOINT is not an Ollama /api endpoint"
        )
        return

    LOGGER.info(
        "Requesting scoring model unload before embedding relationship mining: %s",
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
            "Could not request scoring model unload before embedding relationships: %s",
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
            "Could not verify scoring model release before embedding relationships: %s",
            exc,
        )
        return

    if released:
        LOGGER.info(
            "Scoring model is no longer listed by Ollama; starting embedding relationship mining"
        )
    else:
        LOGGER.warning(
            "Scoring model %s is still listed by Ollama after %.1f seconds; continuing to avoid waiting indefinitely",
            model,
            settings.RELATIONSHIP_EMBEDDING_LLM_UNLOAD_TIMEOUT_SECONDS,
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
    if operation not in {"generate", "chat"}:
        return None

    api_root_path = path[:marker_index] + "/api"
    base_url = urlunparse(
        (parsed.scheme, parsed.netloc, api_root_path.rstrip("/"), "", "", "")
    )
    return OllamaRuntimeEndpoint(
        base_url=base_url,
        generate_url=base_url + "/generate",
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
