"""Timeboxing: the day timeline, start times for tasks, and "fill my free time"."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ppos.application.timebox import Timeline
from ppos.domain.timebox import Span, to_hhmm
from ppos_api.deps import ContainerDep
from ppos_api.schemas import TaskOut

router = APIRouter(tags=["timebox"])


class SpanOut(BaseModel):
    start: str
    end: str
    minutes: int


def _span(s: Span) -> SpanOut:
    return SpanOut(start=to_hhmm(s.start), end=to_hhmm(s.end), minutes=s.minutes)


class MeetingBlockOut(SpanOut):
    id: str
    title: str
    kind: str
    attending: bool


class TaskBlockOut(SpanOut):
    task: TaskOut


class TimelineOut(BaseModel):
    day: date
    window: SpanOut | None
    meetings: list[MeetingBlockOut]
    boxes: list[TaskBlockOut]
    free: list[SpanOut]
    unboxed: list[TaskOut]
    free_minutes: int
    default_minutes: int


def _task(t: object) -> TaskOut:
    return TaskOut.model_validate(t)


def timeline_out(tl: Timeline) -> TimelineOut:
    return TimelineOut(
        day=tl.day,
        window=_span(tl.window) if tl.window else None,
        meetings=[
            MeetingBlockOut(
                **_span(b.span).model_dump(),
                id=b.meeting.id,
                title=b.meeting.title,
                kind=b.meeting.kind.value,
                attending=b.attending,
            )
            for b in tl.meetings
        ],
        boxes=[TaskBlockOut(**_span(b.span).model_dump(), task=_task(b.task)) for b in tl.boxes],
        free=[_span(s) for s in tl.free],
        unboxed=[_task(t) for t in tl.unboxed],
        free_minutes=tl.free_minutes,
        default_minutes=tl.default_minutes,
    )


@router.get("/api/days/{day}/timeline", response_model=TimelineOut)
def timeline(day: date, c: ContainerDep) -> TimelineOut:
    return timeline_out(c.timeline.timeline(day))


class TimeboxIn(BaseModel):
    day: date
    start: str | None = Field(default=None, max_length=5)


@router.put("/api/tasks/{task_id}/timebox", response_model=TaskOut)
def set_timebox(task_id: str, body: TimeboxIn, c: ContainerDep) -> TaskOut:
    return _task(c.tasks.timebox(task_id, body.day, body.start))


class ProposalOut(BaseModel):
    day: date
    placements: list[TaskBlockOut]
    unplaced: list[TaskOut]


@router.post("/api/days/{day}/timebox/propose", response_model=ProposalOut)
def propose(day: date, c: ContainerDep) -> ProposalOut:
    """A deterministic proposal; nothing is saved."""
    p = c.timeline.propose(day)
    return ProposalOut(
        day=p.day,
        placements=[
            TaskBlockOut(**_span(Span(pl.start, pl.start + pl.minutes)).model_dump(), task=_task(t))
            for t, pl in p.placements
        ],
        unplaced=[_task(t) for t in p.unplaced],
    )


class ApplyItem(BaseModel):
    task_id: str
    start: str | None = Field(default=None, max_length=5)


class ApplyIn(BaseModel):
    items: list[ApplyItem] = Field(max_length=100)


@router.post("/api/days/{day}/timebox/apply", response_model=list[TaskOut])
def apply(day: date, body: ApplyIn, c: ContainerDep) -> list[TaskOut]:
    tasks = c.timeline.apply(day, [(i.task_id, i.start) for i in body.items])
    return [_task(t) for t in tasks]
