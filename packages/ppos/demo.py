"""Synthetic showcase data.

`ppos demo` fills a *separate* data directory with realistic but entirely
fictional content so the product can be shown to other people without
exposing anything personal. A ``DEMO`` marker file makes the UI display a
"Demo workspace" badge.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from ppos.application.ports import NoteQuery, TaskQuery
from ppos.bootstrap import Container
from ppos.domain.notes import EntityType, NoteKind
from ppos.domain.planning import Commitment
from ppos.domain.tasks import Priority, Task, TaskStatus
from ppos.shared.clock import new_id
from ppos.shared.errors import ValidationError

DEMO_MARKER = "DEMO"


def seed_demo(c: Container, today: date | None = None) -> dict[str, int]:
    today = today or c.clock.today()
    if c.tasks.find(TaskQuery(limit=1)):
        raise ValidationError("refusing to seed demo data into a workspace that already has tasks")
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    platform = c.projects.create(
        "Retrieval Platform", area="Engineering", color="#6366f1",
        description="Hybrid search service for internal documentation.",
    )  # fmt: skip
    evals = c.projects.create("Model Evaluation", area="Engineering", color="#0ea5e9")
    career = c.projects.create("Promotion Readiness", area="Career", color="#f59e0b")
    learning = c.projects.create("Deep Learning Reading Group", area="Learning", color="#10b981")

    def task(title: str, **kw: object) -> str:
        status = kw.pop("status", None)
        scheduled = kw.pop("scheduled_date", None)
        created = c.tasks.create(title, scheduled_date=scheduled, **kw)  # type: ignore[arg-type]
        if status is not None and status != created.status:
            c.tasks.move(created.id, status=status)  # type: ignore[arg-type]
        return created.id

    # Yesterday — mostly done, one rolled over.
    for title, est in [
        ("Benchmark BM25 vs. hybrid retrieval on the eval set", 120),
        ("Write design notes for chunking strategy", 60),
        ("1:1 with manager — growth plan", 30),
    ]:
        tid = task(title, scheduled_date=yesterday, estimate_minutes=est, project_id=platform.id)
        c.tasks.move(tid, status=TaskStatus.DONE)
        c.tasks.update(tid, {"actual_minutes": est + 15})
    c.days.update_plan(yesterday, {"objective": "Prove hybrid retrieval beats BM25"})
    c.days.save_review(
        yesterday,
        {
            "wins": "Hybrid retrieval +11% recall@10 on the internal eval set.",
            "learning": "Reciprocal-rank fusion is a strong, cheap baseline.",
            "blockers": "Waiting on GPU quota for the re-ranker experiment.",
            "tomorrow_first_task": "Draft the retrieval ADR",
        },
        complete=True,
    )

    # Today — a believable board.
    adr = task(
        "Draft ADR: hybrid retrieval with reciprocal-rank fusion",
        scheduled_date=today, estimate_minutes=90, priority=Priority.P1,
        project_id=platform.id, tags=["architecture", "writing"],
        description="Context, options considered, decision, consequences.",
    )  # fmt: skip
    c.tasks.move(adr, status=TaskStatus.IN_PROGRESS)
    c.tasks.update(adr, {"actual_minutes": 35})
    for sub in [
        "Summarise benchmark results",
        "List rejected alternatives",
        "Ask Priya for review",
    ]:
        task(sub, parent_id=adr)
    review = task(
        "Review PR #482 — streaming tokenizer", scheduled_date=today, estimate_minutes=30,
        priority=Priority.P2, project_id=platform.id, tags=["code-review"],
    )  # fmt: skip
    eval_task = task(
        "Run regression evals on the 4-bit quantised model", scheduled_date=today,
        estimate_minutes=60, priority=Priority.P2, project_id=evals.id, tags=["evals"],
    )  # fmt: skip
    task(
        "Re-ranker experiment on A100 pool", scheduled_date=today, estimate_minutes=45,
        status=TaskStatus.BLOCKED, project_id=platform.id, notes="Waiting on GPU quota (ticket INFRA-2291).",
    )  # fmt: skip
    task("Reply to infra thread about vector DB capacity", scheduled_date=today,
         estimate_minutes=15, status=TaskStatus.DONE)  # fmt: skip
    task(
        "Update team status doc", scheduled_date=today, estimate_minutes=20, status=TaskStatus.DONE
    )
    c.days.update_plan(
        today,
        {
            "objective": "Get the retrieval ADR ready for review",
            "top_priority_ids": [adr, eval_task, review],
        },
    )

    # Overdue + upcoming + backlog.
    task("Submit conference travel request", scheduled_date=today - timedelta(days=3),
         estimate_minutes=15, priority=Priority.P3)  # fmt: skip
    task("Prepare reading-group slides: Mixture-of-Experts routing", scheduled_date=tomorrow,
         estimate_minutes=90, project_id=learning.id, tags=["reading-group"])  # fmt: skip
    backlog: list[tuple[str, dict[str, Any]]] = [
        (
            "Collect evidence for 'technical leadership' competency",
            {
                "project_id": career.id,
                "priority": Priority.P2,
                "tags": ["career"],
                "due_date": today + timedelta(days=12),
            },
        ),
        ("Draft self-review for mid-year cycle", {"project_id": career.id, "due_date": today}),
        (
            "Evaluate sqlite-vec vs pgvector for local RAG",
            {"project_id": platform.id, "estimate_minutes": 120, "tags": ["rag"]},
        ),
        (
            "Write blog post: lessons from building an eval harness",
            {"project_id": evals.id, "tags": ["writing"], "estimate_minutes": 180},
        ),
        (
            "Add latency percentiles to eval dashboard",
            {"project_id": evals.id, "estimate_minutes": 60},
        ),
        (
            "Read: 'Lost in the Middle' (long-context retrieval)",
            {"project_id": learning.id, "tags": ["paper"]},
        ),
        (
            "Refactor ingestion pipeline into idempotent stages",
            {"project_id": platform.id, "priority": Priority.P3, "estimate_minutes": 240},
        ),
        ("Plan Q1 objectives with manager", {"project_id": career.id, "priority": Priority.P2}),
    ]
    for title, kw in backlog:
        task(title, **kw)

    # Notes.
    c.notes.create(
        "Hybrid retrieval — design notes",
        "## Problem\nBM25 misses paraphrases; dense retrieval misses exact identifiers.\n\n"
        "## Approach\n- Run **BM25** and **dense** retrieval in parallel\n- Fuse with reciprocal-rank fusion (k = 60)\n"
        "- Re-rank the top 50 with a cross-encoder *(blocked on GPU quota)*\n\n"
        "## Results\n| Method | Recall@10 |\n|---|---|\n| BM25 | 0.62 |\n| Dense | 0.66 |\n| Hybrid (RRF) | 0.73 |\n\n"
        "## Next steps\n- [x] Benchmark on eval set\n- [ ] Write ADR\n- [ ] Latency budget review\n",
        kind=NoteKind.TECHNICAL, project_id=platform.id, tags=["rag", "architecture"],
    )  # fmt: skip
    c.notes.create(
        "Weekly sync — Retrieval Platform",
        "**Attendees:** Priya, Marcus, me\n\n## Decisions\n- Ship hybrid retrieval behind a flag\n"
        "- Keep BM25 as fallback when the vector index is stale\n\n## Action items\n- [ ] Draft ADR (me)\n"
        "- [ ] Capacity estimate for the vector DB (Marcus)\n",
        kind=NoteKind.MEETING, note_date=yesterday, project_id=platform.id,
    )  # fmt: skip
    c.notes.create(
        body="Weekly digest that maps finished work to competencies automatically",
        kind=NoteKind.IDEA,
        tags=["career", "automation"],
    )
    c.notes.create(body="Cache embeddings per chunk hash so re-indexing is incremental",
                   kind=NoteKind.IDEA, tags=["rag"])  # fmt: skip
    c.notes.create(
        "Led cross-team retrieval benchmark",
        "Designed and ran the benchmark comparing BM25, dense and hybrid retrieval; "
        "result adopted by two teams. **Evidence:** benchmark report, design notes, sync decisions.",
        kind=NoteKind.CAREER_EVIDENCE, project_id=career.id, tags=["leadership", "impact"],
    )  # fmt: skip
    learning_note = c.notes.create(
        "Notes: Mixture-of-Experts routing",
        "- Top-k gating with load-balancing loss\n- Expert capacity factor trades quality for throughput\n"
        "- Open question: how does routing collapse show up in evals?\n",
        kind=NoteKind.LEARNING, project_id=learning.id, tags=["paper"],
    )  # fmt: skip
    journal = c.notes.journal_for(today, create=True)
    assert journal is not None
    c.notes.update(
        journal.id,
        {"body": "Focus: finish the ADR draft before lunch, evals in the afternoon.\n"},
    )
    c.links.link(EntityType.NOTE, learning_note.id, EntityType.PROJECT, learning.id)

    _seed_sprint_and_week(c, today)
    _seed_meetings(c, today)
    _seed_prompt_book(c)
    _seed_documents(c)

    marker = c.settings.local_data_dir / DEMO_MARKER
    marker.write_text("Synthetic demo workspace created by `ppos demo`.\n", encoding="utf-8")
    return {
        "projects": len(c.projects.find()),
        "tasks": len(c.tasks.find(TaskQuery(limit=1000))),
        "notes": len(c.notes.find(NoteQuery(limit=500))),
    }


def _seed_sprint_and_week(c: Container, today: date) -> None:
    start = today - timedelta(days=today.weekday())  # this Monday
    sprint = c.sprints.create(
        name="Sprint 12",
        goal="Hybrid retrieval ready for internal beta",
        start_date=start - timedelta(days=7),
        end_date=start + timedelta(days=6),
    )
    open_tasks = c.tasks.find(TaskQuery(limit=500))
    by_title = {t.title: t for t in open_tasks}
    committed = [
        t.id
        for title, t in by_title.items()
        if t.parent_id is None
        and any(
            k in title
            for k in (
                "ADR",
                "regression evals",
                "PR #482",
                "Re-ranker",
                "Benchmark",
                "design notes",
                "sqlite-vec",
            )
        )
    ]
    stretch = [
        t.id
        for title, t in by_title.items()
        if "blog post" in title or "latency percentiles" in title
    ]
    c.sprints.add_tasks(sprint.id, committed)
    c.sprints.add_tasks(sprint.id, stretch, Commitment.STRETCH)
    c.sprints.start(sprint.id)
    late = c.tasks.create(
        "Fix flaky retrieval eval on CI", estimate_minutes=45, priority=Priority.P2, tags=["evals"]
    )
    c.sprints.add_tasks(sprint.id, [late.id])  # a mid-sprint scope change

    # Backdate completions so the burndown tells a story.
    with c.uow() as uow:
        for i, tid in enumerate(
            t for t in committed if (x := uow.tasks.get(t)) and x.status == TaskStatus.DONE
        ):
            uow.conn.execute(
                "UPDATE tasks SET completed_at = ? WHERE id = ?",
                ((datetime.now(timezone.utc) - timedelta(days=6 - i * 2)).isoformat(), tid),
            )
        uow.commit()

    c.weeks.update_plan(
        today,
        {
            "objectives": [
                {"text": "Retrieval ADR approved", "done": False},
                {"text": "4-bit model regression evals green", "done": False},
                {"text": "Reading-group slides ready", "done": True},
            ]
        },
    )
    # Spread a few tasks across the week so the Week view is alive.
    for offset, title, est in [
        (1, "Pair with Marcus on index sharding", 60),
        (2, "Draft Q1 OKR proposal", 90),
        (3, "Prepare demo for platform review", 45),
    ]:
        c.tasks.create(title, scheduled_date=today + timedelta(days=offset), estimate_minutes=est)


def _ics_time(day: date, hhmm: str) -> str:
    return f"{day.strftime('%Y%m%d')}T{hhmm.replace(':', '')}00"


def _seed_meetings(c: Container, today: date) -> None:
    monday = today - timedelta(days=today.weekday())
    first = monday - timedelta(days=21)
    events = [
        (
            "demo-standup",
            "Team standup",
            first,
            "09:30",
            "09:45",
            "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
        ),
        (
            "demo-1on1",
            "1:1 with Priya (manager)",
            first + timedelta(days=1),
            "11:00",
            "11:30",
            "FREQ=WEEKLY;BYDAY=TU",
        ),
        (
            "demo-arch",
            "Architecture review",
            first + timedelta(days=3),
            "14:00",
            "15:00",
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=TH",
        ),
        ("demo-sync", "Platform sync", first, "10:00", "11:00", "FREQ=WEEKLY;BYDAY=MO"),
        (
            "demo-status",
            "Cross-team status update",
            first + timedelta(days=2),
            "16:00",
            "17:00",
            "FREQ=WEEKLY;BYDAY=WE",
        ),
        (
            "demo-allhands",
            "Engineering all-hands",
            first + timedelta(days=4),
            "15:00",
            "16:00",
            "FREQ=MONTHLY;BYDAY=1FR",
        ),
    ]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//PPOS demo//EN"]
    for uid, title, day, s, e, rule in events:
        lines += [
            "BEGIN:VEVENT", f"UID:{uid}@demo.invalid", f"SUMMARY:{title}",
            f"DTSTART;TZID=Europe/Berlin:{_ics_time(day, s)}", f"DTEND;TZID=Europe/Berlin:{_ics_time(day, e)}",
            f"RRULE:{rule}", "END:VEVENT",
        ]  # fmt: skip
    lines += [
        "BEGIN:VEVENT", "UID:demo-qbr@demo.invalid", "SUMMARY:Quarterly roadmap review",
        f"DTSTART;TZID=Europe/Berlin:{_ics_time(today + timedelta(days=2), '13:00')}",
        f"DTEND;TZID=Europe/Berlin:{_ics_time(today + timedelta(days=2), '14:30')}", "END:VEVENT",
        "END:VCALENDAR",
    ]  # fmt: skip
    c.meetings.import_ics("demo-calendar.ics", "\r\n".join(lines))
    c.meetings.update_series("demo-standup@demo.invalid", {"rating": 4, "topic": "Team"})
    c.meetings.update_series("demo-1on1@demo.invalid", {"rating": 5, "topic": "Career"})
    c.meetings.update_series("demo-arch@demo.invalid", {"rating": 4, "topic": "Architecture"})
    c.meetings.update_series("demo-status@demo.invalid", {"rating": 2, "topic": "Status"})
    c.meetings.update_series(
        "demo-allhands@demo.invalid", {"default_status": "skipped", "topic": "Company"}
    )

    tz = c.settings_service.tz()
    calls = [
        (-6, "10:30", 30, ["Priya"], "Retrieval", "ADR scope", 5),
        (-5, "14:00", 45, ["Marcus"], "Retrieval", "Index sharding", 4),
        (-4, "11:30", 20, ["Lena"], "Evals", "Eval harness questions", 3),
        (-3, "15:30", 60, ["Marcus", "Lena"], "Evals", "Debug flaky eval", 4),
        (-2, "13:30", 25, ["Jonas"], "Hiring", "Candidate debrief", 3),
        (-1, "16:00", 30, ["Priya"], "Career", "Promotion evidence", 5),
        (-1, "11:00", 40, ["Aisha"], "Status", "Status for leadership deck", 2),
    ]
    for offset, hhmm, minutes, people, topic, title, rating in calls:
        day = today + timedelta(days=offset)
        if day.weekday() >= 5:
            day -= timedelta(days=2)
        hh, mm = (int(x) for x in hhmm.split(":"))
        start = datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz)
        c.meetings.log_call(title, start, minutes, people=people, topic=topic, rating=rating)


def _seed_prompt_book(c: Container) -> None:
    from ppos.domain.book import NodeKind

    b = c.book.create_book(
        "Copilot prompts", emoji="🤖", description="Prompts I reuse with coding assistants"
    )
    code = c.book.create_node(b.id, NodeKind.CHAPTER, "Code quality", emoji="🧹")
    py = c.book.create_node(b.id, NodeKind.SECTION, "Python", emoji="🐍", parent_id=code.id)
    c.book.create_node(
        b.id, NodeKind.PAGE, "Add type hints", parent_id=py.id,
        body="Add precise type hints to {{file}}. Use modern built-in generics (list[str], X | None). "
        "Do not change behaviour. Run mypy --strict mentally and fix what it would flag.",
    )  # fmt: skip
    c.book.create_node(
        b.id, NodeKind.PAGE, "Refactor long function", parent_id=py.id,
        body="refactor {{function}} its too long, split it up",
    )  # fmt: skip
    tests = c.book.create_node(b.id, NodeKind.CHAPTER, "Testing", emoji="🧪")
    c.book.create_node(
        b.id, NodeKind.PAGE, "Unit tests for a function", parent_id=tests.id,
        body="Write pytest unit tests for {{function}} in {{file}}.\nCover: happy path, empty input, "
        "invalid types, and one property-based test with hypothesis.\nReturn only the test file.",
    )  # fmt: skip
    rag = c.book.create_node(b.id, NodeKind.CHAPTER, "ML & RAG", emoji="🧠")
    evals = c.book.create_node(b.id, NodeKind.SECTION, "Evaluation", parent_id=rag.id)
    c.book.create_node(
        b.id, NodeKind.PAGE, "Retrieval eval harness", parent_id=evals.id,
        body="Design an evaluation harness for our hybrid retriever: recall@k, MRR and nDCG on a labelled "
        "set of {{n}} queries. Explain how to avoid leakage between tuning and test sets.",
    )  # fmt: skip
    c.book.create_node(
        b.id, NodeKind.PAGE, "Explain this error", emoji="🐞",
        body="Explain this error and propose the smallest fix:\n\n{{error}}",
    )  # fmt: skip


def _seed_documents(c: Container) -> None:
    from ppos.infrastructure.config import REPO_ROOT

    framework = (REPO_ROOT / "fixtures" / "documents" / "level-framework.md").read_bytes()
    c.documents.ingest(
        "level-framework.md", framework, kind="framework", title="Engineering level framework"
    )
    review = (
        "MID-YEAR PERFORMANCE REVIEW (synthetic)\n\nSummary\n\nStrong ownership of the retrieval platform. "
        "Communicates trade-offs clearly.\n\f2. Achievements\n\nLed the hybrid retrieval benchmark adopted by "
        "two teams. Improved recall@10 by 11 percent.\n\f3. Development areas\n\nDelegate more; grow junior "
        "engineers through structured pairing.\n"
    )
    c.documents.ingest(
        "mid-year-review.txt", review.encode(), kind="performance_report", title="Mid-year review"
    )
    c.documents.ingest(
        "retrieval-design.md",
        b"# Hybrid retrieval design\n\n## Problem\n\nBM25 misses paraphrases; dense retrieval misses identifiers.\n\n"
        b"## Decision\n\nReciprocal-rank fusion of BM25 and dense results, k = 60.\n",
        kind="technical",
    )
    c.documents.jobs.wait_idle()
    _seed_career(c)
    _seed_goals(c)
    _seed_skills(c)
    _seed_history(c)


# (document title, kind, quote, statement or None to reuse the quote)
_DEMO_FACTS = [
    ("Engineering level framework", "level_expectation", "Delivers well-scoped features end to end with light guidance.", None),
    ("Engineering level framework", "level_expectation", "Writes tests and\nreviews code within the team.", "Writes tests and reviews code within the team."),
    ("Engineering level framework", "level_expectation", "Leads projects across a team.", None),
    ("Engineering level framework", "level_expectation", "Breaks down ambiguous problems, mentors others and\nimproves engineering practices.", "Breaks down ambiguous problems, mentors others and improves engineering practices."),
    ("Engineering level framework", "level_expectation", "Sets technical direction across several teams.", None),
    ("Engineering level framework", "level_expectation", "Drives architecture decisions with\nmeasurable impact on reliability, cost or velocity.", "Drives architecture decisions with measurable impact on reliability, cost or velocity."),
    ("Mid-year review", "strength", "Strong ownership of the retrieval platform.", None),
    ("Mid-year review", "strength", "Communicates trade-offs clearly.", None),
    ("Mid-year review", "achievement", "Led the hybrid retrieval benchmark adopted by two teams.", None),
    ("Mid-year review", "achievement", "Improved recall@10 by 11 percent.", None),
    ("Mid-year review", "development_area", "Delegate more; grow junior engineers through structured pairing.", None),
]  # fmt: skip


def _seed_career(c: Container) -> None:
    """Hand-curated, accepted facts (quotes verified against the demo documents) and two links,
    so the Career view is populated without a local model."""
    from ppos.domain.facts import Fact, is_grounded
    from ppos.shared.clock import new_id

    docs = {d.title: d for d in c.documents.find()}
    now = c.clock.now()
    with c.uow() as uow:
        for title, kind, quote, statement in _DEMO_FACTS:
            doc = docs[title]
            chunk = next(
                ch for ch in uow.documents.chunks(doc.id) if is_grounded(quote, str(ch["text"]))
            )
            page = chunk.get("page_start")
            section = chunk.get("section")
            uow.facts.add(
                Fact(
                    id=new_id(),
                    document_id=doc.id,
                    kind=kind,
                    statement=statement or quote,
                    quote=quote,
                    confidence=0.9,
                    model="demo (hand-curated)",
                    prompt_template="demo",
                    created_at=now,
                    updated_at=now,
                    chunk_id=str(chunk["id"]),
                    page=page if isinstance(page, int) else None,
                    section=str(section) if section else None,
                    status="accepted",
                    extractor_version=str(chunk.get("extractor_version") or ""),
                )
            )
        uow.commit()
    c.career.sync()
    facts = {f.statement: f for f in c.facts.find(status="accepted")}
    rows = {r.expectation.text: r.expectation for g in c.career.matrix().levels for r in g.rows}
    c.career.link(
        rows["Delivers well-scoped features end to end with light guidance."].id,
        facts["Strong ownership of the retrieval platform."].id,
    )
    c.career.link(
        rows["Sets technical direction across several teams."].id,
        facts["Led the hybrid retrieval benchmark adopted by two teams."].id,
    )


def _seed_goals(c: Container) -> None:
    """A year → quarter → month goal tree linked to tasks, a project and career expectations."""
    from ppos.application.ports import TaskQuery
    from ppos.domain.goals import period_of

    today = c.clock.today()
    year, quarter, month = (period_of(h, today) for h in ("year", "quarter", "month"))
    tasks = {t.title: t for t in c.tasks.find(TaskQuery(limit=1000))}
    rows = {r.expectation.text: r.expectation for g in c.career.matrix().levels for r in g.rows}
    projects = {p.name: p for p in c.projects.find()}

    senior = c.goals.create(
        "Grow into a senior engineer",
        "year",
        year,
        emoji="🚀",
        description="Lead work across the team and make it visible: launches, design docs, mentoring.",
    )
    launch = c.goals.create(
        "Take hybrid retrieval to internal beta",
        "quarter",
        quarter,
        parent_id=senior.id,
        emoji="🔎",
        description="Two teams using it, with an evaluation they trust.",
    )
    bench = c.goals.create(
        "Publish the retrieval benchmark", "month", month, parent_id=launch.id, emoji="📊"
    )
    for title in tasks:
        if any(k in title for k in ("Benchmark", "regression evals", "ADR")):
            c.tasks.update(tasks[title].id, {"goal_id": bench.id})
    mentor = c.goals.create(
        "Mentor a junior engineer through their first design",
        "quarter",
        quarter,
        parent_id=senior.id,
        emoji="🤝",
        progress_mode="manual",
        manual_progress=65,
    )
    talks = c.goals.create(
        "Share what we learn outside the team",
        "year",
        year,
        emoji="🎤",
        progress_mode="metric",
        metric_unit="talks",
        metric_start=0,
        metric_target=4,
        metric_current=3,
    )
    if "Retrieval Platform" in projects:
        c.goals.link(launch.id, "project", projects["Retrieval Platform"].id)
    for goal, text in (
        (launch, "Leads projects across a team."),
        (
            mentor,
            "Breaks down ambiguous problems, mentors others and improves engineering practices.",
        ),
        (talks, "Sets technical direction across several teams."),
    ):
        if text in rows:
            c.goals.link(goal.id, "expectation", rows[text].id)


def _seed_skills(c: Container) -> None:
    """A small skills matrix with history, targets, evidence and one growth goal."""
    facts = {f.statement: f for f in c.facts.find(status="accepted")}
    plan = [
        (
            "System design",
            "Engineering",
            2,
            3,
            4,
            "Led the hybrid retrieval benchmark adopted by two teams.",
        ),
        ("Information retrieval", "Engineering", 3, 3, 4, "Improved recall@10 by 11 percent."),
        ("Python", "Engineering", 4, 4, 4, None),
        ("Mentoring", "Leadership", 1, 2, 3, None),
        ("Communicating trade-offs", "Communication", 3, 3, 4, "Communicates trade-offs clearly."),
        ("Technical writing", "Communication", None, None, 3, None),
    ]
    for name, category, before, now_level, target, evidence in plan:
        s = c.skills.create(name, category, target_level=target)
        if before is not None:
            c.skills.rate(s.id, before, "start of the year")
        if now_level is not None and now_level != before:
            c.skills.rate(s.id, now_level, "after the retrieval launch")
        if evidence and evidence in facts:
            c.skills.link(s.id, facts[evidence].id)
    early = (datetime.now(timezone.utc) - timedelta(days=150)).isoformat()
    with c.uow() as uow:  # spread the early ratings over the past months for a real trend
        uow.conn.execute(
            "UPDATE skill_ratings SET rated_at = ? WHERE note = 'start of the year'", (early,)
        )
        uow.commit()
    mentoring = next(
        r.skill
        for _, rows in c.skills.matrix().categories
        for r in rows
        if r.skill.name == "Mentoring"
    )
    goal = next(
        (n for n in c.goals.all_nodes().values() if n.goal.title.startswith("Mentor a junior")),
        None,
    )
    if goal is not None:
        c.goals.link(goal.goal.id, "skill", mentoring.id)


_HISTORY = [  # (title, project, estimate, logged)
    ("Profile embedding batch job", "Retrieval Platform", 90, 120),
    ("Review chunking PR", "Retrieval Platform", 30, 25),
    ("Fix tokenizer edge case", "Retrieval Platform", 45, 70),
    ("Write eval dataset README", "Model Evaluation", 60, 55),
    ("Add recall@k to the eval harness", "Model Evaluation", 120, 150),
    ("Prepare reading-group notes", "Deep Learning Reading Group", 45, 40),
    ("Triage flaky integration tests", "Model Evaluation", 60, 95),
    ("Upgrade vector index library", "Retrieval Platform", 90, 80),
]


def _seed_history(c: Container) -> None:
    """Ten earlier weeks of finished work so Insights and Reviews show real trends."""
    projects = {p.name: p.id for p in c.projects.find()}
    today = c.clock.today()
    monday = today - timedelta(days=today.weekday())
    with c.uow() as uow:
        for week in range(1, 11):
            start = monday - timedelta(weeks=week)
            count = 3 + (week * 7) % 4  # 3–6 tasks, varying by week
            for k in range(count):
                title, project, est, logged = _HISTORY[(week * 3 + k) % len(_HISTORY)]
                day = start + timedelta(days=k % 5)
                done_at = datetime(day.year, day.month, day.day, 15, 0, tzinfo=timezone.utc)
                factor = 0.8 + ((week + k) % 5) * 0.12
                t = Task(
                    id=new_id(),
                    title=f"{title} ({start.strftime('%b %d')})",
                    created_at=done_at - timedelta(days=2),
                    updated_at=done_at,
                    status=TaskStatus.DONE,
                    estimate_minutes=est,
                    actual_minutes=int(logged * factor),
                    project_id=projects.get(project),
                    scheduled_date=day,
                    completed_at=done_at,
                    tags=["history"],
                )
                uow.tasks.add(t)
        uow.commit()
