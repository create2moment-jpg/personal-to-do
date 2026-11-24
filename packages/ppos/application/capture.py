"""Global quick capture: text in, task / idea / note out."""

from __future__ import annotations

from dataclasses import dataclass

from ppos.application.notes import NoteService
from ppos.application.ports import UnitOfWorkFactory
from ppos.application.tasks import TaskService
from ppos.domain.capture import CaptureKind, ParsedCapture, parse_capture
from ppos.domain.notes import Note, NoteKind
from ppos.domain.tasks import Task
from ppos.shared.clock import Clock
from ppos.shared.errors import ValidationError


@dataclass
class CaptureResult:
    parsed: ParsedCapture
    task: Task | None = None
    note: Note | None = None
    warnings: list[str] | None = None


class CaptureService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        tasks: TaskService,
        notes: NoteService,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._tasks = tasks
        self._notes = notes

    def capture(self, text: str) -> CaptureResult:
        if not text.strip():
            raise ValidationError("nothing to capture")
        parsed = parse_capture(text, self._clock.today())
        warnings: list[str] = []
        if parsed.kind in (CaptureKind.IDEA, CaptureKind.NOTE):
            kind = NoteKind.IDEA if parsed.kind == CaptureKind.IDEA else NoteKind.GENERAL
            note = self._notes.create(body=parsed.title, kind=kind, tags=parsed.tags)
            return CaptureResult(parsed, note=note, warnings=warnings)

        if not parsed.title:
            raise ValidationError("a task needs a title")
        project_id = None
        if parsed.project_hint:
            with self._uow() as uow:
                project = uow.projects.find_by_name(parsed.project_hint)
            if project is None:
                warnings.append(f"unknown project {parsed.project_hint!r}; captured without it")
            else:
                project_id = project.id
        task = self._tasks.create(
            parsed.title,
            scheduled_date=parsed.scheduled_date,
            tags=parsed.tags,
            priority=parsed.priority,
            estimate_minutes=parsed.estimate_minutes,
            due_date=parsed.due_date,
            project_id=project_id,
        )
        return CaptureResult(parsed, task=task, warnings=warnings)
