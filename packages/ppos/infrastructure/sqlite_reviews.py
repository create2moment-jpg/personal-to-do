"""SQLite repository for periodic reviews."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any

from ppos.domain.reviews import Review

_COLS = [f.name for f in fields(Review)]
_TS = {"created_at", "updated_at", "finalized_at"}


def _enc(name: str, v: object) -> object:
    if name in _TS and isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    if name == "snapshot":
        return json.dumps(v)
    return v


def _review(r: sqlite3.Row) -> Review:
    values: dict[str, Any] = {}
    for c in _COLS:
        v = r[c]
        if c in _TS and v:
            v = datetime.fromisoformat(v)
        elif c == "snapshot":
            v = json.loads(v or "{}")
        values[c] = v
    return Review(**values)


class SqliteReviewRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def add(self, r: Review) -> None:
        self._c.execute(
            f"INSERT INTO reviews ({', '.join(_COLS)}) VALUES ({','.join('?' * len(_COLS))})",
            [_enc(c, getattr(r, c)) for c in _COLS],
        )

    def update(self, r: Review) -> None:
        cols = [c for c in _COLS if c != "id"]
        self._c.execute(
            f"UPDATE reviews SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
            [*(_enc(c, getattr(r, c)) for c in cols), r.id],
        )

    def get(self, review_id: str) -> Review | None:
        row = self._c.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
        return _review(row) if row else None

    def by_period(self, kind: str, period: str) -> Review | None:
        row = self._c.execute(
            "SELECT * FROM reviews WHERE kind = ? AND period = ?", (kind, period)
        ).fetchone()
        return _review(row) if row else None

    def all(self) -> list[Review]:
        return [
            _review(r) for r in self._c.execute("SELECT * FROM reviews ORDER BY period DESC, kind")
        ]

    def delete(self, review_id: str) -> None:
        self._c.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
