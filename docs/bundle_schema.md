# DocTriage Bundle Schema

`doctriage_bundle.v1` is the stable file contract between DocTriage and downstream tools such as PdfToMultiAgents.

DocTriage owns document triage, scoring, classification, relationship mining, and bundle export. Downstream tools should read this bundle instead of depending on DocTriage internal JSONL logs.

## Top-Level Object

```json
{
  "schema_version": "doctriage_bundle.v1",
  "title": "Architecture Thinking Bundle",
  "generated_at": "2026-05-01T00:00:00+00:00",
  "source": {},
  "selection_policy": {},
  "statistics": {},
  "documents": [],
  "relations": []
}
```

## Documents

Each item in `documents` describes one selected document.

Required for downstream planning:

- `id`: Stable document id generated from the source identity.
- `source_path`: Original local path. DocTriage never mutates this file.
- `target_path`: Optional copied/routed path under `OUTPUT_ROOT`.
- `preferred_path`: Path selected by the exporter according to `--prefer-target-path`.
- `relative_path`: Path relative to `SOURCE_DIR`.
- `title`: Display title, usually the filename stem.
- `category`: DocTriage category, for example `Architecture`, `Thinking`, `Series`, or `LowQuality`.
- `document_kind`: Normalized document role, for example `ArchitectureDecision`, `IncidentReview`, or `ResearchReport`.
- `topic_tags`: Short canonical topic tags useful for graph projection and downstream filtering.
- `quality`: Integer quality score from `0` to `100`.
- `media_type`: Best-effort media type for downstream adapters.

Optional quality signals:

- `knowledge_density`
- `implementation_specificity`
- `logical_structure`
- `evidence_richness`
- `actionability`
- `strategic_value`
- `freshness`
- `uniqueness`
- `sensitivity_risk`
- `public_writing_suitability`
- `reason`
- `summary`
- `status`

## Relations

Each item in `relations` connects two selected documents.

- `left_relative_path`
- `right_relative_path`
- `relation_score`
- `signals`: Examples include `filename`, `time`, `path`, `category`, `embedding`, and `version_or_sequence`.
- `filename_similarity`
- `time_proximity`
- `path_proximity`
- `embedding_similarity`
- `citation_count`: Number of lightweight title/path citation hits between the pair.

Relations are advisory. Downstream tools should not assume they are complete, symmetric, or globally optimal.

## Compatibility Rules

- Consumers must check `schema_version`.
- Consumers should ignore unknown fields.
- Producers should only remove or rename fields in a new schema version.
- Local paths may contain private information. Public examples should use placeholder paths.

## Example

See `examples/doctriage_bundle.example.json`.
