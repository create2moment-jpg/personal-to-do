from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.domain.tasks import Priority, TaskStatus
from ppos.shared.errors import ValidationError

DAY = date(2026, 11, 24)  # Tuesday; the fixed clock is 09:00 UTC on this day


@pytest.fixture
def c(container: Container) -> Container:
    container.settings_service.update({"timezone": "UTC"})
    return container


def test_timeline_and_timebox(c: Container) -> None:
    c.meetings.log_call("Standup", datetime(2026, 11, 24, 9, 30, tzinfo=timezone.utc), 30)
    a = c.tasks.create("Write ADR", scheduled_date=DAY, estimate_minutes=60)
    b = c.tasks.create("Review PR", scheduled_date=DAY)
    tl = c.timeline.timeline(DAY)
    assert tl.window is not None and (tl.window.start, tl.window.end) == (480, 1020)
    assert [m.meeting.title for m in tl.meetings] == ["Standup"]
    assert {t.id for t in tl.unboxed} == {a.id, b.id} and tl.free_minutes == 540 - 30
    c.tasks.timebox(a.id, DAY, "10:00")
    tl = c.timeline.timeline(DAY)
    [box] = tl.boxes
    assert box.task.id == a.id and (box.span.start, box.span.end) == (600, 660)
    assert tl.free_minutes == 540 - 30 - 60 and [t.id for t in tl.unboxed] == [b.id]
    # moving the task to another day drops its start time
    moved = c.tasks.move(a.id, scheduled_date=date(2026, 11, 25))
    assert moved.timebox_start is None
    with pytest.raises(ValidationError):
        c.tasks.timebox(a.id, DAY, "25:00")


def test_timebox_schedules_a_backlog_task(c: Container) -> None:
    t = c.tasks.create("Plan sprint")
    boxed = c.tasks.timebox(t.id, DAY, "14:00")
    assert boxed.scheduled_date == DAY and boxed.status == TaskStatus.PLANNED
    assert c.tasks.timebox(t.id, DAY, None).timebox_start is None


def test_propose_fills_free_time_after_now_and_applies(c: Container) -> None:
    c.meetings.log_call("Standup", datetime(2026, 11, 24, 9, 30, tzinfo=timezone.utc), 30)
    low = c.tasks.create("Inbox zero", scheduled_date=DAY, estimate_minutes=30)
    top = c.tasks.create("Ship fix", scheduled_date=DAY, estimate_minutes=30, priority=Priority.P1)
    huge = c.tasks.create("Rewrite everything", scheduled_date=DAY, estimate_minutes=600)
    p = c.timeline.propose(DAY)
    assert [(t.id, pl.start) for t, pl in p.placements] == [(top.id, 540), (low.id, 600)]
    assert [t.id for t in p.unplaced] == [huge.id]
    assert c.tasks.get(top.id).timebox_start is None  # a proposal saves nothing
    c.timeline.apply(DAY, [(top.id, "09:00"), (low.id, "10:00")])
    assert c.tasks.get(low.id).timebox_start == "10:00"


def test_repeating_task_keeps_its_time(c: Container) -> None:
    t = c.tasks.create("Plan the day", scheduled_date=DAY, recurrence="FREQ=DAILY")
    c.tasks.timebox(t.id, DAY, "08:30")
    c.tasks.move(t.id, status=TaskStatus.DONE)
    [nxt] = [x for x in c.timeline.timeline(date(2026, 11, 25)).boxes]
    assert nxt.task.title == "Plan the day" and nxt.task.timebox_start == "08:30"


def test_timebox_api(client: TestClient) -> None:
    client.patch("/api/settings", json={"timezone": "UTC"})
    t = client.post("/api/tasks", json={"title": "Focus block", "estimate_minutes": 45}).json()
    r = client.put(f"/api/tasks/{t['id']}/timebox", json={"day": "2026-11-26", "start": "13:15"})
    assert r.status_code == 200 and r.json()["timebox_start"] == "13:15"
    tl = client.get("/api/days/2026-11-26/timeline").json()
    assert tl["boxes"][0]["start"] == "13:15" and tl["boxes"][0]["end"] == "14:00"
    assert tl["window"] == {"start": "08:00", "end": "17:00", "minutes": 540}
    prop = client.post("/api/days/2026-11-26/timebox/propose").json()
    assert prop == {"day": "2026-11-26", "placements": [], "unplaced": []}
    bad = client.put(f"/api/tasks/{t['id']}/timebox", json={"day": "2026-11-26", "start": "1pm"})
    assert bad.status_code == 422
    sat = client.get("/api/days/2026-11-28/timeline").json()
    assert sat["window"] is None and sat["free"] == []
