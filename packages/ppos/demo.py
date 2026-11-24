"""Synthetic showcase data.

`ppos demo` fills a *separate* data directory with realistic but entirely
fictional content so the product can be shown to other people without
exposing anything personal. A ``DEMO`` marker file makes the UI display a
"Demo workspace" badge.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ppos.application.ports import NoteQuery, TaskQuery
from ppos.bootstrap import Container
from ppos.domain.notes import EntityType, NoteKind
from ppos.domain.tasks import Priority, TaskStatus
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
            "capacity_minutes": 330,
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

    marker = c.settings.local_data_dir / DEMO_MARKER
    marker.write_text("Synthetic demo workspace created by `ppos demo`.\n", encoding="utf-8")
    return {
        "projects": len(c.projects.find()),
        "tasks": len(c.tasks.find(TaskQuery(limit=1000))),
        "notes": len(c.notes.find(NoteQuery(limit=500))),
    }
