from __future__ import annotations

from collections import defaultdict
from typing import Any

from .common import cosine_similarity, normalize_pair


class EmbeddingPairCollector:
    name = "embedding"

    def collect(
        self,
        records: list[Any],
        embeddings: dict[int, list[float]],
        settings: Any,
    ) -> set[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()
        indexes = sorted(embeddings)
        if not indexes or len(indexes) > settings.RELATIONSHIP_EMBEDDING_EXHAUSTIVE_LIMIT:
            return pairs

        neighbors: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for position, left in enumerate(indexes):
            for right in indexes[position + 1 :]:
                similarity = cosine_similarity(embeddings[left], embeddings[right])
                neighbors[left].append((similarity, right))
                neighbors[right].append((similarity, left))

        for left, scored_neighbors in neighbors.items():
            for _, right in sorted(scored_neighbors, reverse=True)[
                : settings.RELATIONSHIP_EMBEDDING_TOP_K
            ]:
                pairs.add(normalize_pair(left, right))
        return pairs
