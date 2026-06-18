# DocTriage

Local-first document triage for manual curation, connected learning, RAG, and agent workflows.

[Chinese README](README.zh-CN.md)

DocTriage scans a source folder, extracts text, asks a local LLM to score and explain each document, and gives you a browser console for review, reading status, failure handling, relationship mining, and export. It is useful both for modern AI pipelines and for old-school document selection, sequential reading, and learning by association.

Your source folder stays read-only. DocTriage writes state, logs, relationship results, and optional routed copies under `OUTPUT_ROOT`.

<p align="center">
  <img src="https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/triage.jpg?raw=true" alt="DocTriage overview" width="900">
</p>

DocTriage is built around a practical loop: run local analysis, review and mark documents in the reading console, then use relationship clusters when you need connected learning or downstream exports.

## Why

- Triage large, messy folders without reorganizing the original files.
- Curate documents manually by quality, path order, modification time, and reading status.
- Score documents with explainable signals, not just filenames.
- Review files in a reading console with open, reveal, read, defer, and skip actions.
- Keep failed files visible until they are fixed, skipped, or accepted as failures.
- Learn across related documents through duplicates, series, same-topic clusters, and source-folder context.
- Export stable bundles for downstream RAG or agent tools when needed.

## Features

- Resume-safe analysis with a per-output lock.
- `--plan-only` mode for scoring without copying files into routed folders.
- Reading console with analysis-result and all-source-file views.
- Explainable rows: summary, scoring reason, and dimension scores.
- Failed-file rows with stage, reason, attempts, and direct open/reveal actions.
- Filtered CSV/JSONL export from the current reading view.
- Output language selection for generated summaries and reasons.
- Separate UI language switch in the top-right corner.
- Relationship graph for connected learning, deduplication, and downstream bundle export.

## Screenshots

**Analysis Execution**

![Analysis execution](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/analysis_eng.png?raw=true)

Configure source/output folders, local model settings, plan-only runs, resume behavior, progress, logs, and failure status from one place.

**Reading Console**

![Reading console](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/reading_eng.png?raw=true)

Review scored documents or browse all source files in folder order, then open, reveal, mark, filter, and export the current working set.

**Relationship Graph**

![Relationship graph](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/DocTriage/blob/main/sample_pictures/graph_eng.png?raw=true)

Mine relationship clusters for duplicate detection, series discovery, connected learning, knowledge graph export, and bundle generation.

## Requirements

- Python `>=3.11,<3.15`
- An LLM endpoint: Ollama locally, or an OpenAI-compatible REST endpoint
- Optional: LibreOffice for legacy `.ppt` ingestion

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
Copy-Item .env.example .env
```

Linux and macOS use the same flow with `source .venv/bin/activate` and `cp .env.example .env`.

## Quick Start

Start the browser console:

```powershell
doctriage-reading-ui --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`.

Recommended first pass for a large folder:

```powershell
doctriage `
  --source-dir "D:\example_docs" `
  --output-root "D:\doctriage_run" `
  --llm-endpoint http://localhost:11434/api/generate `
  --llm-model gemma4:e4b `
  --concurrency 1 `
  --plan-only `
  --no-ocr `
  --skip-manifest-analysis `
  --timeout-seconds 240
```

If console scripts are not on `PATH`, run the modules from the checkout:

```powershell
.\.venv\Scripts\python.exe reading_ui.py --host 127.0.0.1 --port 8765
.\.venv\Scripts\python.exe main.py --help
```

## Model Endpoints

DocTriage can run without Ollama if your provider exposes OpenAI-compatible REST APIs:

- scoring/classification: set `LLM_ENDPOINT` to `/v1/chat/completions`, set `LLM_MODEL`, and provide `LLM_API_KEY`;
- relationship/RAG embeddings: set `EMBEDDING_ENDPOINT` to `/v1/embeddings`, set `EMBEDDING_MODEL`, and optionally provide `EMBEDDING_API_KEY`;
- if `EMBEDDING_API_KEY` is empty, embedding requests reuse `LLM_API_KEY`.

The browser console has API key fields for ad hoc runs. It passes keys to worker processes through environment variables and does not save them in browser storage.

## Core Workflow

1. **Run a plan-only pass**

   Get scores, categories, summaries, and reasons without creating copied `HQ` or `LQ` folders.

2. **Review in the reading console**

   Use the analysis view for scored documents and the source view for folder-ordered browsing across every current source file.

3. **Close the loop on failures**

   Failed files appear as rows with stage, reason, attempts, size, and direct open/reveal actions.

4. **Follow relationships and folder context**

   Use source-folder ordering for sequential reading, then use relationship clusters to jump across related documents.

5. **Export filtered decisions**

   Filter the reading table, then export CSV or JSONL for audit, writing, RAG planning, or external review.

6. **Mine relationships when scores are stable**

   Generate clusters and graph exports after the first-pass decisions are good enough.

## CLI

| Command | Purpose |
| --- | --- |
| `doctriage` | Run document analysis |
| `doctriage-reading-ui` | Start the browser console |
| `doctriage-reading` | Read or update reading status from CLI |
| `doctriage-relationships` | Mine document relationships |
| `doctriage-graph` | Export a knowledge graph |
| `doctriage-bundle` | Export a stable downstream bundle |
| `doctriage-rag` | Build or search the resumable RAG chunk index |
| `doctriage-workflow` | Workflow adapter entrypoint |

Each command supports `--help`.

## Output Layout

```text
OUTPUT_ROOT/
  _state/
    progress.json
    run_summary.json
    decisions.jsonl
    processed_files.jsonl
    failed_files.jsonl
    reading_status.jsonl
  _logs/
    doctriage.log
  _relationships/
    relations.jsonl
    clusters.json
    knowledge_graph.json
    doctriage_bundle.json
  _rag/
    progress.json
    manifest.json
    documents.jsonl
    chunks.jsonl
    vectors.jsonl
```

Downstream integrations should prefer `doctriage_bundle.json` over internal JSONL logs.

## AnyDocsToAgents Handoff

The browser console has an **Agent compile** tab for optional handoff to [AnyDocsToAgents](https://github.com/STARRY-INTELLIGENCE-TECHNOLOGY-LIMITED/AnyDocsToAgents). It exports `OUTPUT_ROOT/_relationships/doctriage_bundle.json` and opens AnyDocsToAgents with a URL such as:

```text
http://127.0.0.1:8000/?doctriage_bundle_path=D:\doctriage_run\_relationships\doctriage_bundle.json&autoplan=1#view-planner
```

This is intentionally a loose bridge: DocTriage does not start, embed, or depend on AnyDocsToAgents. Both projects can still run independently.

## Language

DocTriage has two separate language controls:

- Output language controls generated summaries and scoring reasons. `Auto` infers the document language.
- UI language changes console labels only. It does not affect LLM output.

## More Documentation

- [Bundle schema](docs/bundle_schema.md)
- [Knowledge graph abstraction](docs/knowledge_graph.md)
- [Recipes](recipes/README.md)
- [Chinese README](README.zh-CN.md)

## Notes

- Do not place `OUTPUT_ROOT` inside `SOURCE_DIR`.
- Desktop open/reveal actions depend on the local environment.
- Headless servers can run analysis and the web UI, but folder picker and open/reveal actions may be unavailable.
