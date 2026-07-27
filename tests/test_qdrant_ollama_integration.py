import json
import os
from pathlib import Path

import pytest

from config import Settings
from rag_indexer import RagIndexSelection, build_rag_index, search_rag_index


pytestmark = pytest.mark.skipif(
    os.environ.get("DOCTRIAGE_RUN_OLLAMA_INTEGRATION") != "1",
    reason="Set DOCTRIAGE_RUN_OLLAMA_INTEGRATION=1 to run the local Ollama test.",
)


def test_real_ollama_embedding_builds_and_searches_qdrant_local(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    output_root = tmp_path / "output"
    state_dir = output_root / "_state"
    source_dir.mkdir()
    state_dir.mkdir(parents=True)
    fixtures = [
        (
            "office.md",
            "办公室政治中，获得领导长期信任需要稳定交付、守住边界并建立可信度。",
        ),
        ("bread.md", "制作面包需要控制含水量、发酵时间和烘焙温度。"),
    ]
    with (state_dir / "decisions.jsonl").open("w", encoding="utf-8") as handle:
        for filename, text in fixtures:
            source_path = source_dir / filename
            source_path.write_text(text, encoding="utf-8")
            handle.write(
                json.dumps(
                    {
                        "source_path": str(source_path),
                        "relative_path": filename,
                        "status": "planned",
                        "quality": 95,
                        "category": "Business",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    settings = Settings(
        LLM_ENDPOINT="http://127.0.0.1:11434/api/generate",
        SOURCE_DIR=source_dir,
        OUTPUT_ROOT=output_root,
        EMBEDDING_ENDPOINT="http://127.0.0.1:11434/api/embed",
        EMBEDDING_MODEL=os.environ.get(
            "DOCTRIAGE_OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:8b"
        ),
        EMBEDDING_TIMEOUT_SECONDS=300,
        RAG_VECTOR_STORE_TYPE="qdrant_local",
        RAG_QDRANT_COLLECTION="integration_test",
    )

    status = build_rag_index(
        settings,
        selection=RagIndexSelection(min_quality=0),
        embeddings_enabled=True,
        force=True,
    )
    result = search_rag_index(settings, "如何获得领导的长期信任", top_k=2)

    assert status["manifest"]["vector_store"]["store_type"] == "qdrant_local"
    assert status["manifest"]["vector_store"]["vector_count"] == 2
    assert result["mode"] == "vector"
    assert result["vector_store"] == "qdrant_local"
    assert result["results"][0]["relative_path"] == "office.md"
