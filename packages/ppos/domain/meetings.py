"""Meetings, calls and time accounting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum

from ppos.domain.settings import WorkspaceSettings
from ppos.shared.errors import ValidationError


class MeetingKind(str, Enum):
    MEETING = "meeting"
    CALL = "call"


class Attendance(str, Enum):
    ATTENDED = "attended"
    SKIPPED = "skipped"
    PARTIAL = "partial"


@dataclass
class Person:
    id: str
    name: str
    created_at: datetime


@dataclass
class Topic:
    id: str
    name: str
    created_at: datetime


@dataclass
class MeetingSeries:
    series_key: str
    title: str
    updated_at: datetime
    cadence: str | None = None
    default_status: str = "attending"  # attending | skipped
    topic_id: str | None = None
    rating: int | None = None
    notes: str = ""
    source: str = "ics"  # ics | app (created in the app, with a plan)
    plan: dict[str, object] | None = None


@dataclass
class Meeting:
    id: str
    source: str  # ics | manual
    title: str
    start_at: datetime  # aware, UTC
    end_at: datetime
    created_at: datetime
    updated_at: datetime
    kind: MeetingKind = MeetingKind.MEETING
    external_key: str | None = None
    series_key: str | None = None
    all_day: bool = False
    location: str | None = None
    organizer: str | None = None
    cancelled: bool = False
    status: Attendance | None = None  # user override; None = default
    attended_minutes: int | None = None
    rating: int | None = None
    note: str = ""
    topic_id: str | None = None
    people_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split()) or "(no title)"
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValidationError("meeting times must be timezone-aware")
        if self.end_at < self.start_at:
            raise ValidationError("a meeting cannot end before it starts")
        if self.end_at - self.start_at > timedelta(hours=24):
            raise ValidationError("a meeting cannot be longer than 24 hours")
        if self.rating is not None and not 1 <= self.rating <= 5:
            raise ValidationError("rating must be 1–5")
        if self.attended_minutes is not None and self.attended_minutes < 0:
            raise ValidationError("attended minutes must be positive")

    @property
    def duration_minutes(self) -> int:
        return int((self.end_at - self.start_at).total_seconds() // 60)

    def effective_status(self, series: MeetingSeries | None) -> Attendance:
        if self.status is not None:
            return self.status
        if series is not None and series.default_status == "skipped":
            return Attendance.SKIPPED
        return Attendance.ATTENDED

    def counted_minutes(self, series: MeetingSeries | None) -> int:
        """Minutes this meeting consumes (0 when skipped/cancelled/all-day)."""
        if self.cancelled or self.all_day:
            return 0
        status = self.effective_status(series)
        if status == Attendance.SKIPPED:
            return 0
        if status == Attendance.PARTIAL and self.attended_minutes is not None:
            return min(self.attended_minutes, self.duration_minutes)
        return self.duration_minutes


@dataclass(frozen=True)
class ImportedEvent:
    """One occurrence read from a calendar file (read-only source data)."""

    external_key: str
    series_key: str | None
    title: str
    start_at: datetime  # UTC
    end_at: datetime
    all_day: bool
    location: str | None
    organizer: str | None


@dataclass(frozen=True)
class ImportedSeries:
    series_key: str
    title: str
    cadence: str | None


def union_minutes(intervals: list[tuple[datetime, datetime]]) -> int:
    """Total minutes covered by possibly overlapping intervals (counted once)."""
    total = 0.0
    current: tuple[datetime, datetime] | None = None
    for start, end in sorted(intervals):
        if current is None or start > current[1]:
            if current is not None:
                total += (current[1] - current[0]).total_seconds()
            current = (start, end)
        else:
            current = (current[0], max(current[1], end))
    if current is not None:
        total += (current[1] - current[0]).total_seconds()
    return int(total // 60)


def working_window(day: date, settings: WorkspaceSettings) -> tuple[datetime, datetime] | None:
    if day.weekday() not in settings.workdays:
        return None
    tz = settings.tz
    return (
        datetime.combine(day, settings.start_time, tzinfo=tz),
        datetime.combine(day, settings.end_time, tzinfo=tz),
    )


@dataclass(frozen=True)
class DayTime:
    day: date
    work_minutes: int
    meeting_minutes: int  # attended, inside working hours, overlaps counted once
    meeting_minutes_total: int  # attended, any time of day
    available_minutes: int  # work − meetings
    capacity_minutes: int  # available − buffer


def day_time(
    day: date,
    meetings: list[Meeting],
    series: dict[str, MeetingSeries],
    settings: WorkspaceSettings,
) -> DayTime:
    window = working_window(day, settings)
    tz = settings.tz
    intervals_all: list[tuple[datetime, datetime]] = []
    intervals_work: list[tuple[datetime, datetime]] = []
    for m in meetings:
        if m.start_at.astimezone(tz).date() != day:
            continue
        minutes = m.counted_minutes(series.get(m.series_key) if m.series_key else None)
        if minutes == 0:
            continue
        start = m.start_at
        end = start + timedelta(minutes=minutes)
        intervals_all.append((start, end))
        if window:
            s, e = max(start, window[0]), min(end, window[1])
            if e > s:
                intervals_work.append((s, e))
    work = settings.work_minutes if window else 0
    meeting_work = union_minutes(intervals_work)
    available = max(work - meeting_work, 0)
    capacity = int(available * (1 - settings.buffer_percent / 100))
    return DayTime(day, work, meeting_work, union_minutes(intervals_all), available, capacity)


# --------------------------------------------------------------------------- app-created series

FREQS = ("daily", "weekly", "monthly")
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MAX_OCCURRENCES = 1000


@dataclass(frozen=True)
class Recurrence:
    """When a meeting you created repeats. Weekdays use 0 = Monday."""

    freq: str
    interval: int = 1
    weekdays: tuple[int, ...] = ()
    until: date | None = None
    count: int | None = None

    def __post_init__(self) -> None:
        if self.freq not in FREQS:
            raise ValidationError(f"repeat must be one of {', '.join(FREQS)}")
        if not 1 <= self.interval <= 52:
            raise ValidationError("repeat interval must be between 1 and 52")
        if any(not 0 <= d <= 6 for d in self.weekdays):
            raise ValidationError("weekdays must be 0 (Mon) to 6 (Sun)")
        if self.weekdays and self.freq != "weekly":
            raise ValidationError("weekdays apply to weekly meetings only")
        if self.count is not None and not 1 <= self.count <= MAX_OCCURRENCES:
            raise ValidationError(f"number of occurrences must be 1–{MAX_OCCURRENCES}")
        if self.count is not None and self.until is not None:
            raise ValidationError("end a series either on a date or after a number of times")
        object.__setattr__(self, "weekdays", tuple(sorted(set(self.weekdays))))

    def describe(self) -> str:
        every = {"daily": "day", "weekly": "week", "monthly": "month"}[self.freq]
        head = (
            {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}[self.freq]
            if self.interval == 1
            else f"Every {self.interval} {every}s"
        )
        if self.freq == "weekly" and self.weekdays:
            if self.weekdays == (0, 1, 2, 3, 4) and self.interval == 1:
                head = "Every weekday"
            else:
                head += " on " + ", ".join(WEEKDAY_NAMES[d] for d in self.weekdays)
        if self.until:
            head += f" until {self.until.isoformat()}"
        elif self.count:
            head += f", {self.count} times"
        return head

    def days(self, first: date, window_end: date) -> list[date]:
        """All occurrence days from ``first`` up to ``window_end`` (inclusive)."""
        from dateutil.rrule import DAILY, MONTHLY, WEEKLY, rrule, weekday  # type: ignore[import-untyped]

        freq = {"daily": DAILY, "weekly": WEEKLY, "monthly": MONTHLY}[self.freq]
        common = {
            "dtstart": datetime(first.year, first.month, first.day),
            "interval": self.interval,
            "byweekday": [weekday(d) for d in self.weekdays] or None,
        }
        if self.count is not None:  # COUNT and UNTIL must not be combined in one rule
            days = [d.date() for d in rrule(freq, count=self.count, **common)]
            return [d for d in days if d <= window_end]
        end = min(window_end, self.until) if self.until else window_end
        if end < first:
            return []
        rule = rrule(freq, until=datetime(end.year, end.month, end.day), **common)
        return [d.date() for d in rule[:MAX_OCCURRENCES]]

    def to_dict(self) -> dict[str, object]:
        return {
            "freq": self.freq,
            "interval": self.interval,
            "weekdays": list(self.weekdays),
            "until": self.until.isoformat() if self.until else None,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> Recurrence:
        until = d.get("until")
        count = d.get("count")
        return cls(
            freq=str(d["freq"]),
            interval=int(str(d.get("interval", 1))),
            weekdays=tuple(int(str(x)) for x in d.get("weekdays") or []),  # type: ignore[attr-defined]
            until=date.fromisoformat(str(until)) if until else None,
            count=int(str(count)) if count else None,
        )


@dataclass(frozen=True)
class SeriesPlan:
    """Everything needed to (re)generate the occurrences of a series you created."""

    recurrence: Recurrence
    first_day: date
    start_time: str  # HH:MM, local to the workspace time zone
    minutes: int
    kind: str = "meeting"
    people: tuple[str, ...] = ()
    topic: str | None = None
    location: str | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.minutes <= 12 * 60:
            raise ValidationError("duration must be between 1 minute and 12 hours")
        hh, _, mm = self.start_time.partition(":")
        if not (hh.isdigit() and mm.isdigit() and int(hh) < 24 and int(mm) < 60):
            raise ValidationError(f"invalid start time {self.start_time!r}, expected HH:MM")
        if self.kind not in ("meeting", "call"):
            raise ValidationError("kind must be meeting or call")

    def to_dict(self) -> dict[str, object]:
        return {
            "recurrence": self.recurrence.to_dict(),
            "first_day": self.first_day.isoformat(),
            "start_time": self.start_time,
            "minutes": self.minutes,
            "kind": self.kind,
            "people": list(self.people),
            "topic": self.topic,
            "location": self.location,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> SeriesPlan:
        return cls(
            recurrence=Recurrence.from_dict(d["recurrence"]),  # type: ignore[arg-type]
            first_day=date.fromisoformat(str(d["first_day"])),
            start_time=str(d["start_time"]),
            minutes=int(str(d["minutes"])),
            kind=str(d.get("kind", "meeting")),
            people=tuple(str(p) for p in d.get("people") or []),  # type: ignore[attr-defined]
            topic=str(d["topic"]) if d.get("topic") else None,
            location=str(d["location"]) if d.get("location") else None,
        )
