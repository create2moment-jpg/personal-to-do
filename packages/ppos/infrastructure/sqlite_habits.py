"""Storage for habits and the days they were done."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime

from ppos.domain.habits import Habit


class SqliteHabitRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _row(r: sqlite3.Row) -> Habit:
        return Habit(
            r["id"], r["name"], datetime.fromisoformat(r["created_at"]), r["emoji"], r["cadence"],
            bool(r["archived"]), r["position"],
        )  # fmt: skip

    def all(self, include_archived: bool = False) -> list[Habit]:
        sql = "SELECT * FROM habits" + ("" if include_archived else " WHERE archived = 0")
        return [self._row(r) for r in self._c.execute(sql + " ORDER BY position, created_at")]

    def get(self, habit_id: str) -> Habit | None:
        r = self._c.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
        return self._row(r) if r else None

    def save(self, h: Habit) -> None:
        self._c.execute(
            "INSERT INTO habits (id, name, emoji, cadence, archived, position, created_at)"
            " VALUES (?,?,?,?,?,?,?) ON CONFLICT (id) DO UPDATE SET name = excluded.name,"
            " emoji = excluded.emoji, cadence = excluded.cadence, archived = excluded.archived,"
            " position = excluded.position",
            (
                h.id,
                h.name,
                h.emoji,
                h.cadence,
                int(h.archived),
                h.position,
                h.created_at.isoformat(),
            ),
        )

    def delete(self, habit_id: str) -> bool:
        return self._c.execute("DELETE FROM habits WHERE id = ?", (habit_id,)).rowcount > 0

    def set_done(self, habit_id: str, day: date, done: bool) -> None:
        if done:
            self._c.execute(
                "INSERT OR IGNORE INTO habit_checks (habit_id, day) VALUES (?, ?)",
                (habit_id, day.isoformat()),
            )
        else:
            self._c.execute(
                "DELETE FROM habit_checks WHERE habit_id = ? AND day = ?",
                (habit_id, day.isoformat()),
            )

    def done_days(self, since: date) -> dict[str, set[date]]:
        out: dict[str, set[date]] = {}
        for r in self._c.execute(
            "SELECT habit_id, day FROM habit_checks WHERE day >= ?", (since.isoformat(),)
        ):
            out.setdefault(r[0], set()).add(date.fromisoformat(r[1]))
        return out
