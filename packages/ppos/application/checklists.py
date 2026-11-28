"""Reusable checklists (B-026): apply one to get a parent task with a subtask per line."""

from __future__ import annotations

from datetime import date

from ppos.application.ports import UnitOfWorkFactory
from ppos.application.tasks import TaskService
from ppos.domain.capture import parse_capture
from ppos.domain.checklists import Checklist, clean_lines
from ppos.domain.tasks import Task, TaskStatus
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

STARTERS: dict[str, list[str]] = {
    "Release checklist": [
        "Freeze the branch ~15m",
        "Run the full test suite ~30m",
        "Update the changelog ~15m",
        "Tag the release ~10m",
        "Announce in the team channel ~10m",
        "Watch dashboards for an hour ~1h",
    ],
    "1:1 prep": [
        "Review last 1:1 notes ~10m",
        "Update talking points ~10m",
        "Check open follow-ups ~5m",
    ],
    "New teammate onboarding": [
        "Share the onboarding doc",
        "Set up repo access",
        "Pair on a first small task ~1h",
        "Introduce to key people",
        "Check in after the first week ~30m",
    ],
    "Weekly shutdown": [
        "Clear the inbox ~20m",
        "Review the week ~20m",
        "Plan next week's top 3 ~15m",
        "Update the weekly review ~10m",
    ],
}


class ChecklistService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, tasks: TaskService) -> None:
        self._uow = uow
        self._clock = clock
        self._tasks = tasks

    def all(self) -> list[Checklist]:
        with self._uow() as uow:
            return uow.checklists.all()

    def get(self, checklist_id: str) -> Checklist:
        with self._uow() as uow:
            c = uow.checklists.get(checklist_id)
        if c is None:
            raise NotFoundError("checklist", checklist_id)
        return c

    def save(self, name: str, lines: str, checklist_id: str | None = None) -> Checklist:
        name = " ".join(name.split())[:120]
        if not name:
            raise ValidationError("give the checklist a name")
        items = clean_lines(lines)
        if not items:
            raise ValidationError("add at least one item, one per line")
        now = self._clock.now()
        with self._uow() as uow:
            if checklist_id:
                c = uow.checklists.get(checklist_id)
                if c is None:
                    raise NotFoundError("checklist", checklist_id)
                c.name, c.lines, c.updated_at = name, items, now
            else:
                c = Checklist(new_id(), name, items, 0, now, now)
            uow.checklists.save(c)
            uow.audit.record("checklist", c.id, "save", details={"items": len(items)})
            uow.commit()
            return c

    def delete(self, checklist_id: str) -> None:
        with self._uow() as uow:
            if not uow.checklists.delete(checklist_id):
                raise NotFoundError("checklist", checklist_id)
            uow.commit()

    def add_starters(self) -> list[Checklist]:
        have = {c.name.casefold() for c in self.all()}
        for name, lines in STARTERS.items():
            if name.casefold() not in have:
                self.save(name, "\n".join(lines))
        return self.all()

    def apply(self, checklist_id: str, day: date | None = None, title: str = "") -> Task:
        """A parent task named after the checklist, with one subtask per line."""
        cl = self.get(checklist_id)
        today = self._clock.today()
        status = TaskStatus.PLANNED if day else TaskStatus.BACKLOG
        parent = self._tasks.create(
            (title.strip() or f"{cl.name} — {(day or today).isoformat()}")[:200],
            status=status,
            scheduled_date=day,
            tags=["checklist"],
        )
        for line in cl.lines:
            p = parse_capture(line, today)
            self._tasks.create(
                p.title or line,
                status=status,
                scheduled_date=day,
                parent_id=parent.id,
                estimate_minutes=p.estimate_minutes,
                priority=p.priority,
                tags=p.tags,
            )
        with self._uow() as uow:
            c = uow.checklists.get(cl.id)
            if c is not None:
                c.uses += 1
                uow.checklists.save(c)
                uow.commit()
        return parent
