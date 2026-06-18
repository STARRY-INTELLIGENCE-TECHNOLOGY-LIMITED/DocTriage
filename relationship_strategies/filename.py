from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .common import add_window_pairs


class FilenamePairCollector:
    name = "filename"

    def collect(
        self,
        records: list[Any],
        embeddings: Mapping[int, list[float]],
        settings: Any,
    ) -> set[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()
        ordered = sorted(range(len(records)), key=lambda index: records[index].normalized_name)
        add_window_pairs(pairs, ordered, settings.RELATIONSHIP_FILENAME_WINDOW)
        return pairs
