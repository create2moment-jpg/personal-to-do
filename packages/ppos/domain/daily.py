"""Daily plan, end-of-day review and capacity rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from ppos.domain.tasks import Task
from ppos.shared.errors import ValidationError

MAX_TOP_PRIORITIES = 3


@dataclass
class DailyReview:
    unfinished: str = ""
    blockers: str = ""
    learning: str = ""
    wins: str = ""
    tomorrow_first_task: str = ""
    completed_at: datetime | None = None


@dataclass
class DailyPlan:
    day: date
    capacity_minutes: int
    objective: str = ""
    top_priority_ids: list[str] = field(default_factory=list)
    review: DailyReview = field(default_factory=DailyReview)
    updated_at: datetime | None = None
    capacity_mode: str = "auto"  # auto = working hours − meetings − buffer

    def __post_init__(self) -> None:
        if not 0 <= self.capacity_minutes <= 24 * 60:
            raise ValidationError("capacity must be between 0 and 1440 minutes")
        if len(self.top_priority_ids) > MAX_TOP_PRIORITIES:
            raise ValidationError(f"at most {MAX_TOP_PRIORITIES} top priorities")
        if len(set(self.top_priority_ids)) != len(self.top_priority_ids):
            raise ValidationError("top priorities must be unique")


@dataclass(frozen=True)
class CapacitySummary:
    capacity_minutes: int
    planned_minutes: int
    unestimated_count: int
    done_minutes: int

    @property
    def remaining_capacity(self) -> int:
        return self.capacity_minutes - self.planned_minutes

    @property
    def load_ratio(self) -> float:
        if self.capacity_minutes == 0:
            return float("inf") if self.planned_minutes else 0.0
        return self.planned_minutes / self.capacity_minutes

    @property
    def overcommitted(self) -> bool:
        return self.planned_minutes > self.capacity_minutes


# Unestimated tasks still cost something; assume a conservative default so
# the capacity meter cannot be gamed by leaving estimates blank.
DEFAULT_UNESTIMATED_MINUTES = 30


def summarize_capacity(
    capacity_minutes: int, tasks: list[Task], unestimated_minutes: int = DEFAULT_UNESTIMATED_MINUTES
) -> CapacitySummary:
    planned = 0
    unestimated = 0
    done = 0
    for task in tasks:
        if task.parent_id is not None:
            continue  # subtasks are accounted for by their parent's estimate
        if not task.is_open:
            done += task.actual_minutes or (task.estimate_minutes or 0)
            continue
        if task.estimate_minutes is None:
            unestimated += 1
            planned += unestimated_minutes
        else:
            planned += task.remaining_minutes()
    return CapacitySummary(capacity_minutes, planned, unestimated, done)
