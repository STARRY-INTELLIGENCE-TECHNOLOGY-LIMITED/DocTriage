# Contributing

Keep DocTriage small and predictable.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -e .
python -m pytest -q
python -m compileall -q .
```

## Rules

- Do not mutate source document folders.
- Keep generated state under `OUTPUT_ROOT`.
- Add tests for resume, copy, bundle, and relationship behavior changes.
- Prefer optional flags over mandatory heavy dependencies.
- Keep `doctriage_bundle.v1` backward compatible; if a breaking change is needed, bump the schema version.
