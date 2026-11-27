"""SQLite repository for goals and their links."""

from __future__ import annotations

import sqlite3
from dataclasses import fields
from datetime import datetime, timezone
from typing import Any

from ppos.domain.goals import Goal

_COLS = [f.name for f in fields(Goal)]
_TS = {"created_at", "updated_at", "achieved_at"}


def _enc(name: str, v: object) -> object:
    if name in _TS and isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    return v


def _goal(r: sqlite3.Row) -> Goal:
    values: dict[str, Any] = {
        c: (datetime.fromisoformat(r[c]) if c in _TS and r[c] else r[c]) for c in _COLS
    }
    return Goal(**values)


class SqliteGoalRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def add(self, g: Goal) -> None:
        self._c.execute(
            f"INSERT INTO goals ({', '.join(_COLS)}) VALUES ({','.join('?' * len(_COLS))})",
            [_enc(c, getattr(g, c)) for c in _COLS],
        )

    def update(self, g: Goal) -> None:
        cols = [c for c in _COLS if c != "id"]
        self._c.execute(
            f"UPDATE goals SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
            [*(_enc(c, getattr(g, c)) for c in cols), g.id],
        )

    def get(self, goal_id: str) -> Goal | None:
        r = self._c.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return _goal(r) if r else None

    def delete(self, goal_id: str) -> None:
        self._c.execute("DELETE FROM goals WHERE id = ?", (goal_id,))

    def find(self, year: int | None = None) -> list[Goal]:
        sql, args = "SELECT * FROM goals", []
        if year is not None:
            sql += " WHERE period = ? OR period LIKE ?"
            args = [str(year), f"{year}-%"]
        rows = self._c.execute(sql + " ORDER BY position, created_at", args)
        return [_goal(r) for r in rows]

    def max_position(self) -> float:
        return float(self._c.execute("SELECT COALESCE(MAX(position), 0) FROM goals").fetchone()[0])

    # --- links -------------------------------------------------------------
    def link(self, table: str, goal_id: str, other_id: str) -> None:
        col = _LINKS[table]
        self._c.execute(
            f"INSERT OR IGNORE INTO {table} (goal_id, {col}) VALUES (?, ?)", (goal_id, other_id)
        )

    def unlink(self, table: str, goal_id: str, other_id: str) -> int:
        col = _LINKS[table]
        cur = self._c.execute(
            f"DELETE FROM {table} WHERE goal_id = ? AND {col} = ?", (goal_id, other_id)
        )
        return cur.rowcount

    def links(self, table: str) -> list[tuple[str, str]]:
        col = _LINKS[table]
        return [(r[0], r[1]) for r in self._c.execute(f"SELECT goal_id, {col} FROM {table}")]

    def task_states(self) -> list[tuple[str | None, str | None, str]]:
        """(goal_id, project_id, status) of every top-level task linked to a goal or project."""
        rows = self._c.execute(
            "SELECT goal_id, project_id, status FROM tasks WHERE parent_id IS NULL"
            " AND (goal_id IS NOT NULL OR project_id IN (SELECT project_id FROM goal_projects))"
        )
        return [(r[0], r[1], r[2]) for r in rows]


_LINKS = {  # whitelist of link tables
    "goal_expectations": "expectation_id",
    "goal_projects": "project_id",
    "goal_skills": "skill_id",
}
