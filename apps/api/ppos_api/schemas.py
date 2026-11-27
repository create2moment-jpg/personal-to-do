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
    sprint_id: str | None = None
    commitment: str | None = None
    goal_id: str | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = ""
    notes: str = ""
    status: TaskStatus = TaskStatus.BACKLOG
    priority: int = Field(default=4, ge=1, le=4)
    estimate_minutes: int | None = Field(default=None, ge=0)
    project_id: str | None = None
    goal_id: str | None = None
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
    goal_id: str | None = None
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
    capacity_mode: str = "auto"


class DailyPlanUpdate(BaseModel):
    objective: str | None = Field(default=None, max_length=1000)
    capacity_minutes: int | None = Field(default=None, ge=0, le=1440)
    top_priority_ids: list[str] | None = Field(default=None, max_length=3)
    capacity_mode: str | None = Field(default=None, pattern="^(auto|manual)$")


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
    time: DayTimeOut | None = None
    meetings: list[MeetingOut] = []


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
    people: list[str] = []
    start_time: str | None = None
    repeat: str | None = None  # human-readable, meetings only


class CaptureOut(BaseModel):
    kind: str
    task: TaskOut | None
    note: NoteOut | None
    warnings: list[str]
    meeting: MeetingOut | None = None
    series: dict[str, str] | None = None  # {series_key, title, cadence} for a recurring meeting


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


# --------------------------------------------------------------------------- Phase 2/3


class WorkspaceSettingsOut(BaseModel):
    timezone: str
    work_start: str
    work_end: str
    workdays: list[int]
    buffer_percent: int
    sprint_length_days: int
    default_task_minutes: int
    work_minutes: int


class WorkspaceSettingsUpdate(BaseModel):
    timezone: str | None = None
    work_start: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    work_end: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    workdays: list[int] | None = None
    buffer_percent: int | None = Field(default=None, ge=0, le=50)
    sprint_length_days: int | None = Field(default=None, ge=7, le=28)
    default_task_minutes: int | None = Field(default=None, ge=0, le=480)


class SprintOut(Out):
    id: str
    name: str
    goal: str
    start_date: date
    end_date: date
    status: str
    review_summary: str
    review_lessons: str
    completed_at: datetime | None


class SprintCreate(BaseModel):
    name: str = ""
    goal: str = ""
    start_date: date | None = None
    end_date: date | None = None


class SprintUpdate(BaseModel):
    name: str | None = None
    goal: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    review_summary: str | None = None
    review_lessons: str | None = None


class SprintTasksAdd(BaseModel):
    task_ids: list[str] = Field(min_length=1, max_length=500)
    commitment: str = Field(default="committed", pattern="^(committed|stretch)$")


class SprintComplete(BaseModel):
    rollover: str = Field(default="next", pattern="^(next|backlog)$")
    summary: str = ""
    lessons: str = ""


class BurndownPointOut(BaseModel):
    day: date
    remaining_minutes: int
    ideal_minutes: float
    scope_minutes: int


class SprintSummaryOut(BaseModel):
    sprint: SprintOut
    tasks: list[TaskOut]
    committed_total: int
    committed_done: int
    stretch_total: int
    stretch_done: int
    committed_minutes: int
    remaining_minutes: int
    added_after_start: list[str]
    removed_after_start: list[str]
    burndown: list[BurndownPointOut]
    days_total: int
    days_elapsed: int
    completion_rate: float


class SprintCompleteOut(BaseModel):
    sprint: SprintOut
    next_sprint: SprintOut | None
    rolled_over: int


class MeetingOut(BaseModel):
    id: str
    source: str
    kind: str
    title: str
    start_at: datetime
    end_at: datetime
    all_day: bool
    location: str | None
    organizer: str | None
    series_key: str | None
    status: str | None  # explicit override
    effective_status: str
    counted_minutes: int
    duration_minutes: int
    attended_minutes: int | None
    rating: int | None
    note: str
    topic: str | None
    people: list[str]
    series_default_status: str | None
    cadence: str | None


class MeetingUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(attended|skipped|partial)$")
    attended_minutes: int | None = Field(default=None, ge=0, le=1440)
    rating: int | None = Field(default=None, ge=1, le=5)
    note: str | None = None
    topic: str | None = None
    people: list[str] | None = None
    title: str | None = None
    start_at: datetime | None = None
    minutes: int | None = Field(default=None, ge=1, le=720)
    kind: str | None = Field(default=None, pattern="^(meeting|call)$")
    clear_status: bool = False


class CallCreate(BaseModel):
    title: str = ""
    people: list[str] = []
    topic: str | None = None
    start_at: datetime
    minutes: int = Field(ge=1, le=720)
    note: str = ""
    rating: int | None = Field(default=None, ge=1, le=5)
    kind: str = Field(default="call", pattern="^(meeting|call)$")


class RecurrenceIn(BaseModel):
    freq: str = Field(pattern="^(daily|weekly|monthly)$")
    interval: int = Field(default=1, ge=1, le=52)
    weekdays: list[int] = []
    until: date | None = None
    count: int | None = Field(default=None, ge=1, le=1000)


class ScheduleIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    day: date
    start_time: str = Field(pattern=r"^\d{1,2}:\d{2}$")
    minutes: int = Field(ge=1, le=720)
    people: list[str] = []
    topic: str | None = None
    location: str | None = Field(default=None, max_length=300)
    note: str = ""
    kind: str = Field(default="meeting", pattern="^(meeting|call)$")
    recurrence: RecurrenceIn | None = None


class SeriesPlanPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    start_time: str | None = Field(default=None, pattern=r"^\d{1,2}:\d{2}$")
    minutes: int | None = Field(default=None, ge=1, le=720)
    recurrence: RecurrenceIn | None = None
    people: list[str] | None = None
    topic: str | None = None
    location: str | None = None
    kind: str | None = Field(default=None, pattern="^(meeting|call)$")


class SeriesUpdate(BaseModel):
    default_status: str | None = Field(default=None, pattern="^(attending|skipped)$")
    rating: int | None = Field(default=None, ge=1, le=5)
    topic: str | None = None
    notes: str | None = None


class SeriesOut(BaseModel):
    series_key: str
    title: str
    cadence: str | None
    default_status: str
    rating: int | None
    notes: str
    topic: str | None
    occurrences_4w: int
    avg_minutes: int
    minutes_per_month: int
    next_start: datetime | None
    last_start: datetime | None
    source: str = "ics"
    plan: dict[str, Any] | None = None


class IcsImportIn(BaseModel):
    filename: str = Field(default="calendar.ics", max_length=255)
    content: str = Field(min_length=10, max_length=10 * 1024 * 1024)


class IcsImportOut(BaseModel):
    events: int
    created: int
    updated: int
    cancelled: int
    series: int
    window_start: datetime
    window_end: datetime


class NamedOut(Out):
    id: str
    name: str


class DayTimeOut(BaseModel):
    day: date
    work_minutes: int
    meeting_minutes: int
    meeting_minutes_total: int
    available_minutes: int
    capacity_minutes: int


class WeekDayOut(BaseModel):
    day: date
    tasks: list[TaskOut]
    time: DayTimeOut
    capacity_minutes: int
    planned_minutes: int
    meetings: list[MeetingOut]


class WeeklyObjectiveOut(BaseModel):
    text: str
    done: bool = False


class WeeklyPlanOut(BaseModel):
    week_start: date
    objectives: list[WeeklyObjectiveOut]
    notes: str
    review_wins: str
    review_lessons: str
    review_risks: str
    review_next_focus: str
    review_completed_at: datetime | None


class WeeklyPlanUpdate(BaseModel):
    objectives: list[WeeklyObjectiveOut] | None = Field(default=None, max_length=3)
    notes: str | None = None
    review_wins: str | None = None
    review_lessons: str | None = None
    review_risks: str | None = None
    review_next_focus: str | None = None
    complete_review: bool = False


class WeekOut(BaseModel):
    week_start: date
    plan: WeeklyPlanOut
    days: list[WeekDayOut]
    sprint: SprintOut | None
    sprint_backlog: list[TaskOut]


class WeekReviewOut(BaseModel):
    week_start: date
    planned: int
    done: int
    open: int
    done_titles: list[str]
    open_titles: list[str]
    estimate_minutes: int
    actual_minutes: int
    meeting_minutes: int
    available_minutes: int
    work_minutes: int
    objectives: list[WeeklyObjectiveOut]


class RankedOut(BaseModel):
    name: str
    minutes: int
    count: int


class SeriesRankOut(BaseModel):
    series_key: str
    title: str
    minutes: int
    count: int
    rating: float | None


class InsightsOut(BaseModel):
    start: date
    end: date
    days: list[DayTimeOut]
    meeting_minutes: int
    work_minutes: int
    available_minutes: int
    meetings_count: int
    calls_count: int
    by_person: list[RankedOut]
    by_topic: list[RankedOut]
    by_series: list[SeriesRankOut]
    rated_minutes: int
    avg_rating: float | None
    reconsider: list[dict[str, Any]]


TodayOut.model_rebuild()
CaptureOut.model_rebuild()
