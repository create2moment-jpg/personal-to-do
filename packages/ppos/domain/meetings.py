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
