"""Sprints, weekly plans and burndown."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum

from ppos.domain.tasks import Task, TaskStatus
from ppos.shared.errors import ValidationError

MAX_WEEKLY_OBJECTIVES = 3


class SprintStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"


class Commitment(str, Enum):
    COMMITTED = "committed"
    STRETCH = "stretch"


@dataclass
class Sprint:
    id: str
    name: str
    start_date: date
    end_date: date
    created_at: datetime
    updated_at: datetime
    goal: str = ""
    status: SprintStatus = SprintStatus.PLANNED
    review_summary: str = ""
    review_lessons: str = ""
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.name = " ".join(self.name.split())
        if not self.name:
            raise ValidationError("sprint name must not be empty")
        length = (self.end_date - self.start_date).days + 1
        if not 1 <= length <= 42:
            raise ValidationError("a sprint must last between 1 and 42 days")

    @property
    def days(self) -> list[date]:
        return [
            self.start_date + timedelta(days=i)
            for i in range((self.end_date - self.start_date).days + 1)
        ]

    def overlaps(self, other: Sprint) -> bool:
        return self.start_date <= other.end_date and other.start_date <= self.end_date


@dataclass(frozen=True)
class ScopeEvent:
    sprint_id: str
    task_id: str
    action: str  # add | remove
    commitment: str | None
    after_start: bool
    at: datetime


@dataclass
class WeeklyObjective:
    text: str
    done: bool = False


@dataclass
class WeeklyPlan:
    week_start: date  # Monday
    objectives: list[WeeklyObjective] = field(default_factory=list)
    notes: str = ""
    review_wins: str = ""
    review_lessons: str = ""
    review_risks: str = ""
    review_next_focus: str = ""
    review_completed_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.week_start.weekday() != 0:
            raise ValidationError("a week starts on Monday")
        self.objectives = [o for o in self.objectives if o.text.strip()]
        if len(self.objectives) > MAX_WEEKLY_OBJECTIVES:
            raise ValidationError(f"at most {MAX_WEEKLY_OBJECTIVES} weekly objectives")


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


@dataclass(frozen=True)
class BurndownPoint:
    day: date
    remaining_minutes: int
    ideal_minutes: float
    scope_minutes: int


def burndown(
    sprint: Sprint,
    tasks: list[Task],
    scope_events: list[ScopeEvent],
    today: date,
    unestimated_minutes: int = 30,
) -> list[BurndownPoint]:
    """Remaining estimated work at the end of each sprint day.

    A task counts towards a day if it was in the sprint at the end of that day
    (per scope events; tasks without events count from the start) and was not
    completed by then. Future days are omitted from ``remaining``.
    """
    added: dict[str, date] = {}
    removed: dict[str, date] = {}
    for ev in sorted(scope_events, key=lambda e: e.at):
        d = ev.at.date()
        if ev.action == "add":
            # Planned before the start counts from day one; later adds are scope changes.
            added[ev.task_id] = d if ev.after_start else min(d, sprint.start_date)
            removed.pop(ev.task_id, None)
        else:
            removed[ev.task_id] = d

    def weight(t: Task) -> int:
        return t.estimate_minutes if t.estimate_minutes is not None else unestimated_minutes

    def in_scope(t: Task, d: date) -> bool:
        start = added.get(t.id, sprint.start_date)
        end = removed.get(t.id)
        return start <= d and (end is None or end > d)

    days = sprint.days
    initial = sum(
        weight(t) for t in tasks if in_scope(t, sprint.start_date) and t.parent_id is None
    )
    points: list[BurndownPoint] = []
    for i, d in enumerate(days):
        scope = [t for t in tasks if t.parent_id is None and in_scope(t, d)]
        scope_minutes = sum(weight(t) for t in scope)
        remaining = sum(
            weight(t)
            for t in scope
            if not (
                t.status == TaskStatus.DONE
                and t.completed_at is not None
                and t.completed_at.date() <= d
            )
        )
        ideal = initial * (1 - (i + 1) / len(days)) if days else 0
        if d <= today:
            points.append(BurndownPoint(d, remaining, round(ideal, 1), scope_minutes))
        else:
            points.append(BurndownPoint(d, -1, round(ideal, 1), scope_minutes))
    return points
