"""Today view, daily plan and end-of-day review use cases."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Any

from ppos.application.ports import TaskQuery, UnitOfWorkFactory
from ppos.domain.daily import CapacitySummary, DailyPlan, summarize_capacity
from ppos.domain.meetings import DayTime, Meeting, MeetingSeries
from ppos.domain.notes import Note
from ppos.domain.tasks import Task, TaskStatus
from ppos.shared.clock import Clock
from ppos.shared.errors import NotFoundError, ValidationError

REVIEW_FIELDS = frozenset({"unfinished", "blockers", "learning", "wins", "tomorrow_first_task"})
OPEN_STATUSES = (TaskStatus.PLANNED, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)


@dataclass
class TodayView:
    day: date
    plan: DailyPlan
    tasks: list[Task]
    overdue: list[Task]
    due_today_unscheduled: list[Task]
    capacity: CapacitySummary
    journal: Note | None
    completed: list[Task] = field(default_factory=list)
    time: DayTime | None = None
    meetings: list[Meeting] = field(default_factory=list)
    series: dict[str, MeetingSeries] = field(default_factory=dict)


class DayService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        default_capacity_minutes: int,
        day_meetings: Callable[[date], tuple[DayTime, list[Meeting], dict[str, MeetingSeries]]]
        | None = None,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._default_capacity = default_capacity_minutes
        self._day_meetings = day_meetings

    def plan_for(self, day: date) -> DailyPlan:
        with self._uow() as uow:
            return uow.days.get(day) or DailyPlan(day=day, capacity_minutes=self._default_capacity)

    def today_view(self, day: date | None = None) -> TodayView:
        day = day or self._clock.today()
        with self._uow() as uow:
            plan = uow.days.get(day) or DailyPlan(day=day, capacity_minutes=self._default_capacity)
            tasks = uow.tasks.find(TaskQuery(scheduled_date=day, limit=500))
            overdue = (
                uow.tasks.find(TaskQuery(statuses=OPEN_STATUSES, scheduled_before=day, limit=200))
                if day <= self._clock.today()
                else []
            )
            due_unscheduled = [
                t
                for t in uow.tasks.find(
                    TaskQuery(statuses=(TaskStatus.BACKLOG,), unscheduled_only=True, limit=500)
                )
                if t.due_date is not None and t.due_date <= day
            ]
            journal = uow.notes.find_daily_journal(day)
        time: DayTime | None = None
        meetings: list[Meeting] = []
        series: dict[str, MeetingSeries] = {}
        if self._day_meetings is not None:
            time, meetings, series = self._day_meetings(day)
            if plan.capacity_mode == "auto":
                plan.capacity_minutes = time.capacity_minutes
        return TodayView(
            day=day,
            plan=plan,
            tasks=tasks,
            overdue=overdue,
            due_today_unscheduled=due_unscheduled,
            capacity=summarize_capacity(plan.capacity_minutes, tasks),
            journal=journal,
            completed=[t for t in tasks if t.status == TaskStatus.DONE],
            time=time,
            meetings=meetings,
            series=series,
        )

    def update_plan(self, day: date, changes: Mapping[str, Any]) -> DailyPlan:
        allowed = {"objective", "capacity_minutes", "top_priority_ids", "capacity_mode"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            plan = uow.days.get(day) or DailyPlan(day=day, capacity_minutes=self._default_capacity)
            for tid in changes.get("top_priority_ids", []):
                if uow.tasks.get(tid) is None:
                    raise NotFoundError("task", tid)
            updated = DailyPlan(
                day=day,
                capacity_minutes=int(changes.get("capacity_minutes", plan.capacity_minutes)),
                objective=str(changes.get("objective", plan.objective)),
                top_priority_ids=list(changes.get("top_priority_ids", plan.top_priority_ids)),
                review=plan.review,
                updated_at=self._clock.now(),
                capacity_mode=(
                    "manual"
                    if "capacity_minutes" in changes
                    else str(changes.get("capacity_mode", plan.capacity_mode))
                ),
            )
            if updated.capacity_mode not in ("auto", "manual"):
                raise ValidationError("capacity_mode must be auto or manual")
            uow.days.upsert(updated)
            uow.audit.record("day", day.isoformat(), "update_plan", details=dict(changes))
            uow.commit()
            return updated

    def save_review(self, day: date, changes: Mapping[str, Any], complete: bool) -> DailyPlan:
        unknown = set(changes) - REVIEW_FIELDS
        if unknown:
            raise ValidationError(f"unknown review fields: {sorted(unknown)}")
        now = self._clock.now()
        with self._uow() as uow:
            plan = uow.days.get(day) or DailyPlan(day=day, capacity_minutes=self._default_capacity)
            review = replace(plan.review, **dict(changes))
            if complete:
                review.completed_at = now
            plan.review = review
            plan.updated_at = now
            uow.days.upsert(plan)
            uow.audit.record("day", day.isoformat(), "review", details={"complete": complete})
            uow.commit()
            return plan

    def review_draft(self, day: date) -> dict[str, Any]:
        """Deterministic pre-fill for the end-of-day review (no LLM needed)."""
        view = self.today_view(day)
        unfinished = [t for t in view.tasks if t.is_open and t.parent_id is None]
        blocked = [t for t in unfinished if t.status == TaskStatus.BLOCKED]
        return {
            "completed": [t.title for t in view.completed if t.parent_id is None],
            "unfinished": "\n".join(f"- {t.title}" for t in unfinished),
            "blockers": "\n".join(f"- {t.title}" for t in blocked),
            "tomorrow_first_task": unfinished[0].title if unfinished else "",
        }

    def roll_over(self, day: date, to: date | None = None) -> list[Task]:
        """Move unfinished (non-done) tasks of ``day`` to ``to`` (default next day)."""
        target = to or day + timedelta(days=1)
        if target <= day:
            raise ValidationError("roll-over target must be after the source day")
        now = self._clock.now()
        moved: list[Task] = []
        with self._uow() as uow:
            for task in uow.tasks.find(TaskQuery(scheduled_date=day, statuses=OPEN_STATUSES)):
                task.scheduled_date = target
                task.updated_at = now
                if task.status == TaskStatus.IN_PROGRESS:
                    task.status = TaskStatus.PLANNED
                uow.tasks.update(task)
                moved.append(task)
            uow.audit.record(
                "day",
                day.isoformat(),
                "roll_over",
                details={"to": target.isoformat(), "count": len(moved)},
            )
            uow.commit()
        return moved
