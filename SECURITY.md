# Security

DocTriage is designed for local private document processing.

## Sensitive Data

- Do not commit real document folders, generated `data/`, `_state/`, `_logs/`, `_relationships/`, or JSONL logs.
- Use placeholder paths in public examples.
- Treat `decisions.jsonl`, `relations.jsonl`, and bundle files as potentially sensitive because they may contain paths, filenames, categories, scores, and optional summaries.

## Safe Defaults

- Source directories are read-only.
- `OUTPUT_ROOT` must not be inside `SOURCE_DIR`.
- Local summaries, PDF metadata extraction, embeddings, and OCR are configurable.

## Reporting

For public use, open an issue with a minimal reproduction. Do not include private document content or private paths.
