# DocTriage Bundle Schema

`doctriage_bundle.v2` is the file contract between DocTriage and downstream tools such as AnyDocsToAgents.

DocTriage owns document triage, scoring, classification, relationship mining, and bundle export. Downstream tools should read this bundle instead of depending on DocTriage internal JSONL logs.

## Top-Level Object

```json
{
  "schema_version": "doctriage_bundle.v2",
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

Each item in `documents` describes one selected document with structured fields.

Required fields:

- `id`: Stable document id generated from the source identity.
- `title`: Display title, usually the filename stem.
- `paths.source`: Original local path. DocTriage never mutates this file.
- `paths.target`: Optional copied/routed path under `OUTPUT_ROOT`.
- `paths.preferred`: Path selected by the exporter according to `--prefer-target-path`.
- `paths.relative`: Path relative to `SOURCE_DIR`.
- `classification.category`: DocTriage category, for example `Architecture`, `Thinking`, `Series`, or `LowQuality`.
- `classification.document_kind`: Normalized document role, for example `ArchitectureDecision`, `IncidentReview`, or `ResearchReport`.
- `classification.topic_tags`: Short canonical topic tags useful for graph projection and downstream filtering.
- `classification.status`: Terminal DocTriage decision status.
- `classification.media_type`: Best-effort media type for downstream adapters.
- `scores`: Numeric quality and risk dimensions from DocTriage.
- `text.summary`: Optional short summary.
- `text.reason`: Scoring/classification reason.

The `scores` object includes:

- `quality`
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

## Relations

Each item in `relations` connects two selected documents.

- `left_document_id`
- `right_document_id`
- `score`
- `signals`: Examples include `filename`, `time`, `path`, `category`, `embedding`, and `version_or_sequence`.
- `evidence.filename_similarity`
- `evidence.time_proximity`
- `evidence.path_proximity`
- `evidence.embedding_similarity`
- `evidence.citation_count`: Number of lightweight title/path citation hits between the pair.

Relations are advisory. Downstream tools should not assume they are complete, symmetric, or globally optimal.

## Compatibility Rules

- Consumers must check `schema_version`.
- Consumers should ignore unknown fields.
- Producers should only remove or rename fields in a new schema version.
- Local paths may contain private information. Public examples should use placeholder paths.

## Example

See `examples/doctriage_bundle.example.json`.
