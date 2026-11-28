"""People (B-027): everything you share with one person, and 1:1 prep."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Any

from ppos.application.notes import NoteService
from ppos.application.ports import NoteQuery, TaskQuery, UnitOfWork, UnitOfWorkFactory
from ppos.domain.meetings import Attendance, Meeting, MeetingSeries, Person
from ppos.domain.notes import Note, NoteKind
from ppos.domain.tasks import TaskStatus
from ppos.domain.wikilinks import parse_links, snippet, title_key
from ppos.shared.clock import Clock
from ppos.shared.errors import NotFoundError, ValidationError

HISTORY_DAYS = 365
UPCOMING_DAYS = 30


@dataclass
class PersonSummary:
    person: Person
    role: str
    meetings_90d: int = 0
    minutes_90d: int = 0
    last_met: datetime | None = None
    next_meeting: datetime | None = None
    follow_ups: int = 0


@dataclass
class PersonDetail:
    summary: PersonSummary
    talking_points: str
    minutes_30d: int
    avg_rating: float | None
    meetings: list[dict[str, Any]] = field(default_factory=list)  # newest first, incl. upcoming
    follow_ups: list[dict[str, Any]] = field(default_factory=list)
    notes: list[dict[str, Any]] = field(default_factory=list)


def _mentions(text: str, name: str) -> bool:
    words = [re.escape(w) for w in name.split()]
    return (
        bool(words)
        and re.search(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", text, re.I) is not None
    )


def _minutes(m: Meeting) -> int:
    if m.attended_minutes is not None:
        return m.attended_minutes
    return max(0, int((m.end_at - m.start_at).total_seconds() // 60))


class PeopleService:
    def __init__(
        self, uow: UnitOfWorkFactory, clock: Clock, notes: NoteService, tz: Callable[[], tzinfo]
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._notes = notes
        self._tz = tz

    def _window(self, uow: UnitOfWork) -> tuple[list[Meeting], dict[str, MeetingSeries]]:
        now = self._clock.now().astimezone(timezone.utc)
        found = uow.meetings.find(
            now - timedelta(days=HISTORY_DAYS), now + timedelta(days=UPCOMING_DAYS)
        )
        return [m for m in found if not m.cancelled], uow.meetings.series()

    def _attended(self, m: Meeting, series: dict[str, MeetingSeries]) -> bool:
        return m.effective_status(series.get(m.series_key or "")) != Attendance.SKIPPED

    def _summary(
        self,
        uow: UnitOfWork,
        p: Person,
        meetings: list[Meeting],
        series: dict[str, MeetingSeries],
        open_tasks: list[Any],
    ) -> PersonSummary:
        now = self._clock.now()
        mine = [m for m in meetings if p.id in m.people_ids and self._attended(m, series)]
        past = [m for m in mine if m.start_at <= now]
        recent = [m for m in past if m.start_at >= now - timedelta(days=90)]
        upcoming = sorted((m for m in mine if m.start_at > now), key=lambda m: m.start_at)
        role, _ = uow.people.profile(p.id)
        return PersonSummary(
            p,
            role,
            meetings_90d=len(recent),
            minutes_90d=sum(_minutes(m) for m in recent),
            last_met=max((m.start_at for m in past), default=None),
            next_meeting=upcoming[0].start_at if upcoming else None,
            follow_ups=sum(
                1 for t in open_tasks if _mentions(f"{t.title} {t.description}", p.name)
            ),
        )

    def _open_tasks(self, uow: UnitOfWork) -> list[Any]:
        statuses = (
            TaskStatus.BACKLOG,
            TaskStatus.PLANNED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.BLOCKED,
        )
        return uow.tasks.find(TaskQuery(statuses=statuses, limit=5000))

    def all(self) -> list[PersonSummary]:
        with self._uow() as uow:
            meetings, series = self._window(uow)
            open_tasks = self._open_tasks(uow)
            out = [self._summary(uow, p, meetings, series, open_tasks) for p in uow.people.find()]
        far = datetime.min.replace(tzinfo=timezone.utc)
        out.sort(key=lambda s: s.last_met or s.next_meeting or far, reverse=True)
        return out

    def add(self, name: str, role: str = "") -> PersonSummary:
        name = " ".join(name.split())
        if not name or len(name) > 120:
            raise ValidationError("a name of 1–120 characters, please")
        with self._uow() as uow:
            p = uow.people.get_or_create(name)
            if role:
                _, points = uow.people.profile(p.id)
                uow.people.set_profile(
                    p.id, role.strip()[:120], points, self._clock.now().isoformat()
                )
            uow.commit()
        return next(s for s in self.all() if s.person.id == p.id)

    def update(self, person_id: str, role: str | None, talking_points: str | None) -> None:
        with self._uow() as uow:
            if uow.people.get(person_id) is None:
                raise NotFoundError("person", person_id)
            cur_role, cur_points = uow.people.profile(person_id)
            new_points = cur_points if talking_points is None else talking_points
            if len(new_points) > 20_000:
                raise ValidationError("talking points are too long")
            uow.people.set_profile(
                person_id,
                cur_role if role is None else role.strip()[:120],
                new_points,
                self._clock.now().isoformat(),
            )
            uow.commit()

    def detail(self, person_id: str) -> PersonDetail:
        tz = self._tz()
        with self._uow() as uow:
            p = uow.people.get(person_id)
            if p is None:
                raise NotFoundError("person", person_id)
            meetings, series = self._window(uow)
            open_tasks = self._open_tasks(uow)
            summary = self._summary(uow, p, meetings, series, open_tasks)
            _, points = uow.people.profile(p.id)
            notes = uow.notes.find(NoteQuery(limit=100_000))
        now = self._clock.now()
        mine = sorted(
            (m for m in meetings if p.id in m.people_ids), key=lambda m: m.start_at, reverse=True
        )
        attended = [m for m in mine if self._attended(m, series) and m.start_at <= now]
        rated = [m.rating for m in attended if m.rating]
        rows = [
            {
                "id": m.id,
                "title": m.title,
                "kind": m.kind.value,
                "start_at": m.start_at.isoformat(),
                "day": m.start_at.astimezone(tz).date().isoformat(),
                "minutes": _minutes(m),
                "rating": m.rating,
                "note": m.note,
                "upcoming": m.start_at > now,
                "skipped": not self._attended(m, series),
            }
            for m in mine[:60]
        ]
        follow = [
            {"id": t.id, "title": t.title, "status": t.status.value, "due_date": t.due_date}
            for t in open_tasks
            if _mentions(f"{t.title} {t.description}", p.name)
        ][:30]
        return PersonDetail(
            summary,
            points,
            minutes_30d=sum(
                _minutes(m) for m in attended if m.start_at >= now - timedelta(days=30)
            ),
            avg_rating=round(sum(rated) / len(rated), 1) if rated else None,
            meetings=rows,
            follow_ups=follow,
            notes=self._note_mentions(notes, p.name),
        )

    @staticmethod
    def _note_mentions(notes: list[Note], name: str) -> list[dict[str, Any]]:
        key = title_key(name)
        words = [re.escape(w) for w in name.split()]
        pattern = re.compile(r"(?<!\w)" + r"\s+".join(words) + r"(?!\w)", re.I)
        out = []
        for n in sorted(notes, key=lambda x: x.updated_at, reverse=True):
            linked = any(lk.key == key for lk in parse_links(n.body))
            m = pattern.search(n.body)
            if linked or m or title_key(n.title) == key:
                out.append(
                    {
                        "id": n.id,
                        "title": n.title,
                        "linked": linked,
                        "snippet": snippet(n.body, m.start(), m.end()) if m else "",
                        "updated_at": n.updated_at.isoformat(),
                    }
                )
            if len(out) >= 30:
                break
        return out

    def prep_note(self, person_id: str) -> Note:
        """A 1:1 prep note: talking points, open follow-ups and the last meeting's note."""
        d = self.detail(person_id)
        name = d.summary.person.name
        today = self._clock.now().astimezone(self._tz()).date()
        last = next((m for m in d.meetings if not m["upcoming"] and not m["skipped"]), None)
        lines = [f"Prep for a 1:1 with [[{name}]] on {today.isoformat()}.", "", "## Talking points"]
        lines += [d.talking_points.strip() or "- "]
        lines += ["", "## Open follow-ups"]
        lines += [f"- [ ] {t['title']}" for t in d.follow_ups] or ["- none on file"]
        if last:
            lines += ["", f"## Last time ({last['day']})", last["note"].strip() or "- no notes"]
        lines += ["", "## Notes", ""]
        return self._notes.create(
            title=f"1:1 {name} {today.isoformat()}",
            body="\n".join(lines),
            kind=NoteKind.MEETING,
            tags=["one-on-one"],
        )
