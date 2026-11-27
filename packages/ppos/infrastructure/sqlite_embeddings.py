"""SQLite store for local embeddings."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


class SqliteEmbeddingStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def hashes(self, model: str) -> dict[str, str]:
        rows = self._c.execute("SELECT key, text_hash FROM embeddings WHERE model = ?", (model,))
        return {r[0]: r[1] for r in rows}

    def put(self, key: str, model: str, text_hash: str, dim: int, vector: bytes) -> None:
        self._c.execute(
            "INSERT INTO embeddings (key, model, text_hash, dim, vector, updated_at) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT (key) DO UPDATE SET model=excluded.model, text_hash=excluded.text_hash,"
            " dim=excluded.dim, vector=excluded.vector, updated_at=excluded.updated_at",
            (key, model, text_hash, dim, vector, datetime.now(timezone.utc).isoformat()),
        )

    def vectors(self, model: str) -> list[tuple[str, bytes]]:
        rows = self._c.execute("SELECT key, vector FROM embeddings WHERE model = ?", (model,))
        return [(r[0], bytes(r[1])) for r in rows]

    def prune(self, keep: set[str]) -> int:
        stale = [r[0] for r in self._c.execute("SELECT key FROM embeddings") if r[0] not in keep]
        for k in stale:
            self._c.execute("DELETE FROM embeddings WHERE key = ?", (k,))
        return len(stale)

    def count(self, model: str) -> int:
        return int(
            self._c.execute("SELECT COUNT(*) FROM embeddings WHERE model = ?", (model,)).fetchone()[
                0
            ]
        )
