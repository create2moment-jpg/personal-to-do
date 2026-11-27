from datetime import date, timedelta

from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import FixedClock


def test_weekly_trends(container: Container, clock: FixedClock) -> None:
    c = container
    today = clock.today()  # Tue 2026-11-24
    p = c.projects.create("Retrieval Platform")
    a = c.tasks.create("A", project_id=p.id, estimate_minutes=60, scheduled_date=today)
    c.tasks.update(a.id, {"actual_minutes": 90})
    c.tasks.move(a.id, status=TaskStatus.DONE)
    c.tasks.create("B", scheduled_date=today - timedelta(days=1), estimate_minutes=30)  # missed
    c.tasks.create("C", scheduled_date=today)  # today is not over: not counted yet
    c.meetings.schedule("Sync", today, "10:00", 45)
    t = c.insights.trends(4)
    assert [w.week_start for w in t.weeks][-1] == date(2026, 11, 23) and len(t.weeks) == 4
    w = t.weeks[-1]
    assert (w.tasks_done, w.done_estimate, w.actual_minutes, w.accuracy) == (1, 60, 90, 1.5)
    assert (w.planned, w.planned_done, w.reliability) == (2, 1, 0.5)
    assert w.meeting_minutes == 45 and w.work_minutes > 0
    assert t.weeks[0].tasks_done == 0 and t.weeks[0].reliability is None
    assert t.by_project == [("Retrieval Platform", 90, 1)]


def test_trends_api(client: TestClient) -> None:
    r = client.get("/api/insights/trends", params={"weeks": 8}).json()
    assert len(r["weeks"]) == 8 and r["weeks"][0]["reliability"] is None
    assert client.get("/api/insights/trends", params={"weeks": 1}).status_code == 422


def test_future_days_do_not_count_as_missed(container: Container, clock: FixedClock) -> None:
    today = clock.today()
    container.tasks.create("Later this week", scheduled_date=today + timedelta(days=2))
    assert container.insights.trends(2).weeks[-1].planned == 0
