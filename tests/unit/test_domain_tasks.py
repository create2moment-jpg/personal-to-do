from datetime import date, datetime, timezone

import pytest

from ppos.domain.daily import DEFAULT_UNESTIMATED_MINUTES, DailyPlan, summarize_capacity
from ppos.domain.tasks import Task, TaskStatus, detect_dependency_cycle, normalize_tags
from ppos.shared.errors import ConflictError, ValidationError

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = datetime(2026, 1, 2, tzinfo=timezone.utc)


def make(**kw: object) -> Task:
    return Task(
        id=str(kw.pop("id", "t")),
        title=str(kw.pop("title", "x")),
        created_at=T0,
        updated_at=T0,
        **kw,
    )  # type: ignore[arg-type]


def test_title_is_normalised_and_required() -> None:
    assert make(title="  hello   world ").title == "hello world"
    with pytest.raises(ValidationError):
        make(title="   ")


def test_tags_are_normalised_and_deduplicated() -> None:
    assert normalize_tags(["#ML", "ml", " infra "]) == ["ml", "infra"]
    with pytest.raises(ValidationError):
        normalize_tags(["two words"])


def test_done_sets_and_clears_completed_at() -> None:
    t = make(status=TaskStatus.PLANNED)
    t.transition(TaskStatus.DONE, T1)
    assert t.completed_at == T1
    t.transition(TaskStatus.IN_PROGRESS, T1)
    assert t.completed_at is None


def test_moving_to_backlog_unschedules() -> None:
    t = make(status=TaskStatus.PLANNED, scheduled_date=date(2026, 1, 3))
    t.transition(TaskStatus.BACKLOG, T1)
    assert t.scheduled_date is None


def test_scheduling_promotes_backlog_to_planned_and_back() -> None:
    t = make()
    t.schedule(date(2026, 1, 3), T1)
    assert t.status == TaskStatus.PLANNED
    t.schedule(None, T1)
    assert t.status == TaskStatus.BACKLOG


def test_negative_estimate_rejected() -> None:
    with pytest.raises(ValidationError):
        make(estimate_minutes=-5)


def test_dependency_cycle_detection() -> None:
    edges = {"a": {"b"}, "b": {"c"}}
    detect_dependency_cycle("d", "a", edges)  # fine
    with pytest.raises(ConflictError):
        detect_dependency_cycle("c", "a", edges)
    with pytest.raises(ConflictError):
        detect_dependency_cycle("a", "a", edges)


def test_capacity_counts_remaining_and_unestimated_and_skips_subtasks() -> None:
    tasks = [
        make(id="1", estimate_minutes=60, actual_minutes=20, status=TaskStatus.IN_PROGRESS),
        make(id="2", status=TaskStatus.PLANNED),
        make(id="3", estimate_minutes=30, status=TaskStatus.DONE, actual_minutes=25),
        make(id="4", estimate_minutes=500, parent_id="1", status=TaskStatus.PLANNED),
    ]
    s = summarize_capacity(100, tasks)
    assert s.planned_minutes == 40 + DEFAULT_UNESTIMATED_MINUTES
    assert s.unestimated_count == 1
    assert s.done_minutes == 25
    assert not s.overcommitted
    assert summarize_capacity(60, tasks).overcommitted


def test_daily_plan_limits() -> None:
    with pytest.raises(ValidationError):
        DailyPlan(day=date(2026, 1, 1), capacity_minutes=2000)
    with pytest.raises(ValidationError):
        DailyPlan(day=date(2026, 1, 1), capacity_minutes=60, top_priority_ids=["a", "b", "c", "d"])
