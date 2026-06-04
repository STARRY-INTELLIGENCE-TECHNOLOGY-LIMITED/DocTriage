from __future__ import annotations

from .base import PairCollector, collect_pairs
from .citation import collect_citation_pairs
from .embedding import EmbeddingPairCollector
from .filename import FilenamePairCollector
from .path import PathPairCollector
from .time import TimePairCollector

DEFAULT_PAIR_COLLECTORS: tuple[PairCollector, ...] = (
    FilenamePairCollector(),
    TimePairCollector(),
    PathPairCollector(),
    EmbeddingPairCollector(),
)

__all__ = [
    "DEFAULT_PAIR_COLLECTORS",
    "EmbeddingPairCollector",
    "FilenamePairCollector",
    "PairCollector",
    "PathPairCollector",
    "TimePairCollector",
    "collect_citation_pairs",
    "collect_pairs",
]
