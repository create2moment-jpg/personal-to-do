"""Storage for reusable checklists."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from ppos.domain.checklists import Checklist


class SqliteChecklistRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _row(r: sqlite3.Row) -> Checklist:
        return Checklist(
            r["id"], r["name"], [ln for ln in r["lines"].split("\n") if ln], r["uses"],
            datetime.fromisoformat(r["created_at"]), datetime.fromisoformat(r["updated_at"]),
        )  # fmt: skip

    def all(self) -> list[Checklist]:
        return [
            self._row(r)
            for r in self._c.execute("SELECT * FROM checklists ORDER BY uses DESC, name")
        ]

    def get(self, checklist_id: str) -> Checklist | None:
        r = self._c.execute("SELECT * FROM checklists WHERE id = ?", (checklist_id,)).fetchone()
        return self._row(r) if r else None

    def save(self, c: Checklist) -> None:
        self._c.execute(
            "INSERT INTO checklists (id, name, lines, uses, created_at, updated_at) VALUES (?,?,?,?,?,?)"
            " ON CONFLICT (id) DO UPDATE SET name = excluded.name, lines = excluded.lines,"
            " uses = excluded.uses, updated_at = excluded.updated_at",
            (
                c.id,
                c.name,
                "\n".join(c.lines),
                c.uses,
                c.created_at.isoformat(),
                c.updated_at.isoformat(),
            ),
        )

    def delete(self, checklist_id: str) -> bool:
        return self._c.execute("DELETE FROM checklists WHERE id = ?", (checklist_id,)).rowcount > 0
