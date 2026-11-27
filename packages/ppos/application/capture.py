"""Global quick capture: text in, task / idea / note out."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta, timezone, tzinfo

from ppos.application.meetings import MeetingService
from ppos.application.notes import NoteService
from ppos.application.ports import UnitOfWorkFactory
from ppos.application.tasks import TaskService
from ppos.domain.capture import CaptureKind, ParsedCapture, parse_capture
from ppos.domain.meetings import Meeting, MeetingSeries
from ppos.domain.notes import Note, NoteKind
from ppos.domain.repeat import to_rule
from ppos.domain.tasks import Task
from ppos.shared.clock import Clock
from ppos.shared.errors import ValidationError


@dataclass
class CaptureResult:
    parsed: ParsedCapture
    task: Task | None = None
    note: Note | None = None
    warnings: list[str] | None = None
    meeting: Meeting | None = None
    series: MeetingSeries | None = None


DEFAULT_MEETING_MINUTES = 30  # only when the capture gives no ~duration; shown in the preview


class CaptureService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        tasks: TaskService,
        notes: NoteService,
        meetings: MeetingService | None = None,
        tz: Callable[[], tzinfo] | None = None,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._tasks = tasks
        self._notes = notes
        self._meetings = meetings
        self._tz = tz

    def preview(self, text: str) -> tuple[ParsedCapture, str | None]:
        """Parse without saving (live preview in the capture bar).

        Returns the parsed capture and the resolved project name, if any.
        """
        parsed = self.meeting_defaults(parse_capture(text, self._clock.today()))
        project_name = None
        if parsed.project_hint:
            with self._uow() as uow:
                project = uow.projects.find_by_name(parsed.project_hint)
            project_name = project.name if project else None
        return parsed, project_name

    def meeting_defaults(self, parsed: ParsedCapture) -> ParsedCapture:
        """Fill the day, start and duration a meeting capture left out (shown in the preview)."""
        if parsed.kind != CaptureKind.MEETING or self._meetings is None:
            return parsed
        parsed.scheduled_date = parsed.scheduled_date or self._clock.today()
        parsed.start_time = parsed.start_time or self._meetings.default_start(parsed.scheduled_date)
        parsed.estimate_minutes = parsed.estimate_minutes or DEFAULT_MEETING_MINUTES
        return parsed

    def _capture_meeting(self, parsed: ParsedCapture) -> CaptureResult:
        if self._meetings is None:
            raise ValidationError("meetings are not available")
        if not parsed.title:
            raise ValidationError(
                "give the meeting a title, e.g. meeting: Sprint planning @mon @10:00 ~1h weekly"
            )
        parsed = self.meeting_defaults(parsed)
        assert parsed.scheduled_date and parsed.start_time and parsed.estimate_minutes
        out = self._meetings.schedule(
            parsed.title,
            parsed.scheduled_date,
            parsed.start_time,
            parsed.estimate_minutes,
            people=parsed.people,
            topic=parsed.tags[0] if parsed.tags else None,
            recurrence=parsed.recurrence,
        )
        if isinstance(out, Meeting):
            return CaptureResult(parsed, meeting=out, warnings=[])
        return CaptureResult(parsed, series=out, warnings=[])

    def capture(self, text: str) -> CaptureResult:
        if not text.strip():
            raise ValidationError("nothing to capture")
        parsed = parse_capture(text, self._clock.today())
        warnings: list[str] = []
        if parsed.kind == CaptureKind.CALL:
            return self._capture_call(parsed)
        if parsed.kind == CaptureKind.MEETING:
            return self._capture_meeting(parsed)
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
            recurrence=to_rule(parsed.recurrence) if parsed.recurrence else None,
            project_id=project_id,
        )
        return CaptureResult(parsed, task=task, warnings=warnings)

    def _capture_call(self, parsed: ParsedCapture) -> CaptureResult:
        if self._meetings is None:
            raise ValidationError("call logging is not available")
        if not parsed.people and not parsed.title:
            raise ValidationError("say who the call was with, e.g. call: Priya / ADR review ~30m")
        minutes = parsed.estimate_minutes or 30
        tz = self._tz() if self._tz else timezone.utc
        now = self._clock.now().astimezone(tz)
        if parsed.start_time:
            hh, mm = (int(x) for x in parsed.start_time.split(":"))
            start = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        else:
            start = (now - timedelta(minutes=minutes)).replace(second=0, microsecond=0)
        meeting = self._meetings.log_call(
            title=parsed.title,
            start_at=start,
            minutes=minutes,
            people=parsed.people,
            topic=parsed.tags[0] if parsed.tags else None,
        )
        return CaptureResult(parsed, meeting=meeting, warnings=[])
