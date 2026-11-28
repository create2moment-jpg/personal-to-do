"""Month overview for the calendar gadget: what each day holds, counted."""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, tzinfo

from ppos.application.meetings import MeetingService
from ppos.application.ports import TaskQuery
from ppos.application.tasks import TaskService
from ppos.domain.meetings import Attendance
from ppos.domain.tasks import TaskStatus
from ppos.shared.errors import ValidationError


@dataclass(frozen=True)
class DayMarks:
    day: date
    meetings: int  # attended meetings and calls starting that day
    planned: int  # open tasks scheduled that day
    due: int  # open tasks due that day
    done: int  # tasks completed that day


def month_marks(
    month: str, tasks: TaskService, meetings: MeetingService, tz: Callable[[], tzinfo]
) -> list[DayMarks]:
    try:
        year, mon = (int(x) for x in month.split("-"))
        first = date(year, mon, 1)
    except ValueError as exc:
        raise ValidationError("month must look like 2026-11") from exc
    last = date(year, mon, calendar.monthrange(year, mon)[1])
    counts: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    found, series = meetings.between(first, last)
    zone = tz()
    for m in found:
        if m.cancelled:
            continue
        if m.effective_status(series.get(m.series_key or "")) == Attendance.SKIPPED:
            continue
        counts[m.start_at.astimezone(zone).date()]["meetings"] += 1
    for t in tasks.find(TaskQuery(scheduled_from=first, scheduled_to=last, limit=5000)):
        if t.status != TaskStatus.DONE and t.scheduled_date:
            counts[t.scheduled_date]["planned"] += 1
    for t in tasks.find(TaskQuery(limit=5000)):
        if t.status != TaskStatus.DONE and t.due_date and first <= t.due_date <= last:
            counts[t.due_date]["due"] += 1
        if t.completed_at is not None:
            d = t.completed_at.astimezone(zone).date()
            if first <= d <= last:
                counts[d]["done"] += 1
    return [
        DayMarks(d, c["meetings"], c["planned"], c["due"], c["done"])
        for d, c in sorted(counts.items())
        if first <= d <= last
    ]
