"""Sprint and week use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from ppos.application.meetings import MeetingService
from ppos.application.ports import TaskQuery, UnitOfWork, UnitOfWorkFactory
from ppos.application.settings import SettingsService
from ppos.domain.daily import DailyPlan
from ppos.domain.meetings import DayTime, Meeting, MeetingSeries, day_time
from ppos.domain.planning import (
    BurndownPoint,
    Commitment,
    ScopeEvent,
    Sprint,
    SprintStatus,
    WeeklyObjective,
    WeeklyPlan,
    burndown,
    monday_of,
)
from ppos.domain.tasks import Task, TaskStatus
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import ConflictError, NotFoundError, ValidationError


@dataclass
class SprintSummary:
    sprint: Sprint
    tasks: list[Task]
    committed_total: int
    committed_done: int
    stretch_total: int
    stretch_done: int
    committed_minutes: int
    remaining_minutes: int
    added_after_start: list[str]
    removed_after_start: list[str]
    burndown: list[BurndownPoint]
    days_total: int
    days_elapsed: int

    @property
    def completion_rate(self) -> float:
        return self.committed_done / self.committed_total if self.committed_total else 0.0


class SprintService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, settings: SettingsService
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._settings = settings

    def find(self) -> list[Sprint]:
        with self._uow() as uow:
            return uow.sprints.find()

    def current(self) -> Sprint | None:
        """The active sprint, else the next planned one."""
        sprints = self.find()
        active = [s for s in sprints if s.status == SprintStatus.ACTIVE]
        if active:
            return active[0]
        planned = sorted(
            (s for s in sprints if s.status == SprintStatus.PLANNED), key=lambda s: s.start_date
        )
        return planned[0] if planned else None

    def create(
        self,
        name: str = "",
        goal: str = "",
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> Sprint:
        today = self._clock.today()
        sprint_days = self._settings.get().sprint_length_days  # read before locking
        with self._uow() as uow:
            existing = uow.sprints.find()
            if start_date is None:
                latest_end = max(
                    (s.end_date for s in existing if s.status != SprintStatus.COMPLETED),
                    default=None,
                )
                start_date = max(today, latest_end + timedelta(days=1)) if latest_end else today
            end_date = end_date or start_date + timedelta(days=sprint_days - 1)
            now = self._clock.now()
            sprint = Sprint(
                id=new_id(),
                name=name or f"Sprint {len(existing) + 1}",
                goal=goal,
                start_date=start_date,
                end_date=end_date,
                created_at=now,
                updated_at=now,
            )
            for other in existing:
                if other.status != SprintStatus.COMPLETED and other.overlaps(sprint):
                    raise ConflictError(
                        f"overlaps with {other.name} ({other.start_date} – {other.end_date})"
                    )
            uow.sprints.add(sprint)
            uow.audit.record("sprint", sprint.id, "create", details={"name": sprint.name})
            uow.commit()
            return sprint

    def update(self, sprint_id: str, changes: Mapping[str, Any]) -> Sprint:
        allowed = {"name", "goal", "start_date", "end_date", "review_summary", "review_lessons"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            s = self._require(uow, sprint_id)
            for k, v in changes.items():
                setattr(s, k, v)
            s.updated_at = self._clock.now()
            Sprint.__post_init__(s)
            for other in uow.sprints.find():
                if (
                    other.id != s.id
                    and other.status != SprintStatus.COMPLETED
                    and other.overlaps(s)
                ):
                    raise ConflictError(f"overlaps with {other.name}")
            uow.sprints.update(s)
            uow.commit()
            return s

    def start(self, sprint_id: str) -> Sprint:
        with self._uow() as uow:
            s = self._require(uow, sprint_id)
            if s.status != SprintStatus.PLANNED:
                raise ConflictError("only a planned sprint can be started")
            if any(o.status == SprintStatus.ACTIVE for o in uow.sprints.find()):
                raise ConflictError("another sprint is already active — complete it first")
            s.status = SprintStatus.ACTIVE
            s.updated_at = self._clock.now()
            uow.sprints.update(s)
            uow.audit.record("sprint", s.id, "start")
            uow.commit()
            return s

    def add_tasks(
        self, sprint_id: str, task_ids: list[str], commitment: Commitment = Commitment.COMMITTED
    ) -> list[Task]:
        now = self._clock.now()
        out: list[Task] = []
        with self._uow() as uow:
            s = self._require(uow, sprint_id)
            if s.status == SprintStatus.COMPLETED:
                raise ConflictError("the sprint is completed")
            for tid in task_ids:
                t = uow.tasks.get(tid)
                if t is None:
                    raise NotFoundError("task", tid)
                if t.parent_id is not None:
                    raise ValidationError("add the parent task; subtasks follow it")
                if t.sprint_id and t.sprint_id != sprint_id:
                    self._record_scope(uow, t.sprint_id, t, "remove", now)
                if t.sprint_id != sprint_id:
                    self._record_scope(
                        uow,
                        sprint_id,
                        t,
                        "add",
                        now,
                        commitment.value,
                        s.status == SprintStatus.ACTIVE,
                    )
                t.sprint_id = sprint_id
                t.commitment = commitment.value
                t.updated_at = now
                uow.tasks.update(t)
                out.append(t)
            uow.commit()
        return out

    def remove_task(self, task_id: str) -> Task:
        now = self._clock.now()
        with self._uow() as uow:
            t = uow.tasks.get(task_id)
            if t is None:
                raise NotFoundError("task", task_id)
            if t.sprint_id:
                s = self._require(uow, t.sprint_id)
                self._record_scope(
                    uow, s.id, t, "remove", now, after_start=s.status == SprintStatus.ACTIVE
                )
            t.sprint_id = None
            t.commitment = None
            t.updated_at = now
            uow.tasks.update(t)
            uow.commit()
            return t

    def summary(self, sprint_id: str) -> SprintSummary:
        today = self._clock.today()
        default = self._settings.get().default_task_minutes  # read before locking
        with self._uow() as uow:
            s = self._require(uow, sprint_id)
            tasks = uow.tasks.find(TaskQuery(sprint_id=sprint_id, top_level_only=True, limit=1000))
            events = uow.sprints.scope_events(sprint_id)
        committed = [t for t in tasks if t.commitment != Commitment.STRETCH.value]
        stretch = [t for t in tasks if t.commitment == Commitment.STRETCH.value]

        def w(t: Task) -> int:
            return t.estimate_minutes if t.estimate_minutes is not None else default

        added = [e.task_id for e in events if e.after_start and e.action == "add"]
        removed = [e.task_id for e in events if e.after_start and e.action == "remove"]
        elapsed = min(max((today - s.start_date).days + 1, 0), len(s.days))
        return SprintSummary(
            sprint=s,
            tasks=tasks,
            committed_total=len(committed),
            committed_done=sum(t.status == TaskStatus.DONE for t in committed),
            stretch_total=len(stretch),
            stretch_done=sum(t.status == TaskStatus.DONE for t in stretch),
            committed_minutes=sum(w(t) for t in committed),
            remaining_minutes=sum(w(t) for t in tasks if t.status != TaskStatus.DONE),
            added_after_start=added,
            removed_after_start=removed,
            burndown=burndown(s, tasks, events, today, default),
            days_total=len(s.days),
            days_elapsed=elapsed,
        )

    def complete(
        self, sprint_id: str, rollover: str, summary: str = "", lessons: str = ""
    ) -> tuple[Sprint, Sprint | None, int]:
        """Close the sprint. Open tasks roll over to the next sprint (created if
        needed) or back to the backlog."""
        if rollover not in ("next", "backlog"):
            raise ValidationError("rollover must be 'next' or 'backlog'")
        now = self._clock.now()
        next_sprint: Sprint | None = None
        if rollover == "next":
            with self._uow() as uow:
                s = self._require(uow, sprint_id)
                planned = sorted(
                    (o for o in uow.sprints.find() if o.status == SprintStatus.PLANNED),
                    key=lambda o: o.start_date,
                )
            next_sprint = planned[0] if planned else None
            if next_sprint is None:
                start = max(self._clock.today(), s.end_date + timedelta(days=1))
                next_sprint = self.create(start_date=start)
        moved = 0
        with self._uow() as uow:
            s = self._require(uow, sprint_id)
            if s.status == SprintStatus.COMPLETED:
                raise ConflictError("sprint already completed")
            for t in uow.tasks.find(
                TaskQuery(sprint_id=sprint_id, top_level_only=True, limit=1000)
            ):
                if t.status == TaskStatus.DONE:
                    continue
                moved += 1
                self._record_scope(uow, s.id, t, "remove", now, after_start=False)
                if next_sprint is not None:
                    self._record_scope(uow, next_sprint.id, t, "add", now, t.commitment)
                    t.sprint_id = next_sprint.id
                else:
                    t.sprint_id = None
                    t.commitment = None
                t.updated_at = now
                uow.tasks.update(t)
            s.status = SprintStatus.COMPLETED
            s.completed_at = now
            s.review_summary = summary or s.review_summary
            s.review_lessons = lessons or s.review_lessons
            s.updated_at = now
            uow.sprints.update(s)
            uow.audit.record(
                "sprint", s.id, "complete", details={"rolled_over": moved, "to": rollover}
            )
            uow.commit()
        return s, next_sprint, moved

    def delete(self, sprint_id: str) -> None:
        with self._uow() as uow:
            s = self._require(uow, sprint_id)
            if s.status != SprintStatus.PLANNED:
                raise ConflictError("only planned sprints can be deleted")
            for t in uow.tasks.find(TaskQuery(sprint_id=sprint_id, limit=1000)):
                t.sprint_id = None
                t.commitment = None
                uow.tasks.update(t)
            uow.sprints.delete(sprint_id)
            uow.commit()

    @staticmethod
    def _record_scope(
        uow: UnitOfWork,
        sprint_id: str,
        t: Task,
        action: str,
        at: datetime,
        commitment: str | None = None,
        after_start: bool = False,
    ) -> None:
        uow.sprints.add_scope_event(
            ScopeEvent(sprint_id, t.id, action, commitment, after_start, at)
        )

    @staticmethod
    def _require(uow: UnitOfWork, sprint_id: str) -> Sprint:
        s = uow.sprints.get(sprint_id)
        if s is None:
            raise NotFoundError("sprint", sprint_id)
        return s


@dataclass
class WeekDay:
    day: date
    tasks: list[Task]
    time: DayTime
    capacity_minutes: int
    planned_minutes: int
    meetings: list[Meeting]


@dataclass
class WeekView:
    week_start: date
    plan: WeeklyPlan
    days: list[WeekDay]
    sprint: Sprint | None
    sprint_backlog: list[Task]
    series: dict[str, MeetingSeries] = field(default_factory=dict)


@dataclass
class WeekReview:
    week_start: date
    planned: int
    done: int
    open: int
    done_titles: list[str]
    open_titles: list[str]
    estimate_minutes: int
    actual_minutes: int
    meeting_minutes: int
    available_minutes: int
    work_minutes: int
    objectives: list[WeeklyObjective]


class WeekService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        settings: SettingsService,
        meetings: MeetingService,
        sprints: SprintService,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._settings = settings
        self._meetings = meetings
        self._sprints = sprints

    def view(self, any_day: date | None = None) -> WeekView:
        week_start = monday_of(any_day or self._clock.today())
        week_end = week_start + timedelta(days=6)
        settings = self._settings.get()
        meetings, series = self._meetings.between(week_start, week_end)
        with self._uow() as uow:
            plan = uow.weeks.get(week_start) or WeeklyPlan(week_start=week_start)
            tasks = uow.tasks.find(
                TaskQuery(
                    scheduled_from=week_start,
                    scheduled_to=week_end,
                    top_level_only=True,
                    limit=2000,
                )
            )
            plans: dict[date, DailyPlan | None] = {
                week_start + timedelta(days=i): uow.days.get(week_start + timedelta(days=i))
                for i in range(7)
            }
        sprint = self._sprint_for(week_start, week_end)
        backlog: list[Task] = []
        if sprint:
            with self._uow() as uow:
                backlog = [
                    t
                    for t in uow.tasks.find(
                        TaskQuery(sprint_id=sprint.id, top_level_only=True, limit=1000)
                    )
                    if t.status != TaskStatus.DONE and t.scheduled_date is None
                ]
        days: list[WeekDay] = []
        tz = settings.tz
        for i in range(7):
            d = week_start + timedelta(days=i)
            dt = day_time(d, meetings, series, settings)
            p = plans[d]
            cap = (
                p.capacity_minutes
                if p is not None and p.capacity_mode == "manual"
                else dt.capacity_minutes
            )
            day_tasks = [t for t in tasks if t.scheduled_date == d]
            planned = sum(
                (
                    t.estimate_minutes
                    if t.estimate_minutes is not None
                    else settings.default_task_minutes
                )
                for t in day_tasks
                if t.status != TaskStatus.DONE
            )
            day_meetings = [m for m in meetings if m.start_at.astimezone(tz).date() == d]
            days.append(
                WeekDay(
                    d,
                    sorted(day_tasks, key=lambda t: (t.status == TaskStatus.DONE, t.position)),
                    dt,
                    cap,
                    planned,
                    day_meetings,
                )
            )
        return WeekView(week_start, plan, days, sprint, backlog, series)

    def update_plan(self, week_start: date, changes: Mapping[str, Any]) -> WeeklyPlan:
        allowed = {
            "objectives",
            "notes",
            "review_wins",
            "review_lessons",
            "review_risks",
            "review_next_focus",
        }
        unknown = set(changes) - allowed - {"complete_review"}
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        week_start = monday_of(week_start)
        with self._uow() as uow:
            plan = uow.weeks.get(week_start) or WeeklyPlan(week_start=week_start)
            for k, v in changes.items():
                if k == "objectives":
                    plan.objectives = [
                        WeeklyObjective(
                            text=str(o["text"]),
                            done=bool(o.get("done", False)),
                            emoji=o.get("emoji") or None,
                        )
                        for o in v
                    ]
                elif k in allowed:
                    setattr(plan, k, v)
            if changes.get("complete_review"):
                plan.review_completed_at = self._clock.now()
            plan.updated_at = self._clock.now()
            WeeklyPlan.__post_init__(plan)
            uow.weeks.upsert(plan)
            uow.audit.record(
                "week", week_start.isoformat(), "update", details={"fields": sorted(changes)}
            )
            uow.commit()
            return plan

    def review(self, any_day: date) -> WeekReview:
        view = self.view(any_day)
        tasks = [t for d in view.days for t in d.tasks]
        done = [t for t in tasks if t.status == TaskStatus.DONE]
        open_ = [t for t in tasks if t.status != TaskStatus.DONE]
        return WeekReview(
            week_start=view.week_start,
            planned=len(tasks),
            done=len(done),
            open=len(open_),
            done_titles=[t.title for t in done],
            open_titles=[t.title for t in open_],
            estimate_minutes=sum(t.estimate_minutes or 0 for t in done),
            actual_minutes=sum(t.actual_minutes for t in done),
            meeting_minutes=sum(d.time.meeting_minutes_total for d in view.days),
            available_minutes=sum(d.time.available_minutes for d in view.days),
            work_minutes=sum(d.time.work_minutes for d in view.days),
            objectives=view.plan.objectives,
        )

    def roll_over(self, any_day: date, to_week_start: date | None = None) -> int:
        """Move unfinished tasks of a week to the Monday of the next week."""
        week_start = monday_of(any_day)
        target = to_week_start or week_start + timedelta(days=7)
        now = self._clock.now()
        moved = 0
        with self._uow() as uow:
            for t in uow.tasks.find(
                TaskQuery(
                    scheduled_from=week_start,
                    scheduled_to=week_start + timedelta(days=6),
                    limit=2000,
                )
            ):
                if t.status == TaskStatus.DONE:
                    continue
                t.scheduled_date = target
                if t.status == TaskStatus.IN_PROGRESS:
                    t.status = TaskStatus.PLANNED
                t.updated_at = now
                uow.tasks.update(t)
                moved += 1
            uow.commit()
        return moved

    def _sprint_for(self, start: date, end: date) -> Sprint | None:
        sprints = [s for s in self._sprints.find() if s.status != SprintStatus.COMPLETED]
        overlapping = [s for s in sprints if s.start_date <= end and start <= s.end_date]
        active = [s for s in overlapping if s.status == SprintStatus.ACTIVE]
        candidates = active or overlapping
        return candidates[0] if candidates else None
