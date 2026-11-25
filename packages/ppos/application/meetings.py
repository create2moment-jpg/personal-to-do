"""Meetings, calls, calendar import and time insights."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import Any

from ppos.application.ports import UnitOfWork, UnitOfWorkFactory
from ppos.application.settings import SettingsService
from ppos.domain.meetings import (
    Attendance,
    DayTime,
    ImportedEvent,
    ImportedSeries,
    Meeting,
    MeetingKind,
    MeetingSeries,
    Person,
    Recurrence,
    SeriesPlan,
    Topic,
    day_time,
)
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

IcsParser = Callable[
    [str | bytes, datetime, datetime, tzinfo], tuple[list[ImportedEvent], list[ImportedSeries]]
]

IMPORT_PAST_DAYS = 30
IMPORT_FUTURE_DAYS = 120


@dataclass
class ImportResult:
    events: int
    created: int
    updated: int
    cancelled: int
    series: int
    window_start: datetime
    window_end: datetime


@dataclass
class SeriesOverview:
    series: MeetingSeries
    occurrences_4w: int  # upcoming 4 weeks
    avg_minutes: int
    minutes_per_month: int  # attended, projected from the next 4 weeks
    next_start: datetime | None
    last_start: datetime | None
    topic_name: str | None


@dataclass
class TimeInsights:
    start: date
    end: date
    days: list[DayTime]
    meeting_minutes: int
    work_minutes: int
    available_minutes: int
    meetings_count: int
    calls_count: int
    by_person: list[tuple[str, int, int]]  # name, minutes, count
    by_topic: list[tuple[str, int, int]]
    by_series: list[tuple[str, str, int, int, float | None]]  # key, title, minutes, count, rating
    rated_minutes: int
    avg_rating: float | None
    reconsider: list[dict[str, Any]] = field(default_factory=list)


class MeetingService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        settings: SettingsService,
        parser: IcsParser,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._settings = settings
        self._parse = parser

    # ---------------------------------------------------------------- queries
    def day_bounds(self, start: date, end_inclusive: date) -> tuple[datetime, datetime]:
        tz = self._settings.tz()
        return (
            datetime.combine(start, datetime.min.time(), tzinfo=tz).astimezone(timezone.utc),
            datetime.combine(
                end_inclusive + timedelta(days=1), datetime.min.time(), tzinfo=tz
            ).astimezone(timezone.utc),
        )

    def between(
        self, start: date, end_inclusive: date
    ) -> tuple[list[Meeting], dict[str, MeetingSeries]]:
        a, b = self.day_bounds(start, end_inclusive)
        with self._uow() as uow:
            return uow.meetings.find(a, b), uow.meetings.series()

    def day_time(self, day: date) -> DayTime:
        meetings, series = self.between(day, day)
        return day_time(day, meetings, series, self._settings.get())

    def people(self) -> list[Person]:
        with self._uow() as uow:
            return uow.people.find()

    def topics(self) -> list[Topic]:
        with self._uow() as uow:
            return uow.topics.find()

    def last_import(self) -> dict[str, Any] | None:
        with self._uow() as uow:
            return uow.meetings.last_import()

    # ---------------------------------------------------------------- import
    def import_ics(self, filename: str, content: str | bytes) -> ImportResult:
        now = self._clock.now()
        start = now - timedelta(days=IMPORT_PAST_DAYS)
        end = now + timedelta(days=IMPORT_FUTURE_DAYS)
        events, series = self._parse(content, start, end, self._settings.tz())
        created = updated = 0
        with self._uow() as uow:
            for s in series:
                uow.meetings.upsert_series(s.series_key, s.title, s.cadence)
            for ev in events:
                is_new = uow.meetings.upsert_imported(
                    Meeting(
                        id=new_id(),
                        source="ics",
                        external_key=ev.external_key,
                        series_key=ev.series_key,
                        title=ev.title,
                        start_at=ev.start_at,
                        end_at=ev.end_at,
                        all_day=ev.all_day,
                        location=ev.location,
                        organizer=ev.organizer,
                        created_at=now,
                        updated_at=now,
                    )
                )
                created += is_new
                updated += not is_new
            cancelled = uow.meetings.cancel_missing({e.external_key for e in events}, start, end)
            uow.meetings.record_import(filename, (start, end), len(events), len(series))
            uow.audit.record(
                "calendar",
                "import",
                "import_ics",
                actor="system",
                details={
                    "file": filename,
                    "events": len(events),
                    "created": created,
                    "cancelled": cancelled,
                },
            )
            uow.commit()
        return ImportResult(len(events), created, updated, cancelled, len(series), start, end)

    # ---------------------------------------------------------------- calls / edits
    def log_call(
        self,
        title: str,
        start_at: datetime,
        minutes: int,
        people: list[str] | None = None,
        topic: str | None = None,
        note: str = "",
        rating: int | None = None,
        kind: MeetingKind = MeetingKind.CALL,
    ) -> Meeting:
        if not 1 <= minutes <= 12 * 60:
            raise ValidationError("duration must be between 1 minute and 12 hours")
        tz = self._settings.tz()  # read before opening a transaction
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=tz)
        now = self._clock.now()
        with self._uow() as uow:
            person_ids = [uow.people.get_or_create(n).id for n in people or [] if n.strip()]
            topic_id = uow.topics.get_or_create(topic).id if topic and topic.strip() else None
            meeting = Meeting(
                id=new_id(),
                source="manual",
                kind=kind,
                title=title or (f"Call with {', '.join(people or [])}" if people else "Call"),
                start_at=start_at.astimezone(timezone.utc),
                end_at=(start_at + timedelta(minutes=minutes)).astimezone(timezone.utc),
                status=Attendance.ATTENDED,
                topic_id=topic_id,
                note=note,
                rating=rating,
                people_ids=person_ids,
                created_at=now,
                updated_at=now,
            )
            uow.meetings.add(meeting)
            uow.audit.record("meeting", meeting.id, "log_call", details={"minutes": minutes})
            uow.commit()
            return meeting

    # ---------------------------------------------------------------- meetings you create
    def schedule(
        self,
        title: str,
        day: date,
        start_time: str,
        minutes: int,
        *,
        people: list[str] | None = None,
        topic: str | None = None,
        location: str | None = None,
        note: str = "",
        kind: str = "meeting",
        recurrence: Recurrence | None = None,
    ) -> Meeting | MeetingSeries:
        """Add a meeting (or call) to the calendar — once, or as a recurring series."""
        if not title.strip():
            raise ValidationError("give the meeting a title")
        plan = SeriesPlan(
            recurrence=recurrence or Recurrence("daily", count=1),
            first_day=day,
            start_time=start_time,
            minutes=minutes,
            kind=kind,
            people=tuple(p.strip() for p in people or [] if p.strip()),
            topic=topic.strip() if topic and topic.strip() else None,
            location=location.strip() if location and location.strip() else None,
        )
        if recurrence is None:
            tz = self._settings.tz()
            with self._uow() as uow:
                m = self._occurrence(uow, title, plan, day, None, tz)
                m.note = note
                uow.meetings.add(m)
                uow.audit.record("meeting", m.id, "schedule", details={"minutes": minutes})
                uow.commit()
                return m
        key = f"app:{new_id()}"
        with self._uow() as uow:
            uow.meetings.set_series_plan(key, title.strip(), recurrence.describe(), plan.to_dict())
            created = self._materialise(uow, key, title.strip(), plan, from_day=day)
            if plan.topic:
                s = uow.meetings.get_series(key)
                assert s is not None
                s.topic_id = uow.topics.get_or_create(plan.topic).id
                uow.meetings.update_series(s)
            uow.audit.record(
                "meeting_series",
                key,
                "create",
                details={"cadence": recurrence.describe(), "occurrences": created},
            )
            uow.commit()
            series = uow.meetings.get_series(key)
            assert series is not None
            return series

    def edit_series(self, key: str, changes: Mapping[str, Any]) -> MeetingSeries:
        """Change a series you created. Past occurrences stay as they happened; future ones
        are regenerated, keeping what you set on individual occurrences (skips, notes)."""
        allowed = {
            "title",
            "start_time",
            "minutes",
            "recurrence",
            "people",
            "topic",
            "location",
            "kind",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        today = self._clock.today()
        with self._uow() as uow:
            s, plan = self._app_series(uow, key)
            values = plan.to_dict()
            for k in ("start_time", "minutes", "location", "kind", "topic"):
                if k in changes:
                    values[k] = changes[k]
            if "people" in changes:
                values["people"] = [p for p in changes["people"] if p.strip()]
            if "recurrence" in changes:
                r = changes["recurrence"]
                values["recurrence"] = (
                    r if isinstance(r, Recurrence) else Recurrence.from_dict(r)
                ).to_dict()
            new_plan = SeriesPlan.from_dict(values)
            title = str(changes.get("title") or s.title).strip()
            uow.meetings.set_series_plan(
                key, title, new_plan.recurrence.describe(), new_plan.to_dict()
            )
            if "topic" in changes:
                s = uow.meetings.get_series(key) or s
                s.topic_id = uow.topics.get_or_create(new_plan.topic).id if new_plan.topic else None
                uow.meetings.update_series(s)
            self._materialise(uow, key, title, new_plan, from_day=today, replace_future=True)
            uow.audit.record(
                "meeting_series", key, "edit", details={k: str(v) for k, v in changes.items()}
            )
            uow.commit()
            out = uow.meetings.get_series(key)
            assert out is not None
            return out

    def end_series(self, key: str) -> int:
        """Stop a series you created: future occurrences are removed, history is kept."""
        today, now = self._clock.today(), self._clock.now()
        with self._uow() as uow:
            s, plan = self._app_series(uow, key)
            occurrences = uow.meetings.occurrences(key)
            past = [m for m in occurrences if m.start_at < now]
            for m in occurrences:
                if m.start_at >= now:
                    uow.meetings.delete(m.id)
            removed = len(occurrences) - len(past)
            if past:
                r = plan.recurrence
                ended = Recurrence(r.freq, r.interval, r.weekdays, until=today - timedelta(days=1))
                new_plan = SeriesPlan.from_dict(plan.to_dict() | {"recurrence": ended.to_dict()})
                uow.meetings.set_series_plan(key, s.title, ended.describe(), new_plan.to_dict())
            else:
                uow.meetings.delete_series(key)
            uow.audit.record("meeting_series", key, "end", details={"removed": removed})
            uow.commit()
            return removed

    def top_up_series(self) -> int:
        """Keep open-ended series you created filled up to the planning horizon."""
        added = 0
        with self._uow() as uow:
            for key, s in uow.meetings.series().items():
                if s.source != "app" or not s.plan:
                    continue
                plan = SeriesPlan.from_dict(s.plan)
                existing = uow.meetings.occurrences(key)
                start = (
                    (
                        existing[-1].start_at.astimezone(self._settings.tz()).date()
                        + timedelta(days=1)
                    )
                    if existing
                    else plan.first_day
                )
                added += self._materialise(uow, key, s.title, plan, from_day=start)
            if added:
                uow.commit()
        return added

    def _app_series(self, uow: UnitOfWork, key: str) -> tuple[MeetingSeries, SeriesPlan]:
        s = uow.meetings.get_series(key)
        if s is None:
            raise NotFoundError("meeting series", key)
        if s.source != "app" or not s.plan:
            raise ValidationError("imported series are read-only; change them in your calendar")
        return s, SeriesPlan.from_dict(s.plan)

    def _occurrence(
        self, uow: UnitOfWork, title: str, plan: SeriesPlan, day: date, key: str | None, tz: tzinfo
    ) -> Meeting:
        hh, mm = (int(x) for x in plan.start_time.split(":"))
        start = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz).astimezone(timezone.utc)
        now = self._clock.now()
        return Meeting(
            id=new_id(),
            source="manual",
            kind=MeetingKind(plan.kind),
            title=title,
            start_at=start,
            end_at=start + timedelta(minutes=plan.minutes),
            external_key=f"{key}:{day.isoformat()}" if key else None,
            series_key=key,
            location=plan.location,
            topic_id=uow.topics.get_or_create(plan.topic).id if plan.topic else None,
            people_ids=[uow.people.get_or_create(n).id for n in plan.people],
            created_at=now,
            updated_at=now,
        )

    def _materialise(
        self,
        uow: UnitOfWork,
        key: str,
        title: str,
        plan: SeriesPlan,
        from_day: date,
        replace_future: bool = False,
    ) -> int:
        tz = self._settings.tz()
        horizon = self._clock.today() + timedelta(days=IMPORT_FUTURE_DAYS)
        kept: dict[str, Meeting] = {}
        if replace_future:
            for m in uow.meetings.occurrences(key):
                if m.start_at.astimezone(tz).date() >= from_day:
                    if m.external_key:
                        kept[m.external_key.rsplit(":", 1)[-1]] = m
                    uow.meetings.delete(m.id)
        days = [d for d in plan.recurrence.days(plan.first_day, horizon) if d >= from_day]
        for d in days:
            m = self._occurrence(uow, title, plan, d, key, tz)
            old = kept.get(d.isoformat())
            if old is not None:  # carry over what the user set on this occurrence
                m.status, m.note, m.rating, m.cancelled = (
                    old.status,
                    old.note,
                    old.rating,
                    old.cancelled,
                )
                m.attended_minutes = old.attended_minutes
            uow.meetings.add(m)
        return len(days)

    def update(self, meeting_id: str, changes: Mapping[str, Any]) -> Meeting:
        allowed = {
            "status",
            "attended_minutes",
            "rating",
            "note",
            "topic",
            "people",
            "title",
            "start_at",
            "minutes",
            "kind",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        tz = self._settings.tz()
        with self._uow() as uow:
            m = self._require(uow, meeting_id)
            imported_only = {"title", "start_at", "minutes"} & set(changes)
            if imported_only and m.source != "manual":
                raise ValidationError(
                    "imported meetings are read-only; change them in your calendar"
                )
            for key, value in changes.items():
                if key == "status":
                    m.status = Attendance(value) if value else None
                elif key == "topic":
                    m.topic_id = uow.topics.get_or_create(value).id if value else None
                elif key == "people":
                    m.people_ids = [uow.people.get_or_create(n).id for n in value if n.strip()]
                elif key == "kind":
                    m.kind = MeetingKind(value)
                elif key == "start_at":
                    duration = m.end_at - m.start_at
                    start = value if value.tzinfo else value.replace(tzinfo=tz)
                    m.start_at = start.astimezone(timezone.utc)
                    m.end_at = m.start_at + duration
                elif key == "minutes":
                    m.end_at = m.start_at + timedelta(minutes=int(value))
                else:
                    setattr(m, key, value)
            m.updated_at = self._clock.now()
            Meeting.__post_init__(m)
            uow.meetings.update(m)
            uow.audit.record(
                "meeting", m.id, "update", details={k: str(v) for k, v in changes.items()}
            )
            uow.commit()
            return m

    def delete(self, meeting_id: str) -> None:
        with self._uow() as uow:
            m = self._require(uow, meeting_id)
            if m.source != "manual":
                raise ValidationError(
                    "imported meetings can't be deleted; mark them as skipped instead"
                )
            if m.series_key:  # one occurrence of a series you created: cancel just this one
                m.cancelled, m.updated_at = True, self._clock.now()
                uow.meetings.update(m)
            else:
                uow.meetings.delete(meeting_id)
            uow.audit.record("meeting", meeting_id, "delete")
            uow.commit()

    def update_series(self, key: str, changes: Mapping[str, Any]) -> MeetingSeries:
        allowed = {"default_status", "rating", "topic", "notes"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            s = uow.meetings.get_series(key)
            if s is None:
                raise NotFoundError("meeting series", key)
            for k, v in changes.items():
                if k == "default_status":
                    if v not in ("attending", "skipped"):
                        raise ValidationError("default_status must be attending or skipped")
                    s.default_status = v
                elif k == "rating":
                    if v is not None and not 1 <= int(v) <= 5:
                        raise ValidationError("rating must be 1–5")
                    s.rating = v
                elif k == "topic":
                    s.topic_id = uow.topics.get_or_create(v).id if v else None
                else:
                    s.notes = v
            s.updated_at = self._clock.now()
            uow.meetings.update_series(s)
            uow.audit.record(
                "meeting_series", key, "update", details={k: str(v) for k, v in changes.items()}
            )
            uow.commit()
            return s

    def forget_person(self, person_id: str) -> None:
        with self._uow() as uow:
            uow.people.delete(person_id)
            uow.audit.record("person", person_id, "forget")
            uow.commit()

    # ---------------------------------------------------------------- overviews
    def series_overview(self) -> list[SeriesOverview]:
        today = self._clock.today()
        meetings, series = self.between(today - timedelta(days=28), today + timedelta(days=27))
        topics = {t.id: t.name for t in self.topics()}
        now = self._clock.now()
        grouped: dict[str, list[Meeting]] = defaultdict(list)
        for m in meetings:
            if m.series_key:
                grouped[m.series_key].append(m)
        out: list[SeriesOverview] = []
        for key, s in series.items():
            ms = grouped.get(key, [])
            upcoming = [m for m in ms if m.start_at >= now]
            past = [m for m in ms if m.start_at < now]
            basis = upcoming or past
            avg = int(sum(m.duration_minutes for m in basis) / len(basis)) if basis else 0
            attended = sum(m.counted_minutes(s) for m in basis)
            per_month = int(attended * (30 / 28))
            out.append(
                SeriesOverview(
                    series=s,
                    occurrences_4w=len(upcoming),
                    avg_minutes=avg,
                    minutes_per_month=per_month,
                    next_start=upcoming[0].start_at if upcoming else None,
                    last_start=past[-1].start_at if past else None,
                    topic_name=topics.get(s.topic_id) if s.topic_id else None,
                )
            )
        out.sort(key=lambda o: (-o.minutes_per_month, o.series.title.lower()))
        return out

    def insights(self, start: date, end_inclusive: date) -> TimeInsights:
        if end_inclusive < start or (end_inclusive - start).days > 366:
            raise ValidationError("choose a range of up to one year")
        settings = self._settings.get()
        meetings, series = self.between(start, end_inclusive)
        people = {p.id: p.name for p in self.people()}
        topics = {t.id: t.name for t in self.topics()}
        days = [
            day_time(start + timedelta(days=i), meetings, series, settings)
            for i in range((end_inclusive - start).days + 1)
        ]

        by_person: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        by_topic: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        by_series: dict[str, list[Any]] = {}
        rated_minutes = 0
        rating_weight = 0.0
        meetings_count = calls_count = 0
        for m in meetings:
            s = series.get(m.series_key) if m.series_key else None
            minutes = m.counted_minutes(s)
            if minutes == 0:
                continue
            if m.kind == MeetingKind.CALL:
                calls_count += 1
            else:
                meetings_count += 1
            for pid in m.people_ids:
                by_person[people.get(pid, "Unknown")][0] += minutes
                by_person[people.get(pid, "Unknown")][1] += 1
            topic_id = m.topic_id or (s.topic_id if s else None)
            topic = topics.get(topic_id, "Unassigned") if topic_id else "Unassigned"
            by_topic[topic][0] += minutes
            by_topic[topic][1] += 1
            if s:
                entry = by_series.setdefault(s.series_key, [s.title, 0, 0, s.rating])
                entry[1] += minutes
                entry[2] += 1
            rating = m.rating if m.rating is not None else (s.rating if s else None)
            if rating is not None:
                rated_minutes += minutes
                rating_weight += rating * minutes

        reconsider = [
            {
                "series_key": k,
                "title": v[0],
                "minutes": v[1],
                "rating": v[3],
                "suggestion": "Decline or make async"
                if (v[3] or 3) <= 2
                else "Shorten or reduce frequency",
            }
            for k, v in by_series.items()
            if v[1] >= 60 and (v[3] is not None and v[3] <= 2)
        ]
        reconsider.sort(key=lambda r: -int(r["minutes"]))
        return TimeInsights(
            start=start,
            end=end_inclusive,
            days=days,
            meeting_minutes=sum(d.meeting_minutes_total for d in days),
            work_minutes=sum(d.work_minutes for d in days),
            available_minutes=sum(d.available_minutes for d in days),
            meetings_count=meetings_count,
            calls_count=calls_count,
            by_person=sorted(((k, v[0], v[1]) for k, v in by_person.items()), key=lambda x: -x[1]),
            by_topic=sorted(((k, v[0], v[1]) for k, v in by_topic.items()), key=lambda x: -x[1]),
            by_series=sorted(
                ((k, v[0], v[1], v[2], v[3]) for k, v in by_series.items()), key=lambda x: -x[2]
            ),
            rated_minutes=rated_minutes,
            avg_rating=round(rating_weight / rated_minutes, 2) if rated_minutes else None,
            reconsider=reconsider,
        )

    @staticmethod
    def _require(uow: UnitOfWork, meeting_id: str) -> Meeting:
        m = uow.meetings.get(meeting_id)
        if m is None:
            raise NotFoundError("meeting", meeting_id)
        return m
