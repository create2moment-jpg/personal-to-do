"""Composition root: wires settings, infrastructure and application services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from ppos.application.capture import CaptureService
from ppos.application.daily import DayService
from ppos.application.notes import LinkService, NoteService
from ppos.application.ports import SearchHit
from ppos.application.tasks import ProjectService, TaskService
from ppos.infrastructure.config import Settings, ensure_data_dir
from ppos.infrastructure.db import connect
from ppos.infrastructure.migrations import prepare_database
from ppos.infrastructure.sqlite_repos import SqliteUnitOfWorkFactory
from ppos.shared.clock import Clock, SystemClock

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
    clock = clock or SystemClock()
    init_database(settings)
    uow = SqliteUnitOfWorkFactory(settings.db_path)
    tasks = TaskService(uow, clock)
    notes = NoteService(uow, clock, timedelta(seconds=settings.note_snapshot_interval_seconds))
    return Container(
        settings=settings,
        clock=clock,
        uow=uow,
        tasks=tasks,
        projects=ProjectService(uow, clock),
        notes=notes,
        links=LinkService(uow, clock),
        days=DayService(uow, clock, settings.default_capacity_minutes),
        capture=CaptureService(uow, clock, tasks, notes),
    )
