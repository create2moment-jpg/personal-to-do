"""Goals API: year → quarter → month goals with computed progress."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ppos.application.goals import GoalNode
from ppos_api.deps import ContainerDep
from ppos_api.schemas import TaskOut

router = APIRouter(prefix="/api/goals", tags=["goals"])

Horizon = Literal["year", "quarter", "month"]
Status = Literal["active", "achieved", "paused", "dropped"]
Mode = Literal["auto", "manual", "metric"]


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str
    horizon: str
    period: str
    parent_id: str | None
    status: str
    progress_mode: str
    manual_progress: int | None
    metric_unit: str | None
    metric_start: float | None
    metric_target: float | None
    metric_current: float | None
    emoji: str | None
    position: float
    created_at: datetime
    updated_at: datetime
    achieved_at: datetime | None


class ProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    value: float | None
    basis: str
    done: int
    total: int


class NodeOut(BaseModel):
    goal: GoalOut
    progress: ProgressOut
    pace: str
    period_start: date
    period_end: date
    expectation_ids: list[str]
    project_ids: list[str]
    skill_ids: list[str]
    children: list[NodeOut]


class TreeOut(BaseModel):
    year: int
    roots: list[NodeOut]


class GoalIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    horizon: Horizon
    period: str | None = Field(default=None, max_length=10)
    description: str = Field(default="", max_length=5000)
    parent_id: str | None = None
    progress_mode: Mode = "auto"
    manual_progress: int | None = Field(default=None, ge=0, le=100)
    metric_unit: str | None = Field(default=None, max_length=40)
    metric_start: float | None = None
    metric_target: float | None = None
    metric_current: float | None = None
    emoji: str | None = Field(default=None, max_length=8)


class GoalPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    horizon: Horizon | None = None
    period: str | None = Field(default=None, max_length=10)
    description: str | None = Field(default=None, max_length=5000)
    parent_id: str | None = None
    status: Status | None = None
    progress_mode: Mode | None = None
    manual_progress: int | None = Field(default=None, ge=0, le=100)
    metric_unit: str | None = Field(default=None, max_length=40)
    metric_start: float | None = None
    metric_target: float | None = None
    metric_current: float | None = None
    emoji: str | None = Field(default=None, max_length=8)
    position: float | None = None


class LinkIn(BaseModel):
    id: str


class GoalTaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    estimate_minutes: int | None = Field(default=None, ge=1, le=24 * 60)


def node_out(n: GoalNode) -> NodeOut:
    start, end = n.goal.bounds
    return NodeOut(
        goal=GoalOut.model_validate(n.goal),
        progress=ProgressOut.model_validate(n.progress),
        pace=n.pace,
        period_start=start,
        period_end=end,
        expectation_ids=n.expectation_ids,
        project_ids=n.project_ids,
        skill_ids=n.skill_ids,
        children=[node_out(c) for c in n.children],
    )


@router.get("", response_model=TreeOut)
def tree(c: ContainerDep, year: int | None = None) -> TreeOut:
    t = c.goals.tree(year)
    return TreeOut(year=t.year, roots=[node_out(n) for n in t.roots])


@router.get("/flat", response_model=list[GoalOut])
def flat(c: ContainerDep) -> list[GoalOut]:
    """All goals (any year), for pickers such as the task panel."""
    return [GoalOut.model_validate(n.goal) for n in c.goals.all_nodes().values()]


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create(body: GoalIn, c: ContainerDep) -> GoalOut:
    fields = body.model_dump(exclude={"title", "horizon", "period"}, exclude_none=True)
    return GoalOut.model_validate(c.goals.create(body.title, body.horizon, body.period, **fields))


@router.patch("/{goal_id}", response_model=GoalOut)
def update(goal_id: str, body: GoalPatch, c: ContainerDep) -> GoalOut:
    return GoalOut.model_validate(c.goals.update(goal_id, body.model_dump(exclude_unset=True)))


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(goal_id: str, c: ContainerDep) -> Response:
    c.goals.delete(goal_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{goal_id}/tasks", response_model=list[TaskOut])
def tasks(goal_id: str, c: ContainerDep) -> list[TaskOut]:
    return [TaskOut.model_validate(t) for t in c.goals.tasks_of(goal_id)]


@router.post("/{goal_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def add_task(goal_id: str, body: GoalTaskIn, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(c.goals.add_task(goal_id, body.title, body.estimate_minutes))


@router.post("/{goal_id}/{kind}s", status_code=status.HTTP_204_NO_CONTENT)
def link(
    goal_id: str, kind: Literal["expectation", "project", "skill"], body: LinkIn, c: ContainerDep
) -> Response:
    c.goals.link(goal_id, kind, body.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{goal_id}/{kind}s/{other_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink(
    goal_id: str, kind: Literal["expectation", "project", "skill"], other_id: str, c: ContainerDep
) -> Response:
    c.goals.link(goal_id, kind, other_id, on=False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
