"""SQLite repositories for Phase 2/3: settings, sprints, weekly plans, meetings."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from ppos.domain.meetings import Attendance, Meeting, MeetingKind, MeetingSeries, Person, Topic
from ppos.domain.planning import ScopeEvent, Sprint, SprintStatus, WeeklyObjective, WeeklyPlan
from ppos.shared.clock import new_id


def _ts(v: datetime | None) -> str | None:
    return v.astimezone(timezone.utc).isoformat() if v else None


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def _req(v: str | None) -> datetime:
    d = _dt(v)
    assert d is not None
    return d


class SqliteSettingsRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def all(self) -> dict[str, Any]:
        return {
            r["key"]: json.loads(r["value"])
            for r in self._c.execute("SELECT key, value FROM workspace_settings")
        }

    def set_many(self, values: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for key, value in values.items():
            self._c.execute(
                "INSERT INTO workspace_settings (key, value, updated_at) VALUES (?,?,?)"
                " ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, json.dumps(value), now),
            )


class SqliteSprintRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _from(r: sqlite3.Row) -> Sprint:
        return Sprint(
            id=r["id"],
            name=r["name"],
            goal=r["goal"],
            start_date=date.fromisoformat(r["start_date"]),
            end_date=date.fromisoformat(r["end_date"]),
            status=SprintStatus(r["status"]),
            review_summary=r["review_summary"],
            review_lessons=r["review_lessons"],
            created_at=_req(r["created_at"]),
            updated_at=_req(r["updated_at"]),
            completed_at=_dt(r["completed_at"]),
        )

    def add(self, s: Sprint) -> None:
        self._c.execute(
            "INSERT INTO sprints (id, name, goal, start_date, end_date, status, review_summary,"
            " review_lessons, created_at, updated_at, completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                s.id,
                s.name,
                s.goal,
                s.start_date.isoformat(),
                s.end_date.isoformat(),
                s.status.value,
                s.review_summary,
                s.review_lessons,
                _ts(s.created_at),
                _ts(s.updated_at),
                _ts(s.completed_at),
            ),
        )

    def update(self, s: Sprint) -> None:
        self._c.execute(
            "UPDATE sprints SET name=?, goal=?, start_date=?, end_date=?, status=?, review_summary=?,"
            " review_lessons=?, updated_at=?, completed_at=? WHERE id=?",
            (
                s.name,
                s.goal,
                s.start_date.isoformat(),
                s.end_date.isoformat(),
                s.status.value,
                s.review_summary,
                s.review_lessons,
                _ts(s.updated_at),
                _ts(s.completed_at),
                s.id,
            ),
        )

    def get(self, sprint_id: str) -> Sprint | None:
        r = self._c.execute("SELECT * FROM sprints WHERE id = ?", (sprint_id,)).fetchone()
        return self._from(r) if r else None

    def find(self) -> list[Sprint]:
        return [
            self._from(r) for r in self._c.execute("SELECT * FROM sprints ORDER BY start_date DESC")
        ]

    def delete(self, sprint_id: str) -> None:
        self._c.execute("DELETE FROM sprints WHERE id = ?", (sprint_id,))

    def add_scope_event(self, ev: ScopeEvent) -> None:
        self._c.execute(
            "INSERT INTO sprint_scope_events (sprint_id, task_id, action, commitment, after_start, at)"
            " VALUES (?,?,?,?,?,?)",
            (ev.sprint_id, ev.task_id, ev.action, ev.commitment, int(ev.after_start), _ts(ev.at)),
        )

    def scope_events(self, sprint_id: str) -> list[ScopeEvent]:
        rows = self._c.execute(
            "SELECT * FROM sprint_scope_events WHERE sprint_id = ? ORDER BY id", (sprint_id,)
        )
        return [
            ScopeEvent(
                r["sprint_id"],
                r["task_id"],
                r["action"],
                r["commitment"],
                bool(r["after_start"]),
                _req(r["at"]),
            )
            for r in rows
        ]


class SqliteWeeklyPlanRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def get(self, week_start: date) -> WeeklyPlan | None:
        r = self._c.execute(
            "SELECT * FROM weekly_plans WHERE week_start = ?", (week_start.isoformat(),)
        ).fetchone()
        if r is None:
            return None
        return WeeklyPlan(
            week_start=week_start,
            objectives=[WeeklyObjective(**o) for o in json.loads(r["objectives"])],
            notes=r["notes"],
            review_wins=r["review_wins"],
            review_lessons=r["review_lessons"],
            review_risks=r["review_risks"],
            review_next_focus=r["review_next_focus"],
            review_completed_at=_dt(r["review_completed_at"]),
            updated_at=_dt(r["updated_at"]),
        )

    def upsert(self, p: WeeklyPlan) -> None:
        self._c.execute(
            "INSERT INTO weekly_plans (week_start, objectives, notes, review_wins, review_lessons,"
            " review_risks, review_next_focus, review_completed_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)"
            " ON CONFLICT (week_start) DO UPDATE SET objectives=excluded.objectives, notes=excluded.notes,"
            " review_wins=excluded.review_wins, review_lessons=excluded.review_lessons,"
            " review_risks=excluded.review_risks, review_next_focus=excluded.review_next_focus,"
            " review_completed_at=excluded.review_completed_at, updated_at=excluded.updated_at",
            (
                p.week_start.isoformat(),
                json.dumps([o.__dict__ for o in p.objectives]),
                p.notes,
                p.review_wins,
                p.review_lessons,
                p.review_risks,
                p.review_next_focus,
                _ts(p.review_completed_at),
                _ts(p.updated_at),
            ),
        )


class _NamedRepository:
    table = ""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def _rows(self) -> list[sqlite3.Row]:
        return self._c.execute(f"SELECT * FROM {self.table} ORDER BY lower(name)").fetchall()

    def _get_or_create(self, name: str) -> tuple[str, str, datetime]:
        clean = " ".join(name.split())
        r = self._c.execute(
            f"SELECT * FROM {self.table} WHERE lower(name) = lower(?)", (clean,)
        ).fetchone()
        if r:
            return r["id"], r["name"], _req(r["created_at"])
        now = datetime.now(timezone.utc)
        pid = new_id()
        self._c.execute(
            f"INSERT INTO {self.table} (id, name, created_at) VALUES (?,?,?)",
            (pid, clean, _ts(now)),
        )
        return pid, clean, now


class SqlitePeopleRepository(_NamedRepository):
    table = "people"

    def get_or_create(self, name: str) -> Person:
        return Person(*self._get_or_create(name))

    def find(self) -> list[Person]:
        return [Person(r["id"], r["name"], _req(r["created_at"])) for r in self._rows()]

    def delete(self, person_id: str) -> None:
        self._c.execute("DELETE FROM people WHERE id = ?", (person_id,))


class SqliteTopicRepository(_NamedRepository):
    table = "topics"

    def get_or_create(self, name: str) -> Topic:
        return Topic(*self._get_or_create(name))

    def find(self) -> list[Topic]:
        return [Topic(r["id"], r["name"], _req(r["created_at"])) for r in self._rows()]


_MEETING_COLS = (
    "id, source, external_key, series_key, kind, title, start_at, end_at, all_day, location, organizer,"
    " cancelled, status, attended_minutes, rating, note, topic_id, created_at, updated_at"
)


class SqliteMeetingRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    def _from(self, r: sqlite3.Row, people: dict[str, list[str]]) -> Meeting:
        return Meeting(
            id=r["id"],
            source=r["source"],
            external_key=r["external_key"],
            series_key=r["series_key"],
            kind=MeetingKind(r["kind"]),
            title=r["title"],
            start_at=_req(r["start_at"]),
            end_at=_req(r["end_at"]),
            all_day=bool(r["all_day"]),
            location=r["location"],
            organizer=r["organizer"],
            cancelled=bool(r["cancelled"]),
            status=Attendance(r["status"]) if r["status"] else None,
            attended_minutes=r["attended_minutes"],
            rating=r["rating"],
            note=r["note"],
            topic_id=r["topic_id"],
            created_at=_req(r["created_at"]),
            updated_at=_req(r["updated_at"]),
            people_ids=people.get(r["id"], []),
        )

    def _people_for(self, ids: list[str]) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for i in range(0, len(ids), 500):
            chunk = ids[i : i + 500]
            q = f"SELECT meeting_id, person_id FROM meeting_people WHERE meeting_id IN ({','.join('?' * len(chunk))})"
            for r in self._c.execute(q, chunk):
                out.setdefault(r[0], []).append(r[1])
        return out

    def add(self, m: Meeting) -> None:
        self._c.execute(
            f"INSERT INTO meetings ({_MEETING_COLS}) VALUES ({','.join('?' * 19)})",
            (
                m.id,
                m.source,
                m.external_key,
                m.series_key,
                m.kind.value,
                m.title,
                _ts(m.start_at),
                _ts(m.end_at),
                int(m.all_day),
                m.location,
                m.organizer,
                int(m.cancelled),
                m.status.value if m.status else None,
                m.attended_minutes,
                m.rating,
                m.note,
                m.topic_id,
                _ts(m.created_at),
                _ts(m.updated_at),
            ),
        )
        self.set_people(m.id, m.people_ids)

    def update(self, m: Meeting) -> None:
        self._c.execute(
            "UPDATE meetings SET kind=?, title=?, start_at=?, end_at=?, all_day=?, location=?, organizer=?,"
            " cancelled=?, status=?, attended_minutes=?, rating=?, note=?, topic_id=?, series_key=?,"
            " updated_at=? WHERE id=?",
            (
                m.kind.value,
                m.title,
                _ts(m.start_at),
                _ts(m.end_at),
                int(m.all_day),
                m.location,
                m.organizer,
                int(m.cancelled),
                m.status.value if m.status else None,
                m.attended_minutes,
                m.rating,
                m.note,
                m.topic_id,
                m.series_key,
                _ts(m.updated_at),
                m.id,
            ),
        )
        self.set_people(m.id, m.people_ids)

    def upsert_imported(self, m: Meeting) -> bool:
        """Insert, or refresh only the imported columns. Returns True if new."""
        r = self._c.execute(
            "SELECT id FROM meetings WHERE external_key = ?", (m.external_key,)
        ).fetchone()
        if r is None:
            self.add(m)
            return True
        self._c.execute(
            "UPDATE meetings SET title=?, start_at=?, end_at=?, all_day=?, location=?, organizer=?,"
            " series_key=?, cancelled=0, updated_at=? WHERE id=?",
            (
                m.title,
                _ts(m.start_at),
                _ts(m.end_at),
                int(m.all_day),
                m.location,
                m.organizer,
                m.series_key,
                _ts(m.updated_at),
                r["id"],
            ),
        )
        return False

    def cancel_missing(self, keep_keys: set[str], start: datetime, end: datetime) -> int:
        rows = self._c.execute(
            "SELECT id, external_key FROM meetings WHERE source = 'ics' AND cancelled = 0"
            " AND start_at >= ? AND start_at < ?",
            (_ts(start), _ts(end)),
        ).fetchall()
        gone = [r["id"] for r in rows if r["external_key"] not in keep_keys]
        for mid in gone:
            self._c.execute("UPDATE meetings SET cancelled = 1 WHERE id = ?", (mid,))
        return len(gone)

    def get(self, meeting_id: str) -> Meeting | None:
        r = self._c.execute(
            f"SELECT {_MEETING_COLS} FROM meetings WHERE id = ?", (meeting_id,)
        ).fetchone()
        return self._from(r, self._people_for([meeting_id])) if r else None

    def find(
        self, start: datetime, end: datetime, include_cancelled: bool = False
    ) -> list[Meeting]:
        sql = f"SELECT {_MEETING_COLS} FROM meetings WHERE start_at >= ? AND start_at < ?"
        if not include_cancelled:
            sql += " AND cancelled = 0"
        rows = self._c.execute(sql + " ORDER BY start_at", (_ts(start), _ts(end))).fetchall()
        people = self._people_for([r["id"] for r in rows])
        return [self._from(r, people) for r in rows]

    def delete(self, meeting_id: str) -> None:
        self._c.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))

    def set_people(self, meeting_id: str, people_ids: list[str]) -> None:
        self._c.execute("DELETE FROM meeting_people WHERE meeting_id = ?", (meeting_id,))
        for pid in dict.fromkeys(people_ids):
            self._c.execute(
                "INSERT INTO meeting_people (meeting_id, person_id) VALUES (?,?)", (meeting_id, pid)
            )

    # --- series -----------------------------------------------------------
    @staticmethod
    def _series_from(r: sqlite3.Row) -> MeetingSeries:
        return MeetingSeries(
            series_key=r["series_key"],
            title=r["title"],
            cadence=r["cadence"],
            default_status=r["default_status"],
            topic_id=r["topic_id"],
            rating=r["rating"],
            notes=r["notes"],
            updated_at=_req(r["updated_at"]),
        )

    def upsert_series(self, key: str, title: str, cadence: str | None) -> None:
        self._c.execute(
            "INSERT INTO meeting_series (series_key, title, cadence, updated_at) VALUES (?,?,?,?)"
            " ON CONFLICT (series_key) DO UPDATE SET title = excluded.title, cadence = excluded.cadence",
            (key, title, cadence, datetime.now(timezone.utc).isoformat()),
        )

    def update_series(self, s: MeetingSeries) -> None:
        self._c.execute(
            "UPDATE meeting_series SET default_status=?, topic_id=?, rating=?, notes=?, updated_at=?"
            " WHERE series_key=?",
            (s.default_status, s.topic_id, s.rating, s.notes, _ts(s.updated_at), s.series_key),
        )

    def series(self) -> dict[str, MeetingSeries]:
        return {
            r["series_key"]: self._series_from(r)
            for r in self._c.execute("SELECT * FROM meeting_series")
        }

    def get_series(self, key: str) -> MeetingSeries | None:
        r = self._c.execute("SELECT * FROM meeting_series WHERE series_key = ?", (key,)).fetchone()
        return self._series_from(r) if r else None

    # --- imports ----------------------------------------------------------
    def record_import(
        self, filename: str, window: tuple[datetime, datetime], events: int, series: int
    ) -> None:
        self._c.execute(
            "INSERT INTO calendar_imports (id, filename, imported_at, window_start, window_end, events, series)"
            " VALUES (?,?,?,?,?,?,?)",
            (
                new_id(),
                filename,
                datetime.now(timezone.utc).isoformat(),
                _ts(window[0]),
                _ts(window[1]),
                events,
                series,
            ),
        )

    def last_import(self) -> dict[str, Any] | None:
        r = self._c.execute(
            "SELECT * FROM calendar_imports ORDER BY imported_at DESC LIMIT 1"
        ).fetchone()
        return dict(r) if r else None
