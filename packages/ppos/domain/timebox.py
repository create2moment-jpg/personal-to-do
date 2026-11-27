"""Timeboxing: give planned tasks a start time inside the free parts of a day.

Times are minutes since local midnight. Everything here is pure and
deterministic; the application layer converts meetings to local minutes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ppos.shared.errors import ValidationError

SNAP = 5  # proposals start on a 5-minute grid
MIN_SLOT = 15  # gaps shorter than this are not offered as free time
_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_start(value: str | None) -> str | None:
    """Validate a timebox start ("HH:MM"); None or "" clears it."""
    if value is None or value == "":
        return None
    if not _HHMM.match(value):
        raise ValidationError(f"invalid start time {value!r}, expected HH:MM")
    return value


def to_minutes(hhmm: str) -> int:
    hh, mm = hhmm.split(":")
    return int(hh) * 60 + int(mm)


def to_hhmm(minutes: int) -> str:
    minutes = max(0, min(minutes, 24 * 60 - 1))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass(frozen=True)
class Span:
    start: int
    end: int

    @property
    def minutes(self) -> int:
        return self.end - self.start


def merge(spans: list[Span]) -> list[Span]:
    out: list[Span] = []
    for s in sorted((s for s in spans if s.end > s.start), key=lambda s: s.start):
        if out and s.start <= out[-1].end:
            out[-1] = Span(out[-1].start, max(out[-1].end, s.end))
        else:
            out.append(s)
    return out


def free_slots(window: Span | None, busy: list[Span], min_len: int = MIN_SLOT) -> list[Span]:
    """Gaps inside the working window that no meeting or timebox occupies."""
    if window is None:
        return []
    out: list[Span] = []
    cursor = window.start
    for b in merge(busy):
        if b.end <= cursor or b.start >= window.end:
            continue
        if b.start - cursor >= min_len:
            out.append(Span(cursor, b.start))
        cursor = max(cursor, b.end)
    if window.end - cursor >= min_len:
        out.append(Span(cursor, window.end))
    return out


@dataclass(frozen=True)
class Placement:
    task_id: str
    start: int
    minutes: int


def propose(
    tasks: list[tuple[str, int]], free: list[Span], not_before: int = 0
) -> tuple[list[Placement], list[str]]:
    """First-fit in the given order (most important first).

    A task is placed in the earliest free gap that fits its whole duration; tasks
    that fit nowhere are returned as unplaced, never split or shortened.
    """
    gaps = [Span(max(g.start, _snap_up(not_before)), g.end) for g in free if g.end > not_before]
    gaps = [Span(_snap_up(g.start), g.end) for g in gaps if g.end - _snap_up(g.start) > 0]
    placed: list[Placement] = []
    unplaced: list[str] = []
    for task_id, minutes in tasks:
        for i, g in enumerate(gaps):
            if g.minutes >= minutes:
                placed.append(Placement(task_id, g.start, minutes))
                rest = Span(_snap_up(g.start + minutes), g.end)
                gaps[i : i + 1] = [rest] if rest.minutes >= MIN_SLOT else []
                break
        else:
            unplaced.append(task_id)
    return placed, unplaced


def _snap_up(m: int) -> int:
    return -(-m // SNAP) * SNAP
