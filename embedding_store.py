from __future__ import annotations

import json
import sqlite3
import time
from collections import OrderedDict
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path


class SQLiteEmbeddingStore(Mapping[int, list[float]]):
    """Disk-backed embedding lookup keyed by current relationship record index."""

    def __init__(self, path: Path, *, cache_size: int = 512) -> None:
        self.path = Path(path)
        self.cache_size = max(0, int(cache_size))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path), timeout=30)
        self._cache: OrderedDict[int, list[float]] = OrderedDict()
        self._init_schema()

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> "SQLiteEmbeddingStore":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _init_schema(self) -> None:
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_vectors (
                cache_key TEXT PRIMARY KEY,
                dimension INTEGER NOT NULL,
                vector_json TEXT NOT NULL,
                updated_epoch REAL NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS embedding_index (
                record_index INTEGER PRIMARY KEY,
                cache_key TEXT NOT NULL,
                updated_epoch REAL NOT NULL
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_embedding_index_cache_key
            ON embedding_index(cache_key)
            """
        )
        self._connection.commit()

    def clear_index(self) -> None:
        self._connection.execute("DELETE FROM embedding_index")
        self._connection.commit()
        self._cache.clear()

    def clear_all(self) -> None:
        self._connection.execute("DELETE FROM embedding_index")
        self._connection.execute("DELETE FROM embedding_vectors")
        self._connection.commit()
        self._cache.clear()

    def put_vectors(self, entries: Iterable[tuple[str, list[float]]]) -> None:
        rows = [
            (
                key,
                len(vector),
                json.dumps(vector, ensure_ascii=False, separators=(",", ":")),
                time.time(),
            )
            for key, vector in entries
        ]
        if not rows:
            return
        self._connection.executemany(
            """
            INSERT OR REPLACE INTO embedding_vectors
                (cache_key, dimension, vector_json, updated_epoch)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        self._connection.commit()

    def put_many(self, entries: Iterable[tuple[int, str, list[float]]]) -> None:
        rows = list(entries)
        if not rows:
            return
        now = time.time()
        self._connection.executemany(
            """
            INSERT OR REPLACE INTO embedding_vectors
                (cache_key, dimension, vector_json, updated_epoch)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    key,
                    len(vector),
                    json.dumps(vector, ensure_ascii=False, separators=(",", ":")),
                    now,
                )
                for _, key, vector in rows
            ],
        )
        self._connection.executemany(
            """
            INSERT OR REPLACE INTO embedding_index
                (record_index, cache_key, updated_epoch)
            VALUES (?, ?, ?)
            """,
            [(index, key, now) for index, key, _ in rows],
        )
        self._connection.commit()
        for index, _, vector in rows:
            self._remember(index, vector)

    def has_vector(self, key: str) -> bool:
        row = self._connection.execute(
            "SELECT 1 FROM embedding_vectors WHERE cache_key = ?",
            (key,),
        ).fetchone()
        return row is not None

    def bind_existing(self, entries: Iterable[tuple[int, str]]) -> set[int]:
        bindings: list[tuple[int, str, float]] = []
        bound_indexes: set[int] = set()
        cursor = self._connection.cursor()
        now = time.time()
        for index, key in entries:
            if cursor.execute(
                "SELECT 1 FROM embedding_vectors WHERE cache_key = ?",
                (key,),
            ).fetchone():
                bindings.append((index, key, now))
                bound_indexes.add(index)
        if not bindings:
            return bound_indexes
        self._connection.executemany(
            """
            INSERT OR REPLACE INTO embedding_index
                (record_index, cache_key, updated_epoch)
            VALUES (?, ?, ?)
            """,
            bindings,
        )
        self._connection.commit()
        self._cache.clear()
        return bound_indexes

    def __getitem__(self, index: int) -> list[float]:
        cached = self._cache.get(index)
        if cached is not None:
            self._cache.move_to_end(index)
            return cached

        row = self._connection.execute(
            """
            SELECT vectors.vector_json
            FROM embedding_index AS current_index
            JOIN embedding_vectors AS vectors
                ON vectors.cache_key = current_index.cache_key
            WHERE current_index.record_index = ?
            """,
            (index,),
        ).fetchone()
        if row is None:
            raise KeyError(index)
        vector = [float(value) for value in json.loads(row[0])]
        self._remember(index, vector)
        return vector

    def get(self, index: int, default: list[float] | None = None) -> list[float] | None:
        try:
            return self[index]
        except KeyError:
            return default

    def __contains__(self, index: object) -> bool:
        if not isinstance(index, int):
            return False
        if index in self._cache:
            return True
        row = self._connection.execute(
            """
            SELECT 1
            FROM embedding_index AS current_index
            JOIN embedding_vectors AS vectors
                ON vectors.cache_key = current_index.cache_key
            WHERE current_index.record_index = ?
            """,
            (index,),
        ).fetchone()
        return row is not None

    def __iter__(self) -> Iterator[int]:
        cursor = self._connection.execute(
            """
            SELECT current_index.record_index
            FROM embedding_index AS current_index
            JOIN embedding_vectors AS vectors
                ON vectors.cache_key = current_index.cache_key
            ORDER BY current_index.record_index
            """
        )
        for row in cursor:
            yield int(row[0])

    def __len__(self) -> int:
        row = self._connection.execute(
            """
            SELECT COUNT(*)
            FROM embedding_index AS current_index
            JOIN embedding_vectors AS vectors
                ON vectors.cache_key = current_index.cache_key
            """
        ).fetchone()
        return int(row[0]) if row else 0

    def __bool__(self) -> bool:
        return len(self) > 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self.items()) == dict(other.items())
        return NotImplemented

    def _remember(self, index: int, vector: list[float]) -> None:
        if self.cache_size <= 0:
            return
        self._cache[index] = vector
        self._cache.move_to_end(index)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
