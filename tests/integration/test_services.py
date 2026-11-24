from datetime import date, timedelta

import pytest

from ppos.application.ports import NoteQuery, TaskQuery
from ppos.bootstrap import Container
from ppos.domain.notes import EntityType, NoteKind
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ConflictError, NotFoundError, ValidationError

TODAY = date(2026, 11, 24)


def test_create_move_and_complete_task(container: Container) -> None:
    t = container.tasks.create("Ship slice", estimate_minutes=60)
    assert t.status == TaskStatus.BACKLOG
    t = container.tasks.move(t.id, scheduled_date=TODAY)
    assert (t.status, t.scheduled_date) == (TaskStatus.PLANNED, TODAY)
    t = container.tasks.move(t.id, status=TaskStatus.DONE)
    assert t.completed_at is not None
    assert container.tasks.get(t.id).status == TaskStatus.DONE


def test_starting_unscheduled_task_lands_on_today(container: Container) -> None:
    t = container.tasks.create("Unscheduled")
    t = container.tasks.move(t.id, status=TaskStatus.IN_PROGRESS)
    assert t.scheduled_date == TODAY


def test_update_rejects_status_and_unknown_fields(container: Container) -> None:
    t = container.tasks.create("x")
    with pytest.raises(ValidationError):
        container.tasks.update(t.id, {"status": "done"})
    with pytest.raises(NotFoundError):
        container.tasks.update(t.id, {"project_id": "missing"})


def test_dependencies_block_completion_and_cycles(container: Container) -> None:
    a = container.tasks.create("a")
    b = container.tasks.create("b")
    container.tasks.add_dependency(b.id, a.id)
    with pytest.raises(ConflictError):
        container.tasks.add_dependency(a.id, b.id)
    with pytest.raises(ValidationError):
        container.tasks.move(b.id, status=TaskStatus.DONE)
    container.tasks.move(a.id, status=TaskStatus.DONE)
    assert container.tasks.move(b.id, status=TaskStatus.DONE).status == TaskStatus.DONE


def test_subtasks_and_parent_cycle(container: Container) -> None:
    parent = container.tasks.create("parent")
    child = container.tasks.create("child", parent_id=parent.id)
    assert [t.id for t in container.tasks.find(TaskQuery(parent_id=parent.id))] == [child.id]
    with pytest.raises(ValidationError):
        container.tasks.update(parent.id, {"parent_id": child.id})
    container.tasks.delete(parent.id)
    with pytest.raises(NotFoundError):
        container.tasks.get(child.id)  # cascades


def test_today_view_capacity_overdue_and_rollover(container: Container) -> None:
    container.days.update_plan(TODAY, {"capacity_minutes": 60, "objective": "Focus"})
    a = container.tasks.create("a", scheduled_date=TODAY, estimate_minutes=45)
    container.tasks.create("b", scheduled_date=TODAY, estimate_minutes=30)
    old = container.tasks.create("old", scheduled_date=TODAY - timedelta(days=2))
    container.tasks.create("due", due_date=TODAY)

    view = container.days.today_view(TODAY)
    assert view.plan.objective == "Focus"
    assert view.capacity.overcommitted
    assert [t.id for t in view.overdue] == [old.id]
    assert [t.title for t in view.due_today_unscheduled] == ["due"]

    container.tasks.move(a.id, status=TaskStatus.DONE)
    moved = container.days.roll_over(TODAY)
    assert [t.title for t in moved] == ["b"]
    assert container.days.today_view(TODAY + timedelta(days=1)).tasks[0].title == "b"


def test_top_priorities_must_exist(container: Container) -> None:
    with pytest.raises(NotFoundError):
        container.days.update_plan(TODAY, {"top_priority_ids": ["nope"]})


def test_review_draft_and_save(container: Container) -> None:
    container.tasks.create("open one", scheduled_date=TODAY)
    draft = container.days.review_draft(TODAY)
    assert draft["tomorrow_first_task"] == "open one"
    plan = container.days.save_review(TODAY, {"wins": "shipped"}, complete=True)
    assert plan.review.wins == "shipped"
    assert plan.review.completed_at is not None


def test_note_autosave_coalesces_versions(container: Container, clock: FixedClock) -> None:
    note = container.notes.create("Draft", "v1")
    container.notes.update(note.id, {"body": "v1 edit"})
    container.notes.update(note.id, {"body": "v1 edit 2"})
    assert [v.version for v in container.notes.versions(note.id)] == [1]
    assert container.notes.get_version(note.id, 1).body == "v1 edit 2"

    clock.advance(minutes=5)
    container.notes.update(note.id, {"body": "v2"})
    versions = container.notes.versions(note.id)
    assert [v.version for v in versions] == [2, 1]
    assert versions[1].body == "v1 edit 2"  # older window untouched

    restored = container.notes.restore(note.id, 1)
    assert restored.body == "v1 edit 2"
    assert restored.version == 3  # restore appends, never rewrites history


def test_metadata_only_update_does_not_create_version(
    container: Container, clock: FixedClock
) -> None:
    note = container.notes.create("n", "body")
    clock.advance(hours=1)
    container.notes.update(note.id, {"tags": ["x"]})
    assert len(container.notes.versions(note.id)) == 1


def test_journal_is_unique_per_day(container: Container) -> None:
    j1 = container.notes.journal_for(TODAY, create=True)
    j2 = container.notes.journal_for(TODAY, create=True)
    assert j1 is not None and j2 is not None and j1.id == j2.id
    assert container.notes.find(NoteQuery(kind=NoteKind.JOURNAL))[0].note_date == TODAY


def test_links_and_cleanup(container: Container) -> None:
    t = container.tasks.create("t")
    n = container.notes.create("n")
    link = container.links.link(EntityType.NOTE, n.id, EntityType.TASK, t.id)
    again = container.links.link(EntityType.TASK, t.id, EntityType.NOTE, n.id)
    assert link.id == again.id
    container.notes.delete(n.id)
    assert container.links.links_for(EntityType.TASK, t.id) == []


def test_search_finds_tasks_and_notes_and_is_injection_safe(container: Container) -> None:
    container.tasks.create("Evaluate retrieval quality", description="bm25 baseline")
    container.notes.create("RAG notes", "chunking strategies for retrieval")
    hits = container.search("retriev")
    assert {h.entity_type for h in hits} == {EntityType.TASK, EntityType.NOTE}
    assert container.search('") OR (*') == []
    assert container.search("NEAR(a b)") == []


def test_capture_creates_task_or_idea(container: Container) -> None:
    container.projects.create("ML Platform")
    r = container.capture.capture("Fix flaky eval +ml-platform @today !1")
    assert r.task is not None and r.task.project_id is not None
    assert r.task.scheduled_date == TODAY
    r = container.capture.capture("Fix it +unknown")
    assert r.warnings and "unknown" in r.warnings[0]
    r = container.capture.capture("idea: weekly digest #writing")
    assert r.note is not None and r.note.kind == NoteKind.IDEA


def test_audit_log_is_append_only(container: Container) -> None:
    import sqlite3

    container.tasks.create("audited")
    with container.uow() as uow:
        rows = uow.conn.execute("SELECT action FROM audit_log").fetchall()
        assert [r[0] for r in rows] == ["create"]
        with pytest.raises(sqlite3.IntegrityError):
            uow.conn.execute("UPDATE audit_log SET action = 'x'")


def test_concurrent_writers_do_not_fail_with_database_locked(container: Container) -> None:
    """Regression: read-then-write units used to hit 'database is locked'."""
    from concurrent.futures import ThreadPoolExecutor

    task = container.tasks.create("contended", scheduled_date=TODAY)
    note = container.notes.create("n", "x")

    def work(i: int) -> None:
        if i % 3 == 0:
            container.tasks.update(task.id, {"actual_minutes": i})
        elif i % 3 == 1:
            container.notes.update(note.id, {"body": f"edit {i}"})
        else:
            container.tasks.create(f"t{i}", scheduled_date=TODAY)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(60)))
    assert len(container.days.today_view(TODAY).tasks) == 1 + 20
