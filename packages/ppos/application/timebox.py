"""Day timeline: working hours, meetings, timeboxed tasks and the free time between.

"Fill my free time" is a deterministic proposal (most important first, first
fit, never split); nothing changes until the user applies it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from ppos.application.daily import DayService
from ppos.application.ports import TaskQuery
from ppos.application.tasks import TaskService
from ppos.domain.meetings import Attendance, Meeting, MeetingSeries
from ppos.domain.settings import WorkspaceSettings
from ppos.domain.tasks import Task, TaskStatus
from ppos.domain.timebox import Placement, Span, free_slots, propose, to_hhmm, to_minutes
from ppos.shared.clock import Clock

DayMeetings = Callable[[date], tuple[list[Meeting], dict[str, MeetingSeries]]]


@dataclass(frozen=True)
class MeetingBlock:
    meeting: Meeting
    span: Span
    attending: bool


@dataclass(frozen=True)
class TaskBlock:
    task: Task
    span: Span


@dataclass
class Timeline:
    day: date
    window: Span | None  # working hours; None on a non-working day
    meetings: list[MeetingBlock] = field(default_factory=list)
    boxes: list[TaskBlock] = field(default_factory=list)
    free: list[Span] = field(default_factory=list)
    unboxed: list[Task] = field(default_factory=list)  # open tasks on the day, no start yet
    default_minutes: int = 30

    @property
    def free_minutes(self) -> int:
        return sum(s.minutes for s in self.free)


@dataclass(frozen=True)
class Proposal:
    day: date
    placements: list[tuple[Task, Placement]]
    unplaced: list[Task]


class TimelineService:
    def __init__(
        self,
        clock: Clock,
        tasks: TaskService,
        days: DayService,
        day_meetings: DayMeetings,
        settings: Callable[[], WorkspaceSettings],
    ) -> None:
        self._clock = clock
        self._tasks = tasks
        self._days = days
        self._day_meetings = day_meetings
        self._settings = settings

    def _minutes(self, t: Task, default: int) -> int:
        return max(5, t.estimate_minutes or default)

    def timeline(self, day: date) -> Timeline:
        ws = self._settings()
        default = ws.default_task_minutes
        window = None
        if day.weekday() in ws.workdays:
            window = Span(_mins(ws.start_time), _mins(ws.end_time))
        found, series = self._day_meetings(day)
        midnight = datetime.combine(day, time(0), tzinfo=ws.tz)
        blocks = []
        for m in found:
            if m.all_day or m.cancelled:
                continue
            start = int((m.start_at.astimezone(ws.tz) - midnight) / timedelta(minutes=1))
            end = int((m.end_at.astimezone(ws.tz) - midnight) / timedelta(minutes=1))
            span = Span(max(0, start), min(24 * 60, end))
            if span.minutes > 0:
                status = m.effective_status(series.get(m.series_key or ""))
                blocks.append(MeetingBlock(m, span, status != Attendance.SKIPPED))
        blocks.sort(key=lambda b: b.span.start)
        boxes, unboxed = [], []
        for t in self._tasks.find(TaskQuery(scheduled_date=day, limit=500)):
            if t.timebox_start:
                start = to_minutes(t.timebox_start)
                boxes.append(
                    TaskBlock(t, Span(start, min(24 * 60, start + self._minutes(t, default))))
                )
            elif t.status != TaskStatus.DONE:
                unboxed.append(t)
        boxes.sort(key=lambda b: b.span.start)
        busy = [b.span for b in blocks if b.attending] + [b.span for b in boxes]
        return Timeline(day, window, blocks, boxes, free_slots(window, busy), unboxed, default)

    def propose(self, day: date) -> Proposal:
        tl = self.timeline(day)
        top = self._days.plan_for(day).top_priority_ids
        rank = {tid: i for i, tid in enumerate(top)}
        order = sorted(
            tl.unboxed,
            key=lambda t: (
                rank.get(t.id, len(rank)),
                t.status != TaskStatus.IN_PROGRESS,
                int(t.priority),
                t.position,
            ),
        )
        now = self._clock.now().astimezone(self._settings().tz)
        not_before = now.hour * 60 + now.minute if day == now.date() else 0
        placed, unplaced = propose(
            [(t.id, self._minutes(t, tl.default_minutes)) for t in order], tl.free, not_before
        )
        by_id = {t.id: t for t in order}
        return Proposal(day, [(by_id[p.task_id], p) for p in placed], [by_id[i] for i in unplaced])

    def apply(self, day: date, items: list[tuple[str, str | None]]) -> list[Task]:
        return self._tasks.timebox_many(day, items)


def _mins(t: time) -> int:
    return t.hour * 60 + t.minute


__all__ = ["Proposal", "Timeline", "TimelineService", "to_hhmm"]
