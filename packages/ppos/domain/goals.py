"""Goals: a year → quarter → month hierarchy with computed, explainable progress."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ppos.shared.errors import ValidationError

HORIZONS = ("year", "quarter", "month")
STATUSES = ("active", "achieved", "paused", "dropped")
PROGRESS_MODES = ("auto", "manual", "metric")
_RANK = {"year": 0, "quarter": 1, "month": 2}


def period_of(horizon: str, day: date) -> str:
    if horizon == "year":
        return f"{day.year}"
    if horizon == "quarter":
        return f"{day.year}-Q{(day.month - 1) // 3 + 1}"
    if horizon == "month":
        return f"{day.year}-{day.month:02d}"
    raise ValidationError(f"horizon must be one of {', '.join(HORIZONS)}")


def period_bounds(horizon: str, period: str) -> tuple[date, date]:
    """First and last day of a period such as '2026', '2026-Q4' or '2026-11'."""
    patterns = {
        "year": r"(\d{4})",
        "quarter": r"(\d{4})-Q([1-4])",
        "month": r"(\d{4})-(0[1-9]|1[0-2])",
    }
    if horizon not in patterns:
        raise ValidationError(f"horizon must be one of {', '.join(HORIZONS)}")
    m = re.fullmatch(patterns[horizon], period)
    if not m:
        example = {"year": "2026", "quarter": "2026-Q4", "month": "2026-11"}[horizon]
        raise ValidationError(f"{horizon} period must look like {example}")
    year = int(m.group(1))
    if horizon == "year":
        return date(year, 1, 1), date(year, 12, 31)
    first_month = (int(m.group(2)) - 1) * 3 + 1 if horizon == "quarter" else int(m.group(2))
    months = 3 if horizon == "quarter" else 1
    start = date(year, first_month, 1)
    nm = first_month + months
    end = (date(year + 1, 1, 1) if nm > 12 else date(year, nm, 1)) - timedelta(days=1)
    return start, end


@dataclass
class Goal:
    id: str
    title: str
    horizon: str
    period: str
    created_at: datetime
    updated_at: datetime
    description: str = ""
    parent_id: str | None = None
    status: str = "active"
    progress_mode: str = "auto"
    manual_progress: int | None = None
    metric_unit: str | None = None
    metric_start: float | None = None
    metric_target: float | None = None
    metric_current: float | None = None
    emoji: str | None = None
    position: float = 0.0
    achieved_at: datetime | None = None

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split())
        if not self.title:
            raise ValidationError("a goal needs a title")
        if len(self.title) > 300:
            raise ValidationError("goal title must be at most 300 characters")
        period_bounds(self.horizon, self.period)  # validates both
        if self.status not in STATUSES:
            raise ValidationError(f"status must be one of {', '.join(STATUSES)}")
        if self.progress_mode not in PROGRESS_MODES:
            raise ValidationError(f"progress must be one of {', '.join(PROGRESS_MODES)}")
        if self.manual_progress is not None and not 0 <= self.manual_progress <= 100:
            raise ValidationError("manual progress must be 0–100")
        if self.progress_mode == "metric" and self.metric_target is None:
            raise ValidationError("a measurable goal needs a target value")
        if self.metric_target is not None and self.metric_target == (self.metric_start or 0):
            raise ValidationError("target must differ from the starting value")

    @property
    def bounds(self) -> tuple[date, date]:
        return period_bounds(self.horizon, self.period)


def check_parent(child: Goal, parent: Goal) -> None:
    """A sub-goal has a shorter horizon and lies within its parent's period."""
    if _RANK[child.horizon] <= _RANK[parent.horizon]:
        raise ValidationError(f"a {child.horizon} goal cannot sit under a {parent.horizon} goal")
    (cs, ce), (ps, pe) = child.bounds, parent.bounds
    if cs < ps or ce > pe:
        raise ValidationError(f"{child.period} is outside the parent goal's period {parent.period}")


@dataclass(frozen=True)
class Progress:
    value: float | None  # 0..1, None = nothing to measure yet
    basis: str  # how it was computed, shown to the user
    done: int = 0
    total: int = 0


def own_progress(goal: Goal, done: int, total: int) -> Progress | None:
    """Progress from the goal itself (manual / metric / its tasks); None → use sub-goals."""
    if goal.status == "achieved":
        return Progress(1.0, "marked achieved", done, total)
    if goal.progress_mode == "manual":
        v = (goal.manual_progress or 0) / 100
        return Progress(v, "set by you", done, total)
    if goal.progress_mode == "metric":
        start, target = goal.metric_start or 0.0, goal.metric_target or 0.0
        current = goal.metric_current if goal.metric_current is not None else start
        v = max(0.0, min(1.0, (current - start) / (target - start)))
        unit = f" {goal.metric_unit}" if goal.metric_unit else ""
        return Progress(v, f"{_num(current)} of {_num(target)}{unit}", done, total)
    if total:
        return Progress(done / total, f"{done} of {total} tasks done", done, total)
    return None


def combine(goal: Goal, own: Progress | None, children: list[Progress]) -> Progress:
    if own is not None:
        return own
    measured = [c.value for c in children if c.value is not None]
    if measured:
        return Progress(sum(measured) / len(measured), f"average of {len(measured)} sub-goals")
    return Progress(None, "add tasks or sub-goals to measure progress")


def pace(goal: Goal, progress: Progress, today: date) -> str:
    """ahead / on track / behind / not started / upcoming / ended — a hint, not a verdict."""
    start, end = goal.bounds
    if goal.status in ("achieved", "dropped", "paused"):
        return goal.status
    if today < start:
        return "upcoming"
    if progress.value is None:
        return "not started" if today <= end else "ended"
    if today > end:
        return "ended"
    elapsed = ((today - start).days + 1) / ((end - start).days + 1)
    if progress.value >= elapsed + 0.1:
        return "ahead"
    if progress.value >= elapsed - 0.15:
        return "on track"
    return "behind"


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else f"{x:g}"
