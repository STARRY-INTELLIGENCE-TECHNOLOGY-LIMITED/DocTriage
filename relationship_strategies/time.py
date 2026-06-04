from __future__ import annotations

from typing import Any

from .common import add_window_pairs


class TimePairCollector:
    name = "time"

    def collect(
        self,
        records: list[Any],
        embeddings: dict[int, list[float]],
        settings: Any,
    ) -> set[tuple[int, int]]:
        pairs: set[tuple[int, int]] = set()
        ordered = sorted(
            range(len(records)),
            key=lambda index: (records[index].modified_epoch, records[index].relative_path),
        )
        add_window_pairs(pairs, ordered, settings.RELATIONSHIP_TIME_WINDOW)
        return pairs
