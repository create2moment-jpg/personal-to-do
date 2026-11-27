from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from ppos.application.ports import TaskQuery
from ppos.bootstrap import Container
from ppos.domain.tasks import Priority, TaskStatus
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError

TUE = date(2026, 11, 24)


def test_completing_a_repeating_task_creates_the_next(
    container: Container, clock: FixedClock
) -> None:
    c = container
    goal = c.goals.create("Stay on top of reviews", "quarter", "2026-Q4")
    t = c.tasks.create(
        "Weekly status report", scheduled_date=TUE, due_date=TUE + timedelta(days=1),
        estimate_minutes=20, priority=Priority.P2, tags=["report"], goal_id=goal.id,
        recurrence="freq=weekly;byday=tu",
    )  # fmt: skip
    assert t.recurrence == "FREQ=WEEKLY;BYDAY=TU"
    c.tasks.move(t.id, status=TaskStatus.DONE)
    nxt = [x for x in c.tasks.find(TaskQuery(limit=100)) if x.id != t.id and x.title == t.title]
    assert len(nxt) == 1
    n = nxt[0]
    assert n.scheduled_date == date(2026, 12, 1) and n.due_date == date(2026, 12, 2)
    assert (n.status, n.estimate_minutes, n.priority, n.tags, n.goal_id) == (
        TaskStatus.PLANNED,
        20,
        Priority.P2,
        ["report"],
        goal.id,
    )
    assert n.recurrence == "FREQ=WEEKLY;BYDAY=TU" and c.tasks.get(t.id).recurrence is None

    # undo + complete again does not duplicate
    c.tasks.move(t.id, status=TaskStatus.PLANNED)
    c.tasks.move(t.id, status=TaskStatus.DONE)
    assert len([x for x in c.tasks.find(TaskQuery(limit=100)) if x.title == t.title]) == 2


def test_unscheduled_repeating_task_goes_to_backlog(container: Container) -> None:
    t = container.tasks.create("Review finances", recurrence="FREQ=MONTHLY")
    container.tasks.move(t.id, status=TaskStatus.DONE)
    follow = [
        x
        for x in container.tasks.find(TaskQuery(statuses=(TaskStatus.BACKLOG,), limit=50))
        if x.title == "Review finances"
    ]
    assert follow and follow[0].scheduled_date is None and follow[0].recurrence == "FREQ=MONTHLY"


def test_invalid_rules_are_rejected(container: Container, client: TestClient) -> None:
    with pytest.raises(ValidationError):
        container.tasks.create("x", recurrence="FREQ=YEARLY")
    t = client.post("/api/tasks", json={"title": "API task"}).json()
    r = client.patch(f"/api/tasks/{t['id']}", json={"recurrence": "FREQ=DAILY;COUNT=2"})
    assert r.status_code == 422
    ok = client.patch(f"/api/tasks/{t['id']}", json={"recurrence": "freq=daily;interval=2"})
    assert ok.json()["recurrence"] == "FREQ=DAILY;INTERVAL=2"


def test_capture_creates_a_repeating_task(client: TestClient) -> None:
    pv = client.post("/api/capture/preview", json={"text": "Water plants every mon @mon"}).json()
    assert pv["repeat"] == "Weekly on Mon"
    t = client.post("/api/capture", json={"text": "Water plants every mon @mon"}).json()["task"]
    assert t["recurrence"] == "FREQ=WEEKLY;BYDAY=MO"
