"""Sprints and weeks."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Response, status

from ppos.domain.planning import Commitment, Sprint
from ppos_api.deps import ContainerDep
from ppos_api.schemas import (
    BurndownPointOut,
    SprintComplete,
    SprintCompleteOut,
    SprintCreate,
    SprintOut,
    SprintSummaryOut,
    SprintTasksAdd,
    SprintUpdate,
    TaskOut,
    WeekDayOut,
    WeeklyObjectiveOut,
    WeeklyPlanOut,
    WeeklyPlanUpdate,
    WeekOut,
    WeekReviewOut,
)
from ppos_api.serializers import MeetingSerializer, day_time_out

router = APIRouter(tags=["planning"])


def sprint_out(s: Sprint) -> SprintOut:
    return SprintOut(
        id=s.id,
        name=s.name,
        goal=s.goal,
        start_date=s.start_date,
        end_date=s.end_date,
        status=s.status.value,
        review_summary=s.review_summary,
        review_lessons=s.review_lessons,
        completed_at=s.completed_at,
    )


@router.get("/api/sprints", response_model=list[SprintOut])
def list_sprints(c: ContainerDep) -> list[SprintOut]:
    return [sprint_out(s) for s in c.sprints.find()]


@router.get("/api/sprints/current", response_model=SprintOut | None)
def current_sprint(c: ContainerDep) -> SprintOut | None:
    s = c.sprints.current()
    return sprint_out(s) if s else None


@router.post("/api/sprints", response_model=SprintOut, status_code=status.HTTP_201_CREATED)
def create_sprint(body: SprintCreate, c: ContainerDep) -> SprintOut:
    return sprint_out(c.sprints.create(body.name, body.goal, body.start_date, body.end_date))


@router.patch("/api/sprints/{sprint_id}", response_model=SprintOut)
def update_sprint(sprint_id: str, body: SprintUpdate, c: ContainerDep) -> SprintOut:
    return sprint_out(c.sprints.update(sprint_id, body.model_dump(exclude_unset=True)))


@router.delete("/api/sprints/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sprint(sprint_id: str, c: ContainerDep) -> Response:
    c.sprints.delete(sprint_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/sprints/{sprint_id}/start", response_model=SprintOut)
def start_sprint(sprint_id: str, c: ContainerDep) -> SprintOut:
    return sprint_out(c.sprints.start(sprint_id))


@router.get("/api/sprints/{sprint_id}/summary", response_model=SprintSummaryOut)
def sprint_summary(sprint_id: str, c: ContainerDep) -> SprintSummaryOut:
    s = c.sprints.summary(sprint_id)
    return SprintSummaryOut(
        sprint=sprint_out(s.sprint),
        tasks=[TaskOut.model_validate(t) for t in s.tasks],
        committed_total=s.committed_total,
        committed_done=s.committed_done,
        stretch_total=s.stretch_total,
        stretch_done=s.stretch_done,
        committed_minutes=s.committed_minutes,
        remaining_minutes=s.remaining_minutes,
        added_after_start=s.added_after_start,
        removed_after_start=s.removed_after_start,
        burndown=[BurndownPointOut(**p.__dict__) for p in s.burndown],
        days_total=s.days_total,
        days_elapsed=s.days_elapsed,
        completion_rate=round(s.completion_rate, 3),
    )


@router.post("/api/sprints/{sprint_id}/tasks", response_model=list[TaskOut])
def add_sprint_tasks(sprint_id: str, body: SprintTasksAdd, c: ContainerDep) -> list[TaskOut]:
    tasks = c.sprints.add_tasks(sprint_id, body.task_ids, Commitment(body.commitment))
    return [TaskOut.model_validate(t) for t in tasks]


@router.delete("/api/sprints/tasks/{task_id}", response_model=TaskOut)
def remove_sprint_task(task_id: str, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(c.sprints.remove_task(task_id))


@router.post("/api/sprints/{sprint_id}/complete", response_model=SprintCompleteOut)
def complete_sprint(sprint_id: str, body: SprintComplete, c: ContainerDep) -> SprintCompleteOut:
    s, nxt, moved = c.sprints.complete(sprint_id, body.rollover, body.summary, body.lessons)
    return SprintCompleteOut(
        sprint=sprint_out(s), next_sprint=sprint_out(nxt) if nxt else None, rolled_over=moved
    )


def _plan_out(p: object) -> WeeklyPlanOut:
    d = dict(p.__dict__)
    d["objectives"] = [WeeklyObjectiveOut(text=o.text, done=o.done) for o in d["objectives"]]
    d.pop("updated_at", None)
    return WeeklyPlanOut(**d)


@router.get("/api/weeks/{day}", response_model=WeekOut)
def week(day: date, c: ContainerDep) -> WeekOut:
    v = c.weeks.view(day)
    ser = MeetingSerializer(c)
    return WeekOut(
        week_start=v.week_start,
        plan=_plan_out(v.plan),
        days=[
            WeekDayOut(
                day=d.day,
                tasks=[TaskOut.model_validate(t) for t in d.tasks],
                time=day_time_out(d.time),
                capacity_minutes=d.capacity_minutes,
                planned_minutes=d.planned_minutes,
                meetings=[ser(m, v.series) for m in d.meetings],
            )
            for d in v.days
        ],
        sprint=sprint_out(v.sprint) if v.sprint else None,
        sprint_backlog=[TaskOut.model_validate(t) for t in v.sprint_backlog],
    )


@router.patch("/api/weeks/{day}", response_model=WeeklyPlanOut)
def update_week(day: date, body: WeeklyPlanUpdate, c: ContainerDep) -> WeeklyPlanOut:
    changes = body.model_dump(exclude_unset=True)
    if "objectives" in changes:
        changes["objectives"] = [dict(o) for o in changes["objectives"]]
    return _plan_out(c.weeks.update_plan(day, changes))


@router.get("/api/weeks/{day}/review", response_model=WeekReviewOut)
def week_review(day: date, c: ContainerDep) -> WeekReviewOut:
    r = c.weeks.review(day)
    d = dict(r.__dict__)
    d["objectives"] = [WeeklyObjectiveOut(text=o.text, done=o.done) for o in r.objectives]
    return WeekReviewOut(**d)


@router.post("/api/weeks/{day}/roll-over")
def week_roll_over(day: date, c: ContainerDep) -> dict[str, int]:
    return {"moved": c.weeks.roll_over(day)}
