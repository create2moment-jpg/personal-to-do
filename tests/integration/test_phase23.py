from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from ppos.application.ports import TaskQuery
from ppos.bootstrap import Container
from ppos.domain.planning import Commitment, SprintStatus
from ppos.domain.tasks import TaskStatus
from ppos.infrastructure.config import REPO_ROOT
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ConflictError, ValidationError

ICS = (REPO_ROOT / "fixtures" / "calendar" / "sample.ics").read_text(encoding="utf-8")
TUE = date(2026, 11, 24)


def test_ics_import_expands_recurrences_and_filters(container: Container) -> None:
    r = container.meetings.import_ics("sample.ics", ICS)
    assert r.series == 2
    meetings, _ = container.meetings.between(TUE, TUE)
    titles = sorted(m.title for m in meetings)
    assert titles == [
        "Architecture review",
        "Quarterly planning",
        "Team standup",
    ]  # no cancelled / free
    wed, _ = container.meetings.between(TUE + timedelta(days=1), TUE + timedelta(days=1))
    assert [m.title for m in wed] == []  # EXDATE
    thu, _ = container.meetings.between(TUE + timedelta(days=2), TUE + timedelta(days=2))
    assert [m.title for m in thu] == ["Team standup (moved)"]
    assert thu[0].duration_minutes == 30
    fri, _ = container.meetings.between(TUE + timedelta(days=3), TUE + timedelta(days=3))
    assert any(m.all_day and m.title == "Team offsite" for m in fri)
    assert all(m.organizer in (None, "Alex Example") for m in meetings)
    dt = container.meetings.day_time(TUE)
    assert dt.meeting_minutes == 15 + 60 + 60


def test_reimport_is_idempotent_and_keeps_user_choices(container: Container) -> None:
    container.meetings.import_ics("a.ics", ICS)
    meetings, _ = container.meetings.between(TUE, TUE)
    qp = next(m for m in meetings if m.title == "Quarterly planning")
    container.meetings.update(qp.id, {"status": "skipped", "rating": 2, "topic": "Planning"})
    container.meetings.update_series("standup-001@example.test", {"default_status": "skipped"})
    r2 = container.meetings.import_ics("a.ics", ICS)
    assert r2.created == 0
    meetings2, series = container.meetings.between(TUE, TUE)
    qp2 = next(m for m in meetings2 if m.id == qp.id)
    assert qp2.status is not None and qp2.status.value == "skipped" and qp2.rating == 2
    assert series["standup-001@example.test"].default_status == "skipped"
    assert container.meetings.day_time(TUE).meeting_minutes == 60  # only arch review counts
    # removing an event from the file cancels it on re-import
    container.meetings.import_ics(
        "a.ics",
        ICS.replace("SUMMARY:Quarterly planning", "SUMMARY:Quarterly planning\nSTATUS:CANCELLED"),
    )
    assert all(m.title != "Quarterly planning" for m in container.meetings.between(TUE, TUE)[0])


def test_imported_meetings_are_read_only(container: Container) -> None:
    container.meetings.import_ics("a.ics", ICS)
    m = container.meetings.between(TUE, TUE)[0][0]
    with pytest.raises(ValidationError):
        container.meetings.update(m.id, {"title": "hacked"})
    with pytest.raises(ValidationError):
        container.meetings.delete(m.id)


def test_invalid_ics_is_rejected(container: Container) -> None:
    with pytest.raises(ValidationError):
        container.meetings.import_ics("x.ics", "this is not a calendar at all")


def test_auto_capacity_follows_meetings_and_manual_override(container: Container) -> None:
    base = container.days.today_view(TUE).plan.capacity_minutes
    assert base == int(540 * 0.9)
    container.meetings.import_ics("a.ics", ICS)
    view = container.days.today_view(TUE)
    assert view.plan.capacity_minutes == int((540 - 135) * 0.9)
    assert len(view.meetings) == 3
    container.days.update_plan(TUE, {"capacity_minutes": 200})
    assert container.days.today_view(TUE).plan.capacity_minutes == 200
    container.days.update_plan(TUE, {"capacity_mode": "auto"})
    assert container.days.today_view(TUE).plan.capacity_minutes == int((540 - 135) * 0.9)


def test_log_call_and_insights(container: Container, clock: FixedClock) -> None:
    start = datetime(2026, 11, 24, 15, tzinfo=container.settings_service.tz())
    container.meetings.log_call(
        "ADR review", start, 30, people=["Priya", "Marcus"], topic="Retrieval", rating=4
    )
    container.meetings.log_call(
        "", start + timedelta(hours=1), 15, people=["priya"], topic="retrieval"
    )
    container.meetings.import_ics("a.ics", ICS)
    container.meetings.update_series(
        "arch-review-002@example.test", {"rating": 1, "topic": "Architecture"}
    )
    ins = container.meetings.insights(TUE - timedelta(days=6), TUE)
    people = {n: m for n, m, _ in ins.by_person}
    assert people == {"Priya": 45, "Marcus": 30}  # case-insensitive person matching
    topics = {n: m for n, m, _ in ins.by_topic}
    assert topics["Retrieval"] == 45 and topics["Architecture"] >= 60
    assert ins.calls_count == 2
    assert ins.avg_rating is not None
    assert any(r["title"] == "Architecture review" for r in ins.reconsider)


def test_capture_logs_call(container: Container) -> None:
    r = container.capture.capture("call: Priya / Roadmap chat ~20m #planning")
    assert (
        r.meeting is not None
        and r.meeting.duration_minutes == 20
        and r.meeting.kind.value == "call"
    )
    assert [p.name for p in container.meetings.people()] == ["Priya"]


def test_settings_persist_and_change_today(container: Container) -> None:
    container.settings_service.update({"timezone": "America/New_York", "work_start": "09:00"})
    assert container.settings_service.get().work_minutes == 480
    with pytest.raises(ValidationError):
        container.settings_service.update({"buffer_percent": 80})


def test_sprint_lifecycle(container: Container, clock: FixedClock) -> None:
    sprint = container.sprints.create(goal="Ship hybrid retrieval")
    assert (sprint.end_date - sprint.start_date).days == 13
    a = container.tasks.create("a", estimate_minutes=60)
    b = container.tasks.create("b", estimate_minutes=120)
    stretch = container.tasks.create("stretch")
    container.sprints.add_tasks(sprint.id, [a.id, b.id])
    container.sprints.add_tasks(sprint.id, [stretch.id], Commitment.STRETCH)
    container.sprints.start(sprint.id)
    with pytest.raises(ConflictError):
        container.sprints.create(start_date=sprint.start_date)  # overlap
    late = container.tasks.create("late")
    container.sprints.add_tasks(sprint.id, [late.id])
    container.tasks.move(a.id, status=TaskStatus.DONE)
    s = container.sprints.summary(sprint.id)
    assert (s.committed_total, s.committed_done, s.stretch_total) == (3, 1, 1)
    assert s.added_after_start == [late.id]
    assert s.burndown[0].remaining_minutes >= 0
    done, nxt, moved = container.sprints.complete(sprint.id, "next", lessons="Smaller tasks")
    assert done.status == SprintStatus.COMPLETED and nxt is not None and moved == 3
    assert {t.id for t in container.tasks.find(TaskQuery(sprint_id=nxt.id))} == {
        b.id,
        stretch.id,
        late.id,
    }
    assert nxt.start_date == done.end_date + timedelta(days=1)


def test_week_view_review_and_rollover(container: Container) -> None:
    sprint = container.sprints.create()
    container.sprints.start(sprint.id)
    t1 = container.tasks.create("mon", scheduled_date=date(2026, 11, 23), estimate_minutes=60)
    container.tasks.create("tue", scheduled_date=TUE)
    unscheduled = container.tasks.create("sprint only")
    container.sprints.add_tasks(sprint.id, [unscheduled.id])
    container.tasks.move(t1.id, status=TaskStatus.DONE)
    container.meetings.import_ics("a.ics", ICS)
    container.weeks.update_plan(
        TUE, {"objectives": [{"text": "Ship ADR"}, {"text": "Evals", "done": True}]}
    )
    v = container.weeks.view(TUE)
    assert v.week_start == date(2026, 11, 23) and len(v.days) == 7
    assert [o.text for o in v.plan.objectives] == ["Ship ADR", "Evals"]
    assert [t.title for t in v.sprint_backlog] == ["sprint only"]
    assert v.days[1].time.meeting_minutes == 135
    r = container.weeks.review(TUE)
    assert (r.planned, r.done, r.open) == (2, 1, 1) and r.meeting_minutes > 0
    assert container.weeks.roll_over(TUE) == 1
    assert container.tasks.find(TaskQuery(scheduled_date=date(2026, 11, 30)))[0].title == "tue"


def test_migration_from_v1_preserves_data(tmp_path: Path) -> None:
    from ppos.infrastructure import migrations as mig
    from ppos.infrastructure.config import DEFAULT_MIGRATIONS_DIR
    from ppos.infrastructure.db import connect

    conn = connect(tmp_path / "x.db")
    all_m = mig.discover(DEFAULT_MIGRATIONS_DIR)
    mig.upgrade(conn, all_m, target=1)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO tasks (id, title, status, created_at, updated_at)"
        " VALUES ('t', 'keep', 'backlog', ?, ?)",
        (now, now),
    )
    conn.execute("INSERT INTO daily_plans (day, capacity_minutes) VALUES ('2026-01-01', 300)")
    mig.upgrade(conn, all_m)
    row = conn.execute("SELECT title, sprint_id, commitment FROM tasks").fetchone()
    assert tuple(row) == ("keep", None, None)
    assert conn.execute("SELECT capacity_mode FROM daily_plans").fetchone()[0] == "auto"
    mig.downgrade(conn, all_m, steps=1)
    assert conn.execute("SELECT title FROM tasks").fetchone()[0] == "keep"
