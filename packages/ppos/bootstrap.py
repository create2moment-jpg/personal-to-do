"""Composition root: wires settings, infrastructure and application services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from ppos.ai.output import clean_improved
from ppos.ai.prompts import load_template
from ppos.ai.provider import build_provider
from ppos.ai.runtime import AIRuntime, env_config
from ppos.application.assistant import AssistantService
from ppos.application.book import BookService
from ppos.application.capture import CaptureService
from ppos.application.career import CareerService
from ppos.application.daily import DayService
from ppos.application.documents import DocumentService, Extractor, JobRunner
from ppos.application.facts import FactService
from ppos.application.goals import GoalService
from ppos.application.insights import InsightsService
from ppos.application.meetings import MeetingService
from ppos.application.notes import LinkService, NoteService
from ppos.application.planning import SprintService, WeekService
from ppos.application.ports import SearchHit
from ppos.application.reviews import ReviewService
from ppos.application.settings import SettingsService
from ppos.application.skills import SkillService
from ppos.application.tasks import ProjectService, TaskService
from ppos.domain.meetings import DayTime, Meeting, MeetingSeries, day_time
from ppos.infrastructure.config import Settings, ensure_data_dir
from ppos.infrastructure.db import connect
from ppos.infrastructure.document_store import DocumentStore
from ppos.infrastructure.extract import EXTRACTOR_VERSION, extract_pages, pdf_title, sniff
from ppos.infrastructure.ics import parse_ics
from ppos.infrastructure.jobs import ThreadJobRunner
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
    ai: AIRuntime
    documents: DocumentService
    facts: FactService
    career: CareerService
    goals: GoalService
    skills: SkillService
    reviews: ReviewService
    insights: InsightsService
    assistant: AssistantService

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


def build_container(
    settings: Settings, clock: Clock | None = None, jobs: JobRunner | None = None
) -> Container:
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

    ai = AIRuntime(
        uow,
        env_config(settings.llm_provider, settings.llm_base_url, settings.llm_model,
                   settings.llm_timeout_seconds, settings.llm_embedding_model),
        settings.llm_allow_remote,
        # legacy .env Ollama setups keep the native API until settings are applied in the app
        env_provider=build_provider(
            settings.llm_provider, settings.llm_base_url, settings.llm_model,
            settings.llm_timeout_seconds, settings.llm_allow_remote,
        ) if settings.llm_provider == "ollama" else None,
    )  # fmt: skip

    def run_template(rel_path: str, values: dict[str, str]) -> tuple[str, str, str, int]:
        """Render a versioned prompt template and run it on the local model."""
        template = load_template(settings.prompts_dir, rel_path)
        system = template.meta.get("role", "You are a careful assistant.")
        temperature, max_tokens = ai.generation_params(
            settings.llm_temperature, settings.llm_max_tokens
        )
        r = ai.generate(
            system, template.render(**values), temperature=temperature, max_tokens=max_tokens
        )
        return r.text, r.model, template.ref, r.latency_ms

    def improver(original: str, style_instruction: str) -> tuple[str, str, str, int]:
        text, model, ref, latency = run_template(
            "02_writing/improve_prompt/v1.md",
            {"style_instruction": style_instruction, "prompt": original},
        )
        return clean_improved(text), model, ref, latency

    job_runner: JobRunner = jobs or ThreadJobRunner()

    documents = DocumentService(
        uow,
        clock,
        DocumentStore(settings.local_data_dir),
        Extractor(sniff=sniff, pages=extract_pages, title=pdf_title, version=EXTRACTOR_VERSION),
        job_runner,
    )
    documents.resume_pending()
    meetings.top_up_series()  # open-ended series you created stay filled ahead

    goals = GoalService(uow, clock, tasks)
    days = DayService(
        uow, clock, settings.default_capacity_minutes, day_meetings,
        unestimated_minutes=lambda: workspace.get().default_task_minutes,
    )  # fmt: skip
    assistant = AssistantService(uow, clock, ai, run_template, job_runner, days, workspace.tz)
    if ai.embedding_model:
        assistant.start_index()  # keep search by meaning fresh in the background

    return Container(
        settings=settings,
        clock=clock,
        uow=uow,
        tasks=tasks,
        projects=ProjectService(uow, clock),
        notes=notes,
        links=LinkService(uow, clock),
        days=days,
        capture=CaptureService(uow, clock, tasks, notes, meetings, workspace.tz),
        settings_service=workspace,
        meetings=meetings,
        sprints=sprints,
        weeks=WeekService(uow, clock, workspace, meetings, sprints),
        book=BookService(uow, clock, improver),
        ai=ai,
        documents=documents,
        facts=FactService(uow, clock, run_template, job_runner, enabled=lambda: ai.name != "none"),
        career=CareerService(uow, clock, tasks),
        goals=goals,
        skills=SkillService(uow, clock, goals),
        insights=InsightsService(uow, clock, meetings),
        assistant=assistant,
        reviews=ReviewService(
            uow, clock, meetings, goals, run_template, enabled=lambda: ai.name != "none"
        ),
    )
