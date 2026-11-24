"""Composition root: wires settings, infrastructure and application services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from ppos.ai.output import clean_improved
from ppos.ai.prompts import load_template
from ppos.ai.provider import LLMProvider, build_provider
from ppos.application.book import BookService
from ppos.application.capture import CaptureService
from ppos.application.daily import DayService
from ppos.application.meetings import MeetingService
from ppos.application.notes import LinkService, NoteService
from ppos.application.planning import SprintService, WeekService
from ppos.application.ports import SearchHit
from ppos.application.settings import SettingsService
from ppos.application.tasks import ProjectService, TaskService
from ppos.domain.meetings import DayTime, Meeting, MeetingSeries, day_time
from ppos.infrastructure.config import Settings, ensure_data_dir
from ppos.infrastructure.db import connect
from ppos.infrastructure.ics import parse_ics
from ppos.infrastructure.migrations import prepare_database
from ppos.infrastructure.sqlite_repos import SqliteUnitOfWorkFactory
from ppos.shared.clock import Clock, ZonedClock

log = logging.getLogger("ppos")


@dataclass
class Container:
    settings: Settings
    clock: Clock
    uow: SqliteUnitOfWorkFactory
    tasks: TaskService
    projects: ProjectService
    notes: NoteService
    links: LinkService
    days: DayService
    capture: CaptureService
    settings_service: SettingsService
    meetings: MeetingService
    sprints: SprintService
    weeks: WeekService
    book: BookService
    ai: LLMProvider

    def search(self, query: str, limit: int = 20) -> list[SearchHit]:
        with self.uow() as uow:
            return uow.search.search(query, limit)


def init_database(settings: Settings) -> list[int]:
    ensure_data_dir(settings)
    conn = connect(settings.db_path)
    try:
        applied = prepare_database(conn, settings.migrations_dir, settings.auto_migrate)
    finally:
        conn.close()
    if applied:
        log.info("applied migrations %s", applied)
    return applied


def build_container(settings: Settings, clock: Clock | None = None) -> Container:
    init_database(settings)
    uow = SqliteUnitOfWorkFactory(settings.db_path)
    workspace = SettingsService(uow)
    workspace.get()  # warm the cache so later reads never open a nested transaction
    clock = clock or ZonedClock(workspace.tz)
    tasks = TaskService(uow, clock)
    notes = NoteService(uow, clock, timedelta(seconds=settings.note_snapshot_interval_seconds))
    meetings = MeetingService(uow, clock, workspace, parse_ics)
    sprints = SprintService(uow, clock, workspace)

    def day_meetings(day: date) -> tuple[DayTime, list[Meeting], dict[str, MeetingSeries]]:
        found, series = meetings.between(day, day)
        return day_time(day, found, series, workspace.get()), found, series

    ai = build_provider(
        settings.llm_provider, settings.llm_base_url, settings.llm_model,
        settings.llm_timeout_seconds, settings.llm_allow_remote,
    )  # fmt: skip
    improve_template = load_template(settings.prompts_dir, "02_writing/improve_prompt/v1.md")

    def improver(original: str, style_instruction: str) -> tuple[str, str, str, int]:
        prompt = improve_template.render(style_instruction=style_instruction, prompt=original)
        system = improve_template.meta.get("role", "You improve prompts.")
        r = ai.generate(
            system, prompt, temperature=settings.llm_temperature, max_tokens=settings.llm_max_tokens
        )
        return clean_improved(r.text), r.model, improve_template.ref, r.latency_ms

    return Container(
        settings=settings,
        clock=clock,
        uow=uow,
        tasks=tasks,
        projects=ProjectService(uow, clock),
        notes=notes,
        links=LinkService(uow, clock),
        days=DayService(uow, clock, settings.default_capacity_minutes, day_meetings),
        capture=CaptureService(uow, clock, tasks, notes, meetings, workspace.tz),
        settings_service=workspace,
        meetings=meetings,
        sprints=sprints,
        weeks=WeekService(uow, clock, workspace, meetings, sprints),
        book=BookService(uow, clock, improver),
        ai=ai,
    )
