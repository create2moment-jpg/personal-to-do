"""Habits (B-030): streaks are counted kindly — today not done yet does not break one."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ppos.domain.book import clean_emoji
from ppos.shared.errors import ValidationError

CADENCES = ("daily", "weekdays", "weekly")


@dataclass
class Habit:
    id: str
    name: str
    created_at: datetime
    emoji: str | None = None
    cadence: str = "daily"
    archived: bool = False
    position: float = 0.0

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())[:80]
        if not self.name:
            raise ValidationError("give the habit a name")
        if self.cadence not in CADENCES:
            raise ValidationError(f"cadence must be one of {', '.join(CADENCES)}")
        self.emoji = clean_emoji(self.emoji)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def streak(cadence: str, done: set[date], today: date) -> int:
    """Consecutive periods with the habit done, ending today (or yesterday if today is open)."""
    if cadence == "weekly":
        weeks = {_monday(d) for d in done}
        cur = _monday(today)
        if cur not in weeks:
            cur -= timedelta(days=7)  # this week is still open
        n = 0
        while cur in weeks:
            n += 1
            cur -= timedelta(days=7)
        return n
    counts = (lambda d: d.weekday() < 5) if cadence == "weekdays" else (lambda d: True)
    day = today
    if day not in done:
        day -= timedelta(days=1)  # today is still open
    n = 0
    for _ in range(3650):
        if counts(day):
            if day not in done:
                break
            n += 1
        day -= timedelta(days=1)
    return n


def rate(cadence: str, done: set[date], today: date, days: int = 30) -> float:
    """Share of the last ``days`` periods (days, weekdays or weeks) in which it was done."""
    if cadence == "weekly":
        weeks = [_monday(today) - timedelta(days=7 * i) for i in range(1, days // 7 + 1)]
        hit = {_monday(d) for d in done}
        return round(sum(w in hit for w in weeks) / len(weeks), 2) if weeks else 0.0
    span = [today - timedelta(days=i) for i in range(1, days + 1)]
    if cadence == "weekdays":
        span = [d for d in span if d.weekday() < 5]
    return round(sum(d in done for d in span) / len(span), 2) if span else 0.0
