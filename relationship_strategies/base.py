from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class PairCollector(Protocol):
    name: str

    def collect(
        self,
        records: list[Any],
        embeddings: Mapping[int, list[float]],
        settings: Any,
    ) -> set[tuple[int, int]]:
        """Return normalized candidate document index pairs."""


def collect_pairs(
    collectors: tuple[PairCollector, ...],
    records: list[Any],
    embeddings: Mapping[int, list[float]],
    settings: Any,
) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for collector in collectors:
        pairs.update(collector.collect(records, embeddings, settings))
    return pairs
