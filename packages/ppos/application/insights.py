"""Insights: week-by-week trends computed from your own records (no AI)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from ppos.application.meetings import MeetingService
from ppos.application.ports import TaskQuery, UnitOfWorkFactory
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import Clock
from ppos.shared.errors import ValidationError


@dataclass(frozen=True)
class WeekStat:
    week_start: date
    tasks_done: int
    done_estimate: int
    actual_minutes: int
    accuracy: float | None  # logged ÷ estimate on tasks that have both
    planned: int  # top-level tasks scheduled in the week
    planned_done: int
    meeting_minutes: int
    work_minutes: int
    available_minutes: int

    @property
    def reliability(self) -> float | None:
        return round(self.planned_done / self.planned, 3) if self.planned else None


@dataclass(frozen=True)
class Trends:
    weeks: list[WeekStat]
    by_project: list[tuple[str, int, int]]  # name, minutes, count
    by_topic: list[tuple[str, int, int]]
    by_person: list[tuple[str, int, int]]


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class InsightsService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, meetings: MeetingService) -> None:
        self._uow = uow
        self._clock = clock
        self._meetings = meetings

    def trends(self, weeks: int = 12) -> Trends:
        if not 2 <= weeks <= 52:
            raise ValidationError("weeks must be between 2 and 52")
        today = self._clock.today()
        last = _monday(today)
        first = last - timedelta(weeks=weeks - 1)
        end = last + timedelta(days=6)
        frm = datetime.combine(first, time.min, tzinfo=timezone.utc)
        to = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
        with self._uow() as uow:
            done = uow.tasks.find(
                TaskQuery(
                    statuses=(TaskStatus.DONE,),
                    completed_from=frm,
                    completed_to=to,
                    top_level_only=True,
                    limit=10000,
                )
            )
            planned = uow.tasks.find(
                TaskQuery(scheduled_from=first, scheduled_to=end, top_level_only=True, limit=10000)
            )
            projects = {p.id: p.name for p in uow.projects.find()}
        ins = self._meetings.insights(first, min(end, today))

        acc: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for t in done:
            assert t.completed_at is not None
            w = _monday(t.completed_at.date())
            acc[w]["done"] += 1
            acc[w]["est"] += t.estimate_minutes or 0
            acc[w]["actual"] += t.actual_minutes
            if t.estimate_minutes and t.actual_minutes:
                acc[w]["both_est"] += t.estimate_minutes
                acc[w]["both_actual"] += t.actual_minutes
        for t in planned:
            # a day that isn't over yet can't count against you (unless it's already done)
            if t.scheduled_date is None or (
                t.scheduled_date >= today and t.status != TaskStatus.DONE
            ):
                continue
            w = _monday(t.scheduled_date)
            acc[w]["planned"] += 1
            acc[w]["planned_done"] += t.status == TaskStatus.DONE
        for d in ins.days:
            w = _monday(d.day)
            acc[w]["meet"] += d.meeting_minutes
            acc[w]["work"] += d.work_minutes
            acc[w]["avail"] += d.available_minutes

        stats = []
        for i in range(weeks):
            w = first + timedelta(weeks=i)
            a = acc[w]
            stats.append(
                WeekStat(
                    week_start=w,
                    tasks_done=a["done"],
                    done_estimate=a["est"],
                    actual_minutes=a["actual"],
                    accuracy=round(a["both_actual"] / a["both_est"], 3) if a["both_est"] else None,
                    planned=a["planned"],
                    planned_done=a["planned_done"],
                    meeting_minutes=a["meet"],
                    work_minutes=a["work"],
                    available_minutes=a["avail"],
                )
            )
        by_project: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for t in done:
            name = projects.get(t.project_id or "", "No project")
            by_project[name][0] += t.actual_minutes or t.estimate_minutes or 0
            by_project[name][1] += 1
        ranked = sorted(
            ((n, m, c) for n, (m, c) in by_project.items()), key=lambda x: (-x[1], x[0])
        )
        return Trends(stats, ranked, ins.by_topic[:8], ins.by_person[:8])
