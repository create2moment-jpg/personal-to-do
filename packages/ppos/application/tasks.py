"""Task and project use cases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import date, datetime, timedelta
from typing import Any

from ppos.application.ports import TaskQuery, UnitOfWork, UnitOfWorkFactory
from ppos.domain.notes import EntityType
from ppos.domain.projects import Project, ProjectStatus
from ppos.domain.repeat import next_after, normalize_rule
from ppos.domain.tasks import (
    Priority,
    Task,
    TaskStatus,
    detect_dependency_cycle,
    normalize_tags,
    normalize_title,
    validate_minutes,
)
from ppos.domain.timebox import parse_start
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

TASK_EDITABLE_FIELDS = frozenset(
    {
        "title",
        "description",
        "notes",
        "priority",
        "estimate_minutes",
        "actual_minutes",
        "project_id",
        "area",
        "parent_id",
        "tags",
        "due_date",
        "recurrence",
        "position",
        "goal_id",
    }
)
# status and scheduled_date go through move() so invariants are applied in one place.

PROJECT_EDITABLE_FIELDS = frozenset({"name", "description", "area", "status", "color", "emoji"})


TRASH_DAYS = 30


class TaskService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    # -- queries ---------------------------------------------------------
    def get(self, task_id: str) -> Task:
        with self._uow() as uow:
            return _require_task(uow, task_id)

    def find(self, query: TaskQuery) -> list[Task]:
        with self._uow() as uow:
            return uow.tasks.find(query)

    def dependencies_of(self, task_id: str) -> list[str]:
        with self._uow() as uow:
            _require_task(uow, task_id)
            return uow.tasks.dependencies_of(task_id)

    # -- commands --------------------------------------------------------
    def create(
        self,
        title: str,
        *,
        status: TaskStatus = TaskStatus.BACKLOG,
        scheduled_date: date | None = None,
        **fields: Any,
    ) -> Task:
        unknown = set(fields) - TASK_EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"unknown task fields: {sorted(unknown)}")
        now = self._clock.now()
        with self._uow() as uow:
            if fields.get("project_id"):
                _require_project(uow, fields["project_id"])
            if fields.get("goal_id") and uow.goals.get(fields["goal_id"]) is None:
                raise NotFoundError("goal", fields["goal_id"])
            if "recurrence" in fields:
                fields["recurrence"] = normalize_rule(fields["recurrence"])
            if fields.get("parent_id"):
                _require_task(uow, fields["parent_id"])
            if scheduled_date is not None and status == TaskStatus.BACKLOG:
                status = TaskStatus.PLANNED
            fields.setdefault("position", uow.tasks.max_position(status, scheduled_date) + 1)
            task = Task(
                id=new_id(),
                title=title,
                created_at=now,
                updated_at=now,
                status=status,
                scheduled_date=scheduled_date,
                completed_at=now if status == TaskStatus.DONE else None,
                **fields,
            )
            uow.tasks.add(task)
            uow.audit.record("task", task.id, "create", details={"title": task.title})
            uow.commit()
            return task

    def update(self, task_id: str, changes: Mapping[str, Any]) -> Task:
        unknown = set(changes) - TASK_EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"fields not editable here: {sorted(unknown)}")
        with self._uow() as uow:
            task = _require_task(uow, task_id)
            before = asdict(task)
            for key, value in changes.items():
                if key == "title":
                    value = normalize_title(value)
                elif key == "tags":
                    value = normalize_tags(value)
                elif key in ("estimate_minutes", "actual_minutes"):
                    validate_minutes(key, value)
                    if key == "actual_minutes" and value is None:
                        value = 0
                elif key == "priority":
                    value = Priority(value)
                elif key == "project_id" and value:
                    _require_project(uow, value)
                elif key == "goal_id" and value and uow.goals.get(value) is None:
                    raise NotFoundError("goal", value)
                elif key == "recurrence":
                    value = normalize_rule(value)
                elif key == "parent_id" and value:
                    _validate_parent(uow, task, value)
                setattr(task, key, value)
            task.updated_at = self._clock.now()
            uow.tasks.update(task)
            uow.audit.record("task", task.id, "update", details=_diff(before, asdict(task)))
            uow.commit()
            return task

    def timebox(self, task_id: str, day: date, start: str | None) -> Task:
        """Give a task a start time on ``day`` (scheduling it there), or clear it."""
        return self.timebox_many(day, [(task_id, start)])[0]

    def timebox_many(self, day: date, items: list[tuple[str, str | None]]) -> list[Task]:
        """Set several start times in one transaction (all or nothing)."""
        checked = [(task_id, parse_start(start)) for task_id, start in items]
        now = self._clock.now()
        out = []
        with self._uow() as uow:
            for task_id, start in checked:
                task = _require_task(uow, task_id)
                if task.status == TaskStatus.DONE and start is not None:
                    raise ValidationError("a finished task cannot be timeboxed")
                before = task.timebox_start
                if start is not None and task.scheduled_date != day:
                    task.schedule(day, now)
                    task.position = uow.tasks.max_position(task.status, day) + 1
                task.timebox_start = start
                task.updated_at = now
                uow.tasks.update(task)
                uow.audit.record(
                    "task",
                    task.id,
                    "timebox",
                    details={"day": day.isoformat(), "from": before, "to": start},
                )
                out.append(task)
            uow.commit()
        return out

    def move(
        self,
        task_id: str,
        *,
        status: TaskStatus | None = None,
        scheduled_date: date | None = None,
        unschedule: bool = False,
        position: float | None = None,
    ) -> Task:
        """Drag/drop: change state and/or day in one atomic step."""
        now = self._clock.now()
        with self._uow() as uow:
            task = _require_task(uow, task_id)
            before = {"status": task.status.value, "scheduled_date": str(task.scheduled_date)}
            if unschedule:
                task.schedule(None, now)
            elif scheduled_date is not None:
                task.schedule(scheduled_date, now)
            spawn = False
            was_scheduled = task.scheduled_date  # before completion auto-dates it
            if status is not None:
                if status == TaskStatus.DONE:
                    self._assert_dependencies_done(uow, task)
                    spawn = task.recurrence is not None and task.status != TaskStatus.DONE
                task.transition(status, now)
                if status != TaskStatus.BACKLOG and task.scheduled_date is None:
                    # Planned/active work without a day lands on today.
                    task.scheduled_date = self._clock.today()
            if position is not None:
                task.position = position
            else:
                task.position = uow.tasks.max_position(task.status, task.scheduled_date) + 1
            uow.tasks.update(task)
            if spawn:
                self._spawn_next(uow, task, now, was_scheduled)
            uow.audit.record(
                "task",
                task.id,
                "move",
                details={
                    "from": before,
                    "to": {"status": task.status.value, "scheduled_date": str(task.scheduled_date)},
                },
            )
            uow.commit()
            return task

    def _spawn_next(
        self, uow: UnitOfWork, done: Task, now: datetime, scheduled: date | None
    ) -> Task:
        """A repeating task was completed: create its next occurrence and hand the rule over."""
        assert done.recurrence is not None
        anchor = scheduled or done.due_date or self._clock.today()
        nxt = next_after(done.recurrence, anchor)
        shift = nxt - anchor
        status = TaskStatus.PLANNED if scheduled else TaskStatus.BACKLOG
        follow = Task(
            id=new_id(),
            title=done.title,
            created_at=now,
            updated_at=now,
            description=done.description,
            notes=done.notes,
            status=status,
            priority=done.priority,
            estimate_minutes=done.estimate_minutes,
            project_id=done.project_id,
            area=done.area,
            tags=list(done.tags),
            due_date=done.due_date + shift if done.due_date else None,
            scheduled_date=nxt if scheduled else None,
            recurrence=done.recurrence,
            goal_id=done.goal_id,
            position=uow.tasks.max_position(status, nxt if scheduled else None) + 1,
            timebox_start=done.timebox_start if scheduled else None,  # same time next time
        )
        uow.tasks.add(follow)
        done.recurrence = (
            None  # the rule lives on in the next occurrence; re-completing won't duplicate
        )
        uow.tasks.update(done)
        uow.audit.record(
            "task", follow.id, "repeat", details={"from": done.id, "on": nxt.isoformat()}
        )
        return follow

    def delete(self, task_id: str) -> list[str]:
        """Move a task and its subtasks to the trash (restorable for TRASH_DAYS days)."""
        now = self._clock.now()
        with self._uow() as uow:
            task = _require_task(uow, task_id)
            ids = [task.id, *self._descendants(uow, task.id)]
            for tid in ids:
                t = uow.tasks.get(tid)
                if t is not None and t.deleted_at is None:
                    t.deleted_at, t.updated_at = now, now
                    uow.tasks.update(t)
            uow.audit.record(
                "task", task_id, "delete", details={"title": task.title, "count": len(ids)}
            )
            uow.commit()
            return ids

    def restore(self, task_id: str) -> Task:
        """Take a task (with the subtasks deleted together with it) out of the trash."""
        now = self._clock.now()
        with self._uow() as uow:
            task = uow.tasks.get(task_id)
            if task is None or task.deleted_at is None:
                raise NotFoundError("deleted task", task_id)
            stamp = task.deleted_at
            chain = [task]
            parent_id = task.parent_id
            while parent_id:  # a subtask needs its parent back too
                parent = uow.tasks.get(parent_id)
                if parent is None or parent.deleted_at is None:
                    break
                chain.append(parent)
                parent_id = parent.parent_id
            subtasks = [
                t for t in uow.tasks.find(TaskQuery(parent_id=task.id, trashed=True, limit=500))
                if t.deleted_at == stamp
            ]  # fmt: skip
            for t in [*chain, *subtasks]:
                t.deleted_at, t.updated_at = None, now
                uow.tasks.update(t)
            uow.audit.record("task", task_id, "restore")
            uow.commit()
            return task

    def trash(self) -> list[Task]:
        with self._uow() as uow:
            items = uow.tasks.find(TaskQuery(trashed=True, top_level_only=False, limit=500))
        return sorted(items, key=lambda t: t.deleted_at or t.updated_at, reverse=True)

    def purge_trash(self, days: int = TRASH_DAYS) -> int:
        """Delete for good what has been in the trash longer than ``days``."""
        cutoff = self._clock.now() - timedelta(days=days)
        removed = 0
        with self._uow() as uow:
            for t in uow.tasks.find(TaskQuery(trashed=True, limit=10000)):
                if t.deleted_at is not None and t.deleted_at < cutoff:
                    uow.tasks.delete(t.id)
                    uow.links.delete_for_entity(EntityType.TASK, t.id)
                    removed += 1
            if removed:
                uow.audit.record(
                    "task", "trash", "purge", actor="system", details={"removed": removed}
                )
            uow.commit()
        return removed

    @staticmethod
    def _descendants(uow: UnitOfWork, task_id: str) -> list[str]:
        out: list[str] = []
        stack = [task_id]
        while stack:
            for child in uow.tasks.find(TaskQuery(parent_id=stack.pop(), limit=500)):
                out.append(child.id)
                stack.append(child.id)
        return out

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        with self._uow() as uow:
            _require_task(uow, task_id)
            _require_task(uow, depends_on)
            detect_dependency_cycle(task_id, depends_on, uow.tasks.dependencies())
            uow.tasks.add_dependency(task_id, depends_on)
            uow.audit.record("task", task_id, "add_dependency", details={"on": depends_on})
            uow.commit()

    def remove_dependency(self, task_id: str, depends_on: str) -> None:
        with self._uow() as uow:
            uow.tasks.remove_dependency(task_id, depends_on)
            uow.audit.record("task", task_id, "remove_dependency", details={"on": depends_on})
            uow.commit()

    @staticmethod
    def _assert_dependencies_done(uow: UnitOfWork, task: Task) -> None:
        for dep_id in uow.tasks.dependencies_of(task.id):
            dep = uow.tasks.get(dep_id)
            if dep is not None and dep.is_open and dep.deleted_at is None:
                raise ValidationError(f"blocked by unfinished dependency: {dep.title!r}")


class ProjectService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def find(self, include_archived: bool = False) -> list[Project]:
        with self._uow() as uow:
            return uow.projects.find(include_archived)

    def create(self, name: str, **fields: Any) -> Project:
        unknown = set(fields) - PROJECT_EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"unknown project fields: {sorted(unknown)}")
        now = self._clock.now()
        with self._uow() as uow:
            if uow.projects.find_by_name(name):
                raise ValidationError(f"project {name!r} already exists")
            project = Project(id=new_id(), name=name, created_at=now, updated_at=now, **fields)
            uow.projects.add(project)
            uow.audit.record("project", project.id, "create", details={"name": project.name})
            uow.commit()
            return project

    def update(self, project_id: str, changes: Mapping[str, Any]) -> Project:
        unknown = set(changes) - PROJECT_EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            project = _require_project(uow, project_id)
            data = asdict(project) | dict(changes)
            data["status"] = ProjectStatus(data["status"])
            data["updated_at"] = self._clock.now()
            updated = Project(**data)  # re-run invariants
            uow.projects.update(updated)
            uow.audit.record("project", project_id, "update", details=dict(changes))
            uow.commit()
            return updated


def _require_task(uow: UnitOfWork, task_id: str) -> Task:
    task = uow.tasks.get(task_id)
    if task is None or task.deleted_at is not None:  # trashed tasks are only reachable via restore
        raise NotFoundError("task", task_id)
    return task


def _require_project(uow: UnitOfWork, project_id: str) -> Project:
    project = uow.projects.get(project_id)
    if project is None:
        raise NotFoundError("project", project_id)
    return project


def _validate_parent(uow: UnitOfWork, task: Task, parent_id: str) -> None:
    if parent_id == task.id:
        raise ValidationError("a task cannot be its own parent")
    current: str | None = parent_id
    while current is not None:
        parent = _require_task(uow, current)
        if parent.parent_id == task.id:
            raise ValidationError("subtask nesting would create a cycle")
        current = parent.parent_id


def _diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        k: {"from": str(before[k]), "to": str(after[k])}
        for k in after
        if k != "updated_at" and before.get(k) != after[k]
    }
