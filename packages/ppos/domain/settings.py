"""Workspace settings: time zone, working hours, sprint defaults."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo, available_timezones

from ppos.shared.errors import ValidationError

DEFAULT_TIMEZONE = "Europe/Berlin"


@dataclass(frozen=True)
class WorkspaceSettings:
    timezone: str = DEFAULT_TIMEZONE
    work_start: str = "08:00"
    work_end: str = "17:00"
    workdays: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon=0
    buffer_percent: int = 10
    sprint_length_days: int = 14
    default_task_minutes: int = 30  # what a task without an estimate counts as in capacity

    def __post_init__(self) -> None:
        if self.timezone not in _zones():
            raise ValidationError(f"unknown time zone {self.timezone!r}")
        start, end = parse_hhmm(self.work_start), parse_hhmm(self.work_end)
        if end <= start:
            raise ValidationError("working hours must end after they start")
        if not self.workdays or any(d not in range(7) for d in self.workdays):
            raise ValidationError("workdays must be weekday numbers 0 (Mon) – 6 (Sun)")
        if not 0 <= self.buffer_percent <= 50:
            raise ValidationError("buffer must be between 0 and 50 percent")
        if not 7 <= self.sprint_length_days <= 28:
            raise ValidationError("sprint length must be between 7 and 28 days")
        if not 0 <= self.default_task_minutes <= 480:
            raise ValidationError("default task time must be between 0 and 480 minutes")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def start_time(self) -> time:
        return parse_hhmm(self.work_start)

    @property
    def end_time(self) -> time:
        return parse_hhmm(self.work_end)

    @property
    def work_minutes(self) -> int:
        s, e = self.start_time, self.end_time
        return (e.hour * 60 + e.minute) - (s.hour * 60 + s.minute)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def merged(self, changes: dict[str, Any]) -> WorkspaceSettings:
        unknown = set(changes) - set(asdict(self))
        if unknown:
            raise ValidationError(f"unknown settings: {sorted(unknown)}")
        data = asdict(self) | changes
        data["workdays"] = sorted({int(d) for d in data["workdays"]})
        return WorkspaceSettings(**data)


def parse_hhmm(value: str) -> time:
    try:
        hh, mm = value.split(":")
        return time(int(hh), int(mm))
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"invalid time {value!r}, expected HH:MM") from exc


_ZONES: set[str] | None = None


def _zones() -> set[str]:
    global _ZONES
    if _ZONES is None:
        _ZONES = available_timezones()
    return _ZONES
