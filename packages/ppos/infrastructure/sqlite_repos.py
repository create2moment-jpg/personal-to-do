"""SQLite implementations of the application ports."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ppos.application.ports import Actor, NoteQuery, SearchHit, TaskQuery
from ppos.domain.daily import DailyPlan, DailyReview
from ppos.domain.notes import EntityType, Link, Note, NoteKind, NoteVersion
from ppos.domain.projects import Project, ProjectStatus
from ppos.domain.tasks import Priority, Task, TaskStatus
from ppos.infrastructure.db import connect
from ppos.infrastructure.sqlite_book import SqliteBookRepository
from ppos.infrastructure.sqlite_documents import SqliteDocumentRepository
from ppos.infrastructure.sqlite_facts import SqliteFactRepository
from ppos.infrastructure.sqlite_planning import (
    SqliteMeetingRepository,
    SqlitePeopleRepository,
    SqliteSettingsRepository,
    SqliteSprintRepository,
    SqliteTopicRepository,
    SqliteWeeklyPlanRepository,
)


def _ts(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _ds(value: date | None) -> str | None:
    return value.isoformat() if value else None


_TASK_COLS = (
    "id, title, description, notes, status, priority, estimate_minutes, actual_minutes, "
    "project_id, area, parent_id, tags, due_date, scheduled_date, recurrence, position, "
    "created_at, updated_at, completed_at, sprint_id, commitment"
)


def _task_row(t: Task) -> tuple[Any, ...]:
    return (
        t.id, t.title, t.description, t.notes, t.status.value, int(t.priority),
        t.estimate_minutes, t.actual_minutes, t.project_id, t.area, t.parent_id,
        json.dumps(t.tags), _ds(t.due_date), _ds(t.scheduled_date), t.recurrence,
        t.position, _ts(t.created_at), _ts(t.updated_at), _ts(t.completed_at),
        t.sprint_id, t.commitment,
    )  # fmt: skip


def _task_from(row: sqlite3.Row) -> Task:
    created = _dt(row["created_at"])
    updated = _dt(row["updated_at"])
    assert created is not None and updated is not None
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        notes=row["notes"],
        status=TaskStatus(row["status"]),
        priority=Priority(row["priority"]),
        estimate_minutes=row["estimate_minutes"],
        actual_minutes=row["actual_minutes"],
        project_id=row["project_id"],
        area=row["area"],
        parent_id=row["parent_id"],
        tags=json.loads(row["tags"]),
        due_date=_d(row["due_date"]),
        scheduled_date=_d(row["scheduled_date"]),
        recurrence=row["recurrence"],
        position=row["position"],
        created_at=created,
        updated_at=updated,
        completed_at=_dt(row["completed_at"]),
        sprint_id=row["sprint_id"],
        commitment=row["commitment"],
    )


class SqliteTaskRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def add(self, task: Task) -> None:
        placeholders = ",".join("?" * 21)
        self._c.execute(
            f"INSERT INTO tasks ({_TASK_COLS}) VALUES ({placeholders})", _task_row(task)
        )

    def get(self, task_id: str) -> Task | None:
        row = self._c.execute(f"SELECT {_TASK_COLS} FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _task_from(row) if row else None

    def update(self, task: Task) -> None:
        cols = [c.strip() for c in _TASK_COLS.split(",")][1:]
        assignments = ", ".join(f"{c} = ?" for c in cols)
        values = _task_row(task)
        self._c.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", (*values[1:], task.id))

    def delete(self, task_id: str) -> None:
        self._c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def find(self, query: TaskQuery) -> list[Task]:
        where: list[str] = []
        args: list[Any] = []
        if query.statuses:
            where.append(f"status IN ({','.join('?' * len(query.statuses))})")
            args.extend(s.value for s in query.statuses)
        if query.scheduled_date is not None:
            where.append("scheduled_date = ?")
            args.append(query.scheduled_date.isoformat())
        if query.scheduled_before is not None:
            where.append("scheduled_date < ?")
            args.append(query.scheduled_before.isoformat())
        if query.unscheduled_only:
            where.append("scheduled_date IS NULL")
        if query.project_id is not None:
            where.append("project_id = ?")
            args.append(query.project_id)
        if query.parent_id is not None:
            where.append("parent_id = ?")
            args.append(query.parent_id)
        elif query.top_level_only:
            where.append("parent_id IS NULL")
        if query.sprint_id is not None:
            where.append("sprint_id = ?")
            args.append(query.sprint_id)
        if query.scheduled_from is not None:
            where.append("scheduled_date >= ?")
            args.append(query.scheduled_from.isoformat())
        if query.scheduled_to is not None:
            where.append("scheduled_date <= ?")
            args.append(query.scheduled_to.isoformat())
        if query.completed_from is not None:
            where.append("completed_at >= ?")
            args.append(_ts(query.completed_from))
        if query.completed_to is not None:
            where.append("completed_at < ?")
            args.append(_ts(query.completed_to))
        if query.tag is not None:
            where.append("EXISTS (SELECT 1 FROM json_each(tasks.tags) WHERE value = ?)")
            args.append(query.tag.lower())
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = (
            f"SELECT {_TASK_COLS} FROM tasks {clause} "
            "ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 "
            "WHEN 'blocked' THEN 2 WHEN 'backlog' THEN 3 ELSE 4 END, "
            "position, priority, created_at LIMIT ? OFFSET ?"
        )
        rows = self._c.execute(sql, (*args, query.limit, query.offset)).fetchall()
        return [_task_from(r) for r in rows]

    def dependencies(self) -> dict[str, set[str]]:
        edges: dict[str, set[str]] = {}
        for task_id, dep in self._c.execute("SELECT task_id, depends_on FROM task_dependencies"):
            edges.setdefault(task_id, set()).add(dep)
        return edges

    def dependencies_of(self, task_id: str) -> list[str]:
        rows = self._c.execute(
            "SELECT depends_on FROM task_dependencies WHERE task_id = ?", (task_id,)
        ).fetchall()
        return [r[0] for r in rows]

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        self._c.execute(
            "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on) VALUES (?, ?)",
            (task_id, depends_on),
        )

    def remove_dependency(self, task_id: str, depends_on: str) -> None:
        self._c.execute(
            "DELETE FROM task_dependencies WHERE task_id = ? AND depends_on = ?",
            (task_id, depends_on),
        )

    def max_position(self, status: TaskStatus, day: date | None) -> float:
        row = self._c.execute(
            "SELECT max(position) FROM tasks WHERE status = ? AND scheduled_date IS ?",
            (status.value, _ds(day)),
        ).fetchone()
        return float(row[0] or 0)


class SqliteProjectRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _from(row: sqlite3.Row) -> Project:
        created, updated = _dt(row["created_at"]), _dt(row["updated_at"])
        assert created is not None and updated is not None
        return Project(
            id=row["id"], name=row["name"], description=row["description"], area=row["area"],
            status=ProjectStatus(row["status"]), color=row["color"],
            created_at=created, updated_at=updated,
        )  # fmt: skip

    def add(self, project: Project) -> None:
        self._c.execute(
            "INSERT INTO projects (id, name, description, area, status, color, created_at,"
            " updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (project.id, project.name, project.description, project.area, project.status.value,
             project.color, _ts(project.created_at), _ts(project.updated_at)),
        )  # fmt: skip

    def get(self, project_id: str) -> Project | None:
        row = self._c.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._from(row) if row else None

    def find_by_name(self, name: str) -> Project | None:
        row = self._c.execute(
            "SELECT * FROM projects WHERE lower(name) = lower(?)", (" ".join(name.split()),)
        ).fetchone()
        return self._from(row) if row else None

    def update(self, project: Project) -> None:
        self._c.execute(
            "UPDATE projects SET name=?, description=?, area=?, status=?, color=?, updated_at=?"
            " WHERE id=?",
            (project.name, project.description, project.area, project.status.value,
             project.color, _ts(project.updated_at), project.id),
        )  # fmt: skip

    def find(self, include_archived: bool = False) -> list[Project]:
        sql = "SELECT * FROM projects"
        if not include_archived:
            sql += " WHERE status <> 'archived'"
        return [self._from(r) for r in self._c.execute(sql + " ORDER BY lower(name)")]


class SqliteNoteRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _from(row: sqlite3.Row) -> Note:
        created, updated = _dt(row["created_at"]), _dt(row["updated_at"])
        assert created is not None and updated is not None
        return Note(
            id=row["id"], title=row["title"], body=row["body"], kind=NoteKind(row["kind"]),
            project_id=row["project_id"], note_date=_d(row["note_date"]),
            tags=json.loads(row["tags"]), version=row["version"],
            last_snapshot_at=_dt(row["last_snapshot_at"]), created_at=created, updated_at=updated,
        )  # fmt: skip

    def add(self, note: Note) -> None:
        self._c.execute(
            "INSERT INTO notes (id, title, body, kind, project_id, note_date, tags, version,"
            " last_snapshot_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (note.id, note.title, note.body, note.kind.value, note.project_id,
             _ds(note.note_date), json.dumps(note.tags), note.version,
             _ts(note.last_snapshot_at), _ts(note.created_at), _ts(note.updated_at)),
        )  # fmt: skip

    def get(self, note_id: str) -> Note | None:
        row = self._c.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return self._from(row) if row else None

    def update(self, note: Note) -> None:
        self._c.execute(
            "UPDATE notes SET title=?, body=?, kind=?, project_id=?, note_date=?, tags=?,"
            " version=?, last_snapshot_at=?, updated_at=? WHERE id=?",
            (note.title, note.body, note.kind.value, note.project_id, _ds(note.note_date),
             json.dumps(note.tags), note.version, _ts(note.last_snapshot_at),
             _ts(note.updated_at), note.id),
        )  # fmt: skip

    def delete(self, note_id: str) -> None:
        self._c.execute("DELETE FROM notes WHERE id = ?", (note_id,))

    def find(self, query: NoteQuery) -> list[Note]:
        where: list[str] = []
        args: list[Any] = []
        if query.kind is not None:
            where.append("kind = ?")
            args.append(query.kind.value)
        if query.project_id is not None:
            where.append("project_id = ?")
            args.append(query.project_id)
        if query.note_date is not None:
            where.append("note_date = ?")
            args.append(query.note_date.isoformat())
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        rows = self._c.execute(
            f"SELECT * FROM notes {clause} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (*args, query.limit, query.offset),
        ).fetchall()
        return [self._from(r) for r in rows]

    def add_version(self, version: NoteVersion) -> None:
        self._c.execute(
            "INSERT INTO note_versions (note_id, version, title, body, created_at)"
            " VALUES (?,?,?,?,?) ON CONFLICT (note_id, version) DO UPDATE SET"
            " title = excluded.title, body = excluded.body, created_at = excluded.created_at",
            (version.note_id, version.version, version.title, version.body,
             _ts(version.created_at)),
        )  # fmt: skip

    def versions(self, note_id: str) -> list[NoteVersion]:
        rows = self._c.execute(
            "SELECT * FROM note_versions WHERE note_id = ? ORDER BY version DESC", (note_id,)
        ).fetchall()
        return [self._version_from(r) for r in rows]

    def get_version(self, note_id: str, version: int) -> NoteVersion | None:
        row = self._c.execute(
            "SELECT * FROM note_versions WHERE note_id = ? AND version = ?", (note_id, version)
        ).fetchone()
        return self._version_from(row) if row else None

    @staticmethod
    def _version_from(row: sqlite3.Row) -> NoteVersion:
        created = _dt(row["created_at"])
        assert created is not None
        return NoteVersion(row["note_id"], row["version"], row["title"], row["body"], created)

    def find_daily_journal(self, day: date) -> Note | None:
        row = self._c.execute(
            "SELECT * FROM notes WHERE kind = 'journal' AND note_date = ?", (day.isoformat(),)
        ).fetchone()
        return self._from(row) if row else None


class SqliteDailyPlanRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def get(self, day: date) -> DailyPlan | None:
        row = self._c.execute(
            "SELECT * FROM daily_plans WHERE day = ?", (day.isoformat(),)
        ).fetchone()
        if row is None:
            return None
        return DailyPlan(
            day=day,
            capacity_minutes=row["capacity_minutes"],
            objective=row["objective"],
            top_priority_ids=json.loads(row["top_priority_ids"]),
            review=DailyReview(
                unfinished=row["review_unfinished"],
                blockers=row["review_blockers"],
                learning=row["review_learning"],
                wins=row["review_wins"],
                tomorrow_first_task=row["review_tomorrow"],
                completed_at=_dt(row["review_completed_at"]),
            ),
            updated_at=_dt(row["updated_at"]),
            capacity_mode=row["capacity_mode"],
        )

    def upsert(self, plan: DailyPlan) -> None:
        r = plan.review
        self._c.execute(
            "INSERT INTO daily_plans (day, capacity_minutes, objective, top_priority_ids,"
            " review_unfinished, review_blockers, review_learning, review_wins, review_tomorrow,"
            " review_completed_at, updated_at, capacity_mode) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT (day) DO UPDATE SET capacity_minutes=excluded.capacity_minutes,"
            " objective=excluded.objective, top_priority_ids=excluded.top_priority_ids,"
            " review_unfinished=excluded.review_unfinished,"
            " review_blockers=excluded.review_blockers,"
            " review_learning=excluded.review_learning, review_wins=excluded.review_wins,"
            " review_tomorrow=excluded.review_tomorrow,"
            " review_completed_at=excluded.review_completed_at, updated_at=excluded.updated_at,"
            " capacity_mode=excluded.capacity_mode",
            (plan.day.isoformat(), plan.capacity_minutes, plan.objective,
             json.dumps(plan.top_priority_ids), r.unfinished, r.blockers, r.learning, r.wins,
             r.tomorrow_first_task, _ts(r.completed_at), _ts(plan.updated_at),
             plan.capacity_mode),
        )  # fmt: skip


class SqliteLinkRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def add(self, link: Link) -> None:
        self._c.execute(
            "INSERT INTO links (id, source_type, source_id, target_type, target_id, created_at)"
            " VALUES (?,?,?,?,?,?)",
            (link.id, link.source_type.value, link.source_id, link.target_type.value,
             link.target_id, _ts(link.created_at)),
        )  # fmt: skip

    def delete(self, link_id: str) -> None:
        self._c.execute("DELETE FROM links WHERE id = ?", (link_id,))

    def for_entity(self, entity_type: EntityType, entity_id: str) -> list[Link]:
        rows = self._c.execute(
            "SELECT * FROM links WHERE (source_type = ? AND source_id = ?)"
            " OR (target_type = ? AND target_id = ?) ORDER BY created_at",
            (entity_type.value, entity_id, entity_type.value, entity_id),
        ).fetchall()
        out: list[Link] = []
        for r in rows:
            created = _dt(r["created_at"])
            assert created is not None
            out.append(
                Link(r["id"], EntityType(r["source_type"]), r["source_id"],
                     EntityType(r["target_type"]), r["target_id"], created)
            )  # fmt: skip
        return out

    def delete_for_entity(self, entity_type: EntityType, entity_id: str) -> None:
        self._c.execute(
            "DELETE FROM links WHERE (source_type = ? AND source_id = ?)"
            " OR (target_type = ? AND target_id = ?)",
            (entity_type.value, entity_id, entity_type.value, entity_id),
        )


_FTS_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def to_fts_query(text: str) -> str:
    """Turn free user text into a safe FTS5 prefix query (no operator injection)."""
    tokens = _FTS_TOKEN_RE.findall(text)
    return " ".join(f'"{t}"*' for t in tokens[:12])


class SqliteSearchIndex:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        fts = to_fts_query(query)
        if not fts:
            return []
        rows = self._c.execute(
            "SELECT entity_type, entity_id, title,"
            " snippet(search_index, -1, '[', ']', '…', 12) AS snip,"
            " bm25(search_index, 0, 0, 5.0, 1.0) AS score"
            " FROM search_index WHERE search_index MATCH ? ORDER BY score LIMIT ?",
            (fts, limit),
        ).fetchall()
        return [
            SearchHit(
                EntityType(r["entity_type"]), r["entity_id"], r["title"], r["snip"], -r["score"]
            )
            for r in rows
        ]


class SqliteAuditLog:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def record(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor: Actor = "user",
        details: dict[str, Any] | None = None,
    ) -> None:
        self._c.execute(
            "INSERT INTO audit_log (at, actor, entity_type, entity_id, action, details)"
            " VALUES (?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), actor, entity_type, entity_id, action,
             json.dumps(details or {}, default=str)),
        )  # fmt: skip


class SqliteUnitOfWork:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.tasks = SqliteTaskRepository(conn)
        self.projects = SqliteProjectRepository(conn)
        self.notes = SqliteNoteRepository(conn)
        self.days = SqliteDailyPlanRepository(conn)
        self.links = SqliteLinkRepository(conn)
        self.search = SqliteSearchIndex(conn)
        self.audit = SqliteAuditLog(conn)
        self.settings = SqliteSettingsRepository(conn)
        self.sprints = SqliteSprintRepository(conn)
        self.weeks = SqliteWeeklyPlanRepository(conn)
        self.people = SqlitePeopleRepository(conn)
        self.topics = SqliteTopicRepository(conn)
        self.meetings = SqliteMeetingRepository(conn)
        self.books = SqliteBookRepository(conn)
        self.documents = SqliteDocumentRepository(conn)
        self.facts = SqliteFactRepository(conn)

    def commit(self) -> None:
        if self.conn.in_transaction:
            self.conn.execute("COMMIT")
        # Keep later work in this unit transactional and serialised too.
        self.conn.execute("BEGIN IMMEDIATE")

    def rollback(self) -> None:
        if self.conn.in_transaction:
            self.conn.execute("ROLLBACK")


class SqliteUnitOfWorkFactory:
    """One short-lived connection per unit of work (safe under the threadpool).

    Units start with ``BEGIN IMMEDIATE``: a deferred transaction that reads and
    then writes cannot be upgraded while another writer is active, and SQLite
    fails that immediately with "database is locked" (the busy timeout does not
    apply to lock upgrades). Taking the write lock up front makes concurrent
    writers queue on the busy timeout instead. WAL keeps reads from other
    connections unblocked.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = db_path

    @contextmanager
    def __call__(self) -> Iterator[SqliteUnitOfWork]:
        conn = connect(self._db_path)
        uow = SqliteUnitOfWork(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield uow
        finally:
            uow.rollback()  # anything not explicitly committed is discarded
            conn.close()
