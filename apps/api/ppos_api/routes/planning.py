"""Today / day plan / review / capture / search / projects."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, status

from ppos.domain.daily import CapacitySummary
from ppos_api.deps import ContainerDep
from ppos_api.schemas import (
    CapacityOut,
    CaptureOut,
    CaptureRequest,
    DailyPlanOut,
    DailyPlanUpdate,
    DailyReviewUpdate,
    NoteOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    RollOverRequest,
    SearchHitOut,
    TaskOut,
    TodayOut,
)

router = APIRouter(tags=["planning"])


def _capacity(cap: CapacitySummary) -> CapacityOut:
    return CapacityOut(
        capacity_minutes=cap.capacity_minutes,
        planned_minutes=cap.planned_minutes,
        unestimated_count=cap.unestimated_count,
        done_minutes=cap.done_minutes,
        remaining_capacity=cap.remaining_capacity,
        load_ratio=round(cap.load_ratio, 3) if cap.capacity_minutes else 0.0,
        overcommitted=cap.overcommitted,
    )


@router.get("/api/today", response_model=TodayOut)
def today(c: ContainerDep, day: date | None = None) -> TodayOut:
    view = c.days.today_view(day)
    return TodayOut(
        day=view.day,
        plan=DailyPlanOut.model_validate(view.plan),
        tasks=[TaskOut.model_validate(t) for t in view.tasks],
        overdue=[TaskOut.model_validate(t) for t in view.overdue],
        due_today_unscheduled=[TaskOut.model_validate(t) for t in view.due_today_unscheduled],
        capacity=_capacity(view.capacity),
        journal=NoteOut.model_validate(view.journal) if view.journal else None,
    )


@router.patch("/api/days/{day}", response_model=DailyPlanOut)
def update_day(day: date, body: DailyPlanUpdate, c: ContainerDep) -> DailyPlanOut:
    return DailyPlanOut.model_validate(c.days.update_plan(day, body.model_dump(exclude_unset=True)))


@router.put("/api/days/{day}/review", response_model=DailyPlanOut)
def save_review(day: date, body: DailyReviewUpdate, c: ContainerDep) -> DailyPlanOut:
    changes = body.model_dump(exclude_unset=True)
    complete = bool(changes.pop("complete", False))
    return DailyPlanOut.model_validate(c.days.save_review(day, changes, complete))


@router.get("/api/days/{day}/review-draft")
def review_draft(day: date, c: ContainerDep) -> dict[str, Any]:
    return c.days.review_draft(day)


@router.post("/api/days/{day}/roll-over", response_model=list[TaskOut])
def roll_over(day: date, body: RollOverRequest, c: ContainerDep) -> list[TaskOut]:
    return [TaskOut.model_validate(t) for t in c.days.roll_over(day, body.to)]


@router.post("/api/days/{day}/journal", response_model=NoteOut)
def journal(day: date, c: ContainerDep) -> NoteOut:
    note = c.notes.journal_for(day, create=True)
    assert note is not None
    return NoteOut.model_validate(note)


@router.post("/api/capture", response_model=CaptureOut, status_code=status.HTTP_201_CREATED)
def capture(body: CaptureRequest, c: ContainerDep) -> CaptureOut:
    result = c.capture.capture(body.text)
    return CaptureOut(
        kind=result.parsed.kind.value,
        task=TaskOut.model_validate(result.task) if result.task else None,
        note=NoteOut.model_validate(result.note) if result.note else None,
        warnings=result.warnings or [],
    )


@router.get("/api/search", response_model=list[SearchHitOut])
def search(c: ContainerDep, q: str = Query(min_length=1, max_length=200),
           limit: int = Query(default=20, ge=1, le=100)) -> list[SearchHitOut]:  # fmt: skip
    return [SearchHitOut.model_validate(h) for h in c.search(q, limit)]


@router.get("/api/projects", response_model=list[ProjectOut])
def list_projects(c: ContainerDep, include_archived: bool = False) -> list[ProjectOut]:
    return [ProjectOut.model_validate(p) for p in c.projects.find(include_archived)]


@router.post("/api/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, c: ContainerDep) -> ProjectOut:
    data = body.model_dump()
    return ProjectOut.model_validate(c.projects.create(data.pop("name"), **data))


@router.patch("/api/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate, c: ContainerDep) -> ProjectOut:
    return ProjectOut.model_validate(
        c.projects.update(project_id, body.model_dump(exclude_unset=True))
    )
