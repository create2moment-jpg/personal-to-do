"""Agentic workflows: multi-step helpers that *propose*, never act on their own.

A workflow reads your records and returns a run: a checklist of actions drawn
from a fixed allow-list. Nothing changes until you apply the actions you keep;
applying goes through the same services (and rules) as the rest of the app.
Runs are stored, so what was proposed and what was applied stays auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from ppos.shared.errors import ValidationError

WORKFLOWS = {
    "plan_week": "Plan my week",
    "week_review": "Prepare my weekly review",
    "evidence_pack": "Build a promotion evidence pack",
}
# The only things a workflow may propose. Each maps to an existing service call.
ACTION_KINDS = frozenset(
    {
        "schedule_task",  # {task_id, day}
        "set_objectives",  # {week_start, objectives: [str]}
        "set_week_review",  # {week_start, fields: {review_*: str}}
        "link_evidence",  # {expectation_id, fact_id}
        "gap_task",  # {expectation_id}
        "evidence_note",  # {level}
    }
)
RUN_STATUSES = ("proposed", "applied", "dismissed")


@dataclass
class Action:
    id: str
    kind: str
    label: str
    params: dict[str, Any]
    detail: str = ""  # why it is proposed (grounded in your records)
    selected: bool = True  # pre-ticked in the checklist
    outcome: str | None = None  # applied | skipped | failed: reason

    def __post_init__(self) -> None:
        if self.kind not in ACTION_KINDS:
            raise ValidationError(f"unknown workflow action {self.kind!r}")


@dataclass
class WorkflowRun:
    id: str
    workflow: str
    created_at: datetime
    title: str
    summary: str
    actions: list[Action] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)  # warnings, things left out and why
    status: str = "proposed"
    applied_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.workflow not in WORKFLOWS:
            raise ValidationError(f"unknown workflow {self.workflow!r}")
        if self.status not in RUN_STATUSES:
            raise ValidationError(f"invalid run status {self.status!r}")


@dataclass(frozen=True)
class Candidate:
    task_id: str
    minutes: int
    latest: date | None  # due date (a placement must not be later)


def fit_week(
    candidates: list[Candidate], free: dict[date, int]
) -> tuple[list[tuple[str, date]], list[str]]:
    """Earliest day with enough remaining capacity, never after the due date.

    ``candidates`` come most important first; ``free`` is remaining minutes per
    day (only the days that may receive work). Returns placements and the ids
    that fit nowhere — those are reported, never squeezed in.
    """
    left = dict(free)
    placed: list[tuple[str, date]] = []
    unplaced: list[str] = []
    for c in candidates:
        days = sorted(d for d in left if c.latest is None or d <= c.latest)
        day = next((d for d in days if left[d] >= c.minutes), None)
        if day is None:
            unplaced.append(c.task_id)
            continue
        left[day] -= c.minutes
        placed.append((c.task_id, day))
    return placed, unplaced
