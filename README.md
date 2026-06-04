# DocTriage

Local document triage for RAG and agent workflows. DocTriage scans a source directory, scores documents with a local LLM, records resumable state, and gives you a browser console for analysis, reading, and relationship review.

The source directory is treated as read-only. All state, logs, and exports are written to `OUTPUT_ROOT`.

## Features

- Resume-safe analysis with `OUTPUT_ROOT/_state/run.lock`
- `plan-only` mode for first-pass scoring without copying files
- Reading console with filters, sorting, open/reveal, and reading status
- Relationship mining with clusters and a local graph tab
- Reset button for clearing one output root after confirmation
- CLI exports for knowledge graph and downstream bundle files

## Requirements

- Python `>=3.11`
- A local LLM endpoint such as Ollama
- Optional: LibreOffice for legacy `.ppt`

## Install

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
Copy-Item .env.example .env
```

Linux / macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

## Quick Start

Start the UI:

```powershell
.\.venv\Scripts\python.exe reading_ui.py --host 127.0.0.1 --port 8765
```

Or launch the default UI entrypoint:

```powershell
.\.venv\Scripts\python.exe main.py
```

Open `http://127.0.0.1:8765/`.

Recommended first run for large folders:

```powershell
.\.venv\Scripts\python.exe main.py `
  --source-dir "D:\example_docs" `
  --output-root "D:\doctriage_run" `
  --llm-endpoint http://localhost:11434/api/generate `
  --llm-model gemma4:e4b `
  --concurrency 1 `
  --plan-only `
  --no-ocr `
  --skip-manifest-analysis `
  --require-local-llm `
  --timeout-seconds 240
```

## UI

The browser console has three tabs:

- `分析执行`
  - Start, stop, resume, or reset one output root
  - Shows current phase such as scan, resume, scoring, or relationship mining
  - Supports templates and collapsible advanced options
- `阅读台`
  - Filter by status, quality, category, tags, sensitivity, and writing suitability
  - Open or reveal files and mark reading status
- `关系图谱`
  - Review mined clusters and local document-to-document edges
  - Generate relationship results, export a knowledge graph, or export a bundle
  - Inspect one cluster at a time instead of rendering an unreadable global graph

## CLI

Main analysis:

```powershell
.\.venv\Scripts\python.exe main.py --help
```

Relationship mining:

```powershell
.\.venv\Scripts\python.exe relationship_miner.py --help
```

Knowledge graph export:

```powershell
.\.venv\Scripts\python.exe knowledge_graph.py --help
```

Bundle export:

```powershell
.\.venv\Scripts\python.exe bundle_exporter.py --help
```

Reading status CLI:

```powershell
.\.venv\Scripts\python.exe reading_tracker.py --help
```

## Relationship Outputs

Relationship mining writes to `OUTPUT_ROOT/_relationships/`:

- `relations.jsonl`: pairwise relationships and evidence
- `clusters.json`: connected components for cluster review
- `knowledge_graph.json`: exported graph projection
- `doctriage_bundle.json`: downstream bundle for other tools

The graph tab reads `clusters.json` and `relations.jsonl`. If they do not exist yet, use the graph tab action buttons to generate them after analysis.

## Output Layout

- `_state/progress.json`: current progress snapshot
- `_state/decisions.jsonl`: scored document decisions
- `_state/processed_files.jsonl`: processed log
- `_state/failed_files.jsonl`: failure log
- `_state/reading_status.jsonl`: reading events
- `_logs/doctriage.log`: analysis and background task log
- `_relationships/`: relationship and export artifacts

## Resume and Reset

- Re-running with the same `OUTPUT_ROOT` resumes automatically
- Changed files or changed key settings are reprocessed
- Only one analysis process may write to one `OUTPUT_ROOT` at a time
- `重置分析` clears the selected output root after confirmation
- Do not place `OUTPUT_ROOT` inside `SOURCE_DIR`

## Notes

- Desktop integrations depend on the local environment
- Headless servers can still run analysis and the web UI, but folder picker and open/reveal actions may be unavailable
- Downstream integrations should prefer `doctriage_bundle.json` over internal JSONL logs
