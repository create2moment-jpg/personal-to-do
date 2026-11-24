"""SQLite repository for career expectations and evidence links."""

from __future__ import annotations

import sqlite3
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any

from ppos.domain.career import EvidenceLink, Expectation

_EXP_COLS = [f.name for f in fields(Expectation)]
_LINK_COLS = [f.name for f in fields(EvidenceLink)]
_TS = {"created_at", "updated_at"}


def _enc(name: str, v: object) -> object:
    if name in _TS and isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    return v


def _values(r: sqlite3.Row, cols: list[str]) -> dict[str, Any]:
    return {c: datetime.fromisoformat(r[c]) if c in _TS else r[c] for c in cols}


def _exp(r: sqlite3.Row) -> Expectation:
    return Expectation(**_values(r, _EXP_COLS))


def _link(r: sqlite3.Row) -> EvidenceLink:
    return EvidenceLink(**_values(r, _LINK_COLS))


class SqliteCareerRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def add_expectation(self, e: Expectation) -> None:
        self._c.execute(
            f"INSERT INTO career_expectations ({', '.join(_EXP_COLS)}) "
            f"VALUES ({','.join('?' * len(_EXP_COLS))})",
            [_enc(c, getattr(e, c)) for c in _EXP_COLS],
        )

    def update_expectation(self, e: Expectation) -> None:
        cols = [c for c in _EXP_COLS if c != "id"]
        self._c.execute(
            f"UPDATE career_expectations SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
            [*(_enc(c, getattr(e, c)) for c in cols), e.id],
        )

    def delete_expectation(self, expectation_id: str) -> None:
        self._c.execute("DELETE FROM career_expectations WHERE id = ?", (expectation_id,))

    def get_expectation(self, expectation_id: str) -> Expectation | None:
        r = self._c.execute(
            "SELECT * FROM career_expectations WHERE id = ?", (expectation_id,)
        ).fetchone()
        return _exp(r) if r else None

    def expectations(self) -> list[Expectation]:
        rows = self._c.execute(
            "SELECT * FROM career_expectations ORDER BY level, position, created_at"
        )
        return [_exp(r) for r in rows]

    def max_position(self, level: str) -> float:
        r = self._c.execute(
            "SELECT COALESCE(MAX(position), 0) FROM career_expectations WHERE level = ?", (level,)
        ).fetchone()
        return float(r[0])

    def add_link(self, link: EvidenceLink) -> None:
        self._c.execute(
            f"INSERT INTO evidence_links ({', '.join(_LINK_COLS)}) "
            f"VALUES ({','.join('?' * len(_LINK_COLS))})",
            [_enc(c, getattr(link, c)) for c in _LINK_COLS],
        )

    def get_link(self, expectation_id: str, fact_id: str) -> EvidenceLink | None:
        r = self._c.execute(
            "SELECT * FROM evidence_links WHERE expectation_id = ? AND fact_id = ?",
            (expectation_id, fact_id),
        ).fetchone()
        return _link(r) if r else None

    def delete_link(self, expectation_id: str, fact_id: str) -> int:
        cur = self._c.execute(
            "DELETE FROM evidence_links WHERE expectation_id = ? AND fact_id = ?",
            (expectation_id, fact_id),
        )
        return cur.rowcount

    def links(self) -> list[EvidenceLink]:
        rows = self._c.execute("SELECT * FROM evidence_links ORDER BY created_at")
        return [_link(r) for r in rows]
