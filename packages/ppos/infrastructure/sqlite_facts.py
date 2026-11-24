"""SQLite repository for extracted facts and extraction runs."""

from __future__ import annotations

import sqlite3
from dataclasses import fields
from datetime import datetime, timezone

from ppos.domain.facts import Fact, FactRun

_FACT_COLS = [f.name for f in fields(Fact)]
_RUN_COLS = [f.name for f in fields(FactRun)]
_TS = {"created_at", "updated_at", "started_at", "finished_at"}


def _enc(name: str, v: object) -> object:
    if name in _TS and isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    return v


def _dec(name: str, v: object) -> object:
    if name in _TS and isinstance(v, str):
        return datetime.fromisoformat(v)
    return v


class SqliteFactRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def add_run(self, r: FactRun) -> None:
        self._c.execute(
            f"INSERT INTO fact_runs ({', '.join(_RUN_COLS)}) VALUES ({','.join('?' * len(_RUN_COLS))})",
            [_enc(c, getattr(r, c)) for c in _RUN_COLS],
        )

    def update_run(self, r: FactRun) -> None:
        cols = [c for c in _RUN_COLS if c != "id"]
        self._c.execute(
            f"UPDATE fact_runs SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
            [*(_enc(c, getattr(r, c)) for c in cols), r.id],
        )

    def get_run(self, run_id: str) -> FactRun | None:
        r = self._c.execute("SELECT * FROM fact_runs WHERE id = ?", (run_id,)).fetchone()
        return FactRun(**{c: _dec(c, r[c]) for c in _RUN_COLS}) if r else None  # type: ignore[arg-type]

    def latest_run(self, document_id: str) -> FactRun | None:
        r = self._c.execute(
            "SELECT * FROM fact_runs WHERE document_id = ? ORDER BY started_at DESC LIMIT 1",
            (document_id,),
        ).fetchone()
        return FactRun(**{c: _dec(c, r[c]) for c in _RUN_COLS}) if r else None  # type: ignore[arg-type]

    def add(self, f: Fact) -> None:
        self._c.execute(
            f"INSERT INTO facts ({', '.join(_FACT_COLS)}) VALUES ({','.join('?' * len(_FACT_COLS))})",
            [_enc(c, getattr(f, c)) for c in _FACT_COLS],
        )

    def update(self, f: Fact) -> None:
        cols = [c for c in _FACT_COLS if c != "id"]
        self._c.execute(
            f"UPDATE facts SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
            [*(_enc(c, getattr(f, c)) for c in cols), f.id],
        )

    def get(self, fact_id: str) -> Fact | None:
        r = self._c.execute("SELECT * FROM facts WHERE id = ?", (fact_id,)).fetchone()
        return Fact(**{c: _dec(c, r[c]) for c in _FACT_COLS}) if r else None  # type: ignore[arg-type]

    def find(
        self, document_id: str | None = None, kind: str | None = None, status: str | None = None
    ) -> list[Fact]:
        where, args = [], []
        for col, val in (("document_id", document_id), ("kind", kind), ("status", status)):
            if val is not None:
                where.append(f"{col} = ?")
                args.append(val)
        sql = "SELECT * FROM facts" + (f" WHERE {' AND '.join(where)}" if where else "")
        rows = self._c.execute(sql + " ORDER BY page, created_at", args)
        return [Fact(**{c: _dec(c, r[c]) for c in _FACT_COLS}) for r in rows]  # type: ignore[arg-type]

    def delete_proposed(self, document_id: str) -> int:
        cur = self._c.execute(
            "DELETE FROM facts WHERE document_id = ? AND status = 'proposed'", (document_id,)
        )
        return cur.rowcount
