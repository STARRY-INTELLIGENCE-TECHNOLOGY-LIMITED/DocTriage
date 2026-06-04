# Pre-RAG Knowledge Graph Abstraction

DocTriage builds a pre-ingestion knowledge graph before chunking documents into a RAG index. The graph is intentionally lightweight: it captures document quality, routing policy, categories, and relationship evidence without requiring a graph database.

## Core Objects

`DocumentNode`

Represents one source document after parsing and scoring.

Key fields:

- `id`: Stable document identifier derived from relative path.
- `relative_path`: Path under the source root.
- `target_path`: Planned or copied routing destination.
- `category`: `Architecture`, `Design`, `Implementation`, `Operations`, `CaseStudy`, `Research`, `Business`, `Thinking`, `Series`, or `LowQuality`.
- `document_kind`: Normalized document role such as `ArchitectureDecision`, `ImplementationGuide`, `IncidentReview`, or `ResearchReport`.
- `topic_tags`: Short canonical tags projected into topic nodes.
- `quality`: 0-100 triage score.
- Extended value signals: `evidence_richness`, `actionability`, `strategic_value`, `freshness`, `uniqueness`, `sensitivity_risk`, and `public_writing_suitability`.
- `summary`: Optional local short summary for relationship mining.
- `attributes.ingestion_action`: `ingest` or `archive`.

`RelationshipEdge`

Represents evidence-backed relationships between graph nodes.

Supported edge types:

- `RELATED_TO`: General relationship when evidence is useful but not specific enough.
- `SAME_SERIES`: Filename and time signals suggest a sequence.
- `NEAR_DUPLICATE`: High filename and embedding similarity.
- `EVOLVES_TO`: Version or sequence signals suggest evolution.
- `SAME_TOPIC`: Embedding or semantic signals suggest topical proximity.
- `BELONGS_TO`: Projection edge to a category or cluster.
- `TAGGED_AS`: Projection edge from a document to a topic tag.
- `HAS_KIND`: Projection edge from a document to a normalized document kind.
- `ROUTED_BY`: Projection edge to an ingestion policy.

`DocumentCluster`

Represented as a `KnowledgeNode` of type `Cluster`. Clusters are connected components projected from mined document relationships.

`IngestionPolicy`

Represents routing policy as graph nodes:

- `policy:ingest_hq`: High-quality documents are eligible for RAG ingestion.
- `policy:archive_lq`: Low-quality documents should be archived or reviewed.

## Pipeline Shape

1. `main.py` parses, cleans, scores, and writes `OUTPUT_ROOT/_state/decisions.jsonl`.
2. `relationship_miner.py` mines candidate document relationships and writes `OUTPUT_ROOT/_relationships/relations.jsonl`.
3. `knowledge_graph.py` projects decisions and relations into `OUTPUT_ROOT/_relationships/knowledge_graph.json`.

State logs are append-only. If a document is reprocessed because its source fingerprint or settings signature changed, later records supersede earlier records during relationship mining and graph export.

## Design Principle

The graph layer is a pre-RAG map, not the final RAG index. It should answer:

- Which documents deserve ingestion?
- Which documents should be archived or reviewed?
- Which documents are likely same-series, same-topic, duplicates, or evolution chains?
- Which cluster should be ingested as a coherent context set?

Chunking and vector indexing should happen after this layer, using graph metadata to set priority, grouping, deduplication, and retrieval-time context expansion.
