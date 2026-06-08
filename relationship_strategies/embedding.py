from __future__ import annotations

import heapq
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

        top_k = settings.RELATIONSHIP_EMBEDDING_TOP_K
        neighbors: dict[int, list[tuple[float, int]]] = defaultdict(list)
        for position, left in enumerate(indexes):
            for right in indexes[position + 1 :]:
                similarity = cosine_similarity(embeddings[left], embeddings[right])
                remember_top_neighbor(neighbors[left], top_k, similarity, right)
                remember_top_neighbor(neighbors[right], top_k, similarity, left)

        for left, scored_neighbors in neighbors.items():
            for _, right in sorted(scored_neighbors, reverse=True)[
                :top_k
            ]:
                pairs.add(normalize_pair(left, right))
        return pairs


def remember_top_neighbor(
    neighbors: list[tuple[float, int]], limit: int, similarity: float, index: int
) -> None:
    item = (similarity, index)
    if len(neighbors) < limit:
        heapq.heappush(neighbors, item)
        return
    if item > neighbors[0]:
        heapq.heapreplace(neighbors, item)
