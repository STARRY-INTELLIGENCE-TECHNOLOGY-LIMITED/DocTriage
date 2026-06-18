from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .common import add_window_pairs


class PathPairCollector:
    name = "path"

    def collect(
        self,
        records: list[Any],
        embeddings: Mapping[int, list[float]],
        settings: Any,
    ) -> set[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()
        buckets: dict[str, list[int]] = defaultdict(list)
        for index, record in enumerate(records):
            buckets[str(Path(record.relative_path).parent)].append(index)

        for indexes in buckets.values():
            ordered = sorted(indexes, key=lambda index: records[index].normalized_name)
            add_window_pairs(
                pairs,
                ordered,
                min(settings.RELATIONSHIP_MAX_CANDIDATES_PER_FILE, len(ordered)),
            )
        return pairs
