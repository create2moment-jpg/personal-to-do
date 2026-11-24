"""HTTP request/response models (presentation layer only)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ppos.domain.notes import EntityType, NoteKind
from ppos.domain.projects import ProjectStatus
from ppos.domain.tasks import TaskStatus


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TaskOut(Out):
    id: str
    title: str
    description: str
    notes: str
    status: TaskStatus
    priority: int
    estimate_minutes: int | None
    actual_minutes: int
    project_id: str | None
    area: str | None
    parent_id: str | None
    tags: list[str]
    due_date: date | None
    scheduled_date: date | None
    recurrence: str | None
    position: float
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    notes: str = ""
    status: TaskStatus = TaskStatus.BACKLOG
    priority: int = Field(default=4, ge=1, le=4)
    estimate_minutes: int | None = Field(default=None, ge=0)
    project_id: str | None = None
    area: str | None = None
    parent_id: str | None = None
    tags: list[str] = []
    due_date: date | None = None
    scheduled_date: date | None = None
    recurrence: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    notes: str | None = None
    priority: int | None = Field(default=None, ge=1, le=4)
    estimate_minutes: int | None = Field(default=None, ge=0)
    actual_minutes: int | None = Field(default=None, ge=0)
    project_id: str | None = None
    area: str | None = None
    parent_id: str | None = None
    tags: list[str] | None = None
    due_date: date | None = None
    recurrence: str | None = None
    position: float | None = None


class TaskMove(BaseModel):
    status: TaskStatus | None = None
    scheduled_date: date | None = None
    unschedule: bool = False
    position: float | None = None


class ProjectOut(Out):
    id: str
    name: str
    description: str
    area: str | None
    status: ProjectStatus
    color: str | None
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    area: str | None = None
    color: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    area: str | None = None
    status: ProjectStatus | None = None
    color: str | None = None


class NoteOut(Out):
    id: str
    title: str
    body: str
    kind: NoteKind
    project_id: str | None
    note_date: date | None
    tags: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class NoteSummaryOut(Out):
    id: str
    title: str
    kind: NoteKind
    note_date: date | None
    tags: list[str]
    version: int
    updated_at: datetime


class NoteCreate(BaseModel):
    title: str = ""
    body: str = ""
    kind: NoteKind = NoteKind.GENERAL
    project_id: str | None = None
    note_date: date | None = None
    tags: list[str] = []


class NoteUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    kind: NoteKind | None = None
    project_id: str | None = None
    note_date: date | None = None
    tags: list[str] | None = None
    snapshot: bool = False  # force a new version (e.g. explicit "save version")


class NoteVersionOut(Out):
    note_id: str
    version: int
    title: str
    body: str
    created_at: datetime


class LinkCreate(BaseModel):
    source_type: EntityType
    source_id: str
    target_type: EntityType
    target_id: str


class LinkOut(Out):
    id: str
    source_type: EntityType
    source_id: str
    target_type: EntityType
    target_id: str
    created_at: datetime


class DailyReviewOut(Out):
    unfinished: str
    blockers: str
    learning: str
    wins: str
    tomorrow_first_task: str
    completed_at: datetime | None


class DailyPlanOut(Out):
    day: date
    capacity_minutes: int
    objective: str
    top_priority_ids: list[str]
    review: DailyReviewOut
    updated_at: datetime | None


class DailyPlanUpdate(BaseModel):
    objective: str | None = Field(default=None, max_length=1000)
    capacity_minutes: int | None = Field(default=None, ge=0, le=1440)
    top_priority_ids: list[str] | None = Field(default=None, max_length=3)


class DailyReviewUpdate(BaseModel):
    unfinished: str | None = None
    blockers: str | None = None
    learning: str | None = None
    wins: str | None = None
    tomorrow_first_task: str | None = None
    complete: bool = False


class CapacityOut(BaseModel):
    capacity_minutes: int
    planned_minutes: int
    unestimated_count: int
    done_minutes: int
    remaining_capacity: int
    load_ratio: float
    overcommitted: bool


class TodayOut(BaseModel):
    day: date
    plan: DailyPlanOut
    tasks: list[TaskOut]
    overdue: list[TaskOut]
    due_today_unscheduled: list[TaskOut]
    capacity: CapacityOut
    journal: NoteOut | None


class RollOverRequest(BaseModel):
    to: date | None = None


class CaptureRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)


class CapturePreviewOut(BaseModel):
    kind: str
    title: str
    tags: list[str]
    priority: int
    estimate_minutes: int | None
    scheduled_date: date | None
    due_date: date | None
    project_hint: str | None
    project_name: str | None


class CaptureOut(BaseModel):
    kind: str
    task: TaskOut | None
    note: NoteOut | None
    warnings: list[str]


class SearchHitOut(Out):
    entity_type: EntityType
    entity_id: str
    title: str
    snippet: str
    score: float


class HealthOut(BaseModel):
    status: str
    version: str
    schema_version: int
    data_dir: str
    demo: bool
    ai: dict[str, Any]
