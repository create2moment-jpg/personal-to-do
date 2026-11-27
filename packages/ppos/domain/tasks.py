"""Task entity and its invariants."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum

from ppos.shared.errors import ConflictError, ValidationError

MAX_TITLE_LEN = 500
MAX_TAG_LEN = 64


class TaskStatus(str, Enum):
    BACKLOG = "backlog"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"  # blocked / waiting
    DONE = "done"


class Priority(int, Enum):
    """P1 is the most important. P4 is the default (unprioritised)."""

    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4


@dataclass
class Task:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    description: str = ""
    notes: str = ""
    status: TaskStatus = TaskStatus.BACKLOG
    priority: Priority = Priority.P4
    estimate_minutes: int | None = None
    actual_minutes: int = 0
    project_id: str | None = None
    area: str | None = None
    parent_id: str | None = None
    tags: list[str] = field(default_factory=list)
    due_date: date | None = None
    scheduled_date: date | None = None
    recurrence: str | None = None  # RFC 5545 RRULE text; expansion engine lands in Phase 3
    position: float = 0.0
    completed_at: datetime | None = None
    sprint_id: str | None = None
    commitment: str | None = None  # committed | stretch (only with sprint_id)
    goal_id: str | None = None
    deleted_at: datetime | None = None  # in the trash since (restorable for 30 days)
    timebox_start: str | None = None  # "HH:MM" local start on scheduled_date (timeboxing)

    def __post_init__(self) -> None:
        self.title = normalize_title(self.title)
        self.tags = normalize_tags(self.tags)
        validate_minutes("estimate_minutes", self.estimate_minutes)
        validate_minutes("actual_minutes", self.actual_minutes)
        if self.parent_id is not None and self.parent_id == self.id:
            raise ValidationError("a task cannot be its own parent")

    def transition(self, status: TaskStatus, at: datetime) -> None:
        """Move to a new state, maintaining completion timestamp invariants."""
        if status == self.status:
            return
        if status == TaskStatus.DONE:
            self.completed_at = at
        elif self.status == TaskStatus.DONE:
            self.completed_at = None
        if status == TaskStatus.BACKLOG:
            # Backlog means "not committed to a day".
            self.scheduled_date = None
        self.status = status
        self.updated_at = at

    def schedule(self, day: date | None, at: datetime) -> None:
        if day != self.scheduled_date:
            self.timebox_start = None  # a start time belongs to its day
        self.scheduled_date = day
        if day is not None and self.status == TaskStatus.BACKLOG:
            self.status = TaskStatus.PLANNED
        elif day is None and self.status == TaskStatus.PLANNED:
            self.status = TaskStatus.BACKLOG
        self.updated_at = at

    @property
    def is_open(self) -> bool:
        return self.status != TaskStatus.DONE

    def remaining_minutes(self) -> int:
        if not self.is_open or self.estimate_minutes is None:
            return 0
        return max(self.estimate_minutes - self.actual_minutes, 0)


def normalize_title(title: str) -> str:
    cleaned = " ".join(title.split())
    if not cleaned:
        raise ValidationError("title must not be empty")
    if len(cleaned) > MAX_TITLE_LEN:
        raise ValidationError(f"title must be at most {MAX_TITLE_LEN} characters")
    return cleaned


def normalize_tags(tags: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for raw in tags:
        tag = raw.strip().lstrip("#").lower()
        if not tag:
            continue
        if len(tag) > MAX_TAG_LEN or any(c.isspace() for c in tag):
            raise ValidationError(f"invalid tag {raw!r}")
        seen.setdefault(tag, None)
    return list(seen)


def validate_minutes(name: str, value: int | None) -> None:
    if value is not None and (value < 0 or value > 60 * 24 * 365):
        raise ValidationError(f"{name} must be between 0 and one year of minutes")


def detect_dependency_cycle(task_id: str, depends_on: str, edges: dict[str, set[str]]) -> None:
    """Raise if adding ``task_id -> depends_on`` would create a cycle.

    ``edges`` maps a task to the tasks it depends on.
    """
    if task_id == depends_on:
        raise ConflictError("a task cannot depend on itself")
    stack = [depends_on]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == task_id:
            raise ConflictError("dependency would create a cycle")
        if current in seen:
            continue
        seen.add(current)
        stack.extend(edges.get(current, ()))
