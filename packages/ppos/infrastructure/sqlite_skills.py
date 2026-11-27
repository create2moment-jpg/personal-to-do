"""SQLite repository for the skills matrix."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ppos.domain.skills import Rating, Skill


def _ts(v: datetime) -> str:
    return v.astimezone(timezone.utc).isoformat()


def _skill(r: sqlite3.Row) -> Skill:
    return Skill(
        id=r["id"],
        name=r["name"],
        category=r["category"],
        description=r["description"],
        target_level=r["target_level"],
        position=r["position"],
        created_at=datetime.fromisoformat(r["created_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    )


class SqliteSkillRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def add(self, s: Skill) -> None:
        self._c.execute(
            "INSERT INTO skills (id, name, category, description, target_level, position,"
            " created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (s.id, s.name, s.category, s.description, s.target_level, s.position,
             _ts(s.created_at), _ts(s.updated_at)),
        )  # fmt: skip

    def update(self, s: Skill) -> None:
        self._c.execute(
            "UPDATE skills SET name=?, category=?, description=?, target_level=?, position=?,"
            " updated_at=? WHERE id=?",
            (
                s.name,
                s.category,
                s.description,
                s.target_level,
                s.position,
                _ts(s.updated_at),
                s.id,
            ),
        )

    def get(self, skill_id: str) -> Skill | None:
        r = self._c.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
        return _skill(r) if r else None

    def by_name(self, name: str) -> Skill | None:
        r = self._c.execute("SELECT * FROM skills WHERE lower(name) = lower(?)", (name,)).fetchone()
        return _skill(r) if r else None

    def all(self) -> list[Skill]:
        return [
            _skill(r)
            for r in self._c.execute("SELECT * FROM skills ORDER BY category, position, name")
        ]

    def delete(self, skill_id: str) -> None:
        self._c.execute("DELETE FROM skills WHERE id = ?", (skill_id,))

    def max_position(self) -> float:
        return float(self._c.execute("SELECT COALESCE(MAX(position), 0) FROM skills").fetchone()[0])

    def add_rating(self, r: Rating) -> None:
        self._c.execute(
            "INSERT INTO skill_ratings (id, skill_id, level, note, rated_at) VALUES (?,?,?,?,?)",
            (r.id, r.skill_id, r.level, r.note, _ts(r.rated_at)),
        )

    def ratings(self) -> list[Rating]:
        rows = self._c.execute("SELECT * FROM skill_ratings ORDER BY rated_at, rowid")
        return [
            Rating(
                r["id"], r["skill_id"], r["level"], datetime.fromisoformat(r["rated_at"]), r["note"]
            )
            for r in rows
        ]

    def link_evidence(self, skill_id: str, fact_id: str, origin: str, at: datetime) -> bool:
        cur = self._c.execute(
            "INSERT OR IGNORE INTO skill_evidence (skill_id, fact_id, origin, created_at)"
            " VALUES (?,?,?,?)",
            (skill_id, fact_id, origin, _ts(at)),
        )
        return cur.rowcount > 0

    def unlink_evidence(self, skill_id: str, fact_id: str) -> int:
        return self._c.execute(
            "DELETE FROM skill_evidence WHERE skill_id = ? AND fact_id = ?", (skill_id, fact_id)
        ).rowcount

    def evidence(self) -> list[tuple[str, str, str]]:
        """(skill_id, fact_id, origin)."""
        rows = self._c.execute(
            "SELECT skill_id, fact_id, origin FROM skill_evidence ORDER BY created_at"
        )
        return [(r[0], r[1], r[2]) for r in rows]
