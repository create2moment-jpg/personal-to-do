from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from ppos.ai.provider import AIUnavailableError
from ppos.application.reviews import ReviewService
from ppos.bootstrap import Container
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError


def _seed_month(c: Container) -> None:
    p = c.projects.create("Retrieval Platform")
    t = c.tasks.create(
        "Ship the benchmark", project_id=p.id, estimate_minutes=120, due_date=date(2026, 11, 30)
    )
    c.tasks.update(t.id, {"actual_minutes": 150})
    c.tasks.move(t.id, status=TaskStatus.DONE)
    c.tasks.create("Still open")
    g = c.goals.create("Publish the benchmark", "month", "2026-11")
    c.tasks.update(t.id, {"goal_id": g.id})
    c.goals.update(g.id, {"status": "achieved"})
    s = c.skills.create("System design", level=2)
    c.skills.rate(s.id, 3)
    c.days.save_review(
        date(2026, 11, 24),
        {"wins": "Benchmark adopted by two teams", "learning": "Measure first"},
        complete=True,
    )
    c.meetings.schedule("Planning", date(2026, 11, 24), "08:00", 45)


def test_snapshot_and_lifecycle(container: Container, clock: FixedClock) -> None:
    c = container
    _seed_month(c)
    r = c.reviews.open("month", "2026-11")
    s = r.snapshot
    assert (
        s["tasks"]["completed"] == 1
        and s["tasks"]["accuracy"] == 1.25
        and s["tasks"]["on_time"] == 1
    )
    assert s["tasks"]["by_project"][0][0] == "Retrieval Platform"
    assert s["time"]["meeting_minutes"] == 45 and s["time"]["meetings"] == 1
    assert any(gr["achieved_in_period"] for gr in s["goals"])
    assert s["skills"] == [{"name": "System design", "from": None, "to": 3}]
    assert s["notes"]["wins"][0][1] == "Benchmark adopted by two teams"
    ids = [i["id"] for i in s["items"]]
    assert {"S1", "T1", "M1", "G1", "W1", "L1"} <= set(ids)
    assert c.reviews.open("month", "2026-11").id == r.id  # one review per period

    c.reviews.update(r.id, {"highlights": "- Shipped the benchmark"})
    c.tasks.create("Late addition", status=TaskStatus.DONE)
    assert c.reviews.refresh(r.id).snapshot["tasks"]["completed"] == 2
    final = c.reviews.finalize(r.id)
    assert final.status == "final" and final.finalized_at
    with pytest.raises(ValidationError):
        c.reviews.update(r.id, {"highlights": "x"})
    with pytest.raises(ValidationError):
        c.reviews.refresh(r.id)
    c.reviews.finalize(r.id, final=False)
    md = c.reviews.markdown(r.id)
    assert md.startswith("# November 2026 — monthly review") and "Shipped the benchmark" in md

    due = {(d.kind, d.period): d for d in c.reviews.due()}
    assert (
        due[("month", "2026-10")].in_progress is False
        and due[("month", "2026-11")].review_id == r.id
    )
    assert ("bimonth", "2026-B5") in due and ("year", "2025") in due


def test_ai_draft_is_grounded(container: Container, clock: FixedClock) -> None:
    c = container
    _seed_month(c)
    r = c.reviews.open("month", "2026-11")
    with pytest.raises(AIUnavailableError):
        c.reviews.draft_with_ai(r.id)  # AI is off by default

    seen: dict[str, str] = {}

    def fake(path: str, values: dict[str, str]) -> tuple[str, str, str, int]:
        seen.update(values)
        first = values["items"].splitlines()[0]  # "[S1] 1 tasks completed, ..."
        item_id, text = first[1:3], first[5:]
        return (
            '{"highlights": ["' + text + " [" + item_id + ']", "Doubled revenue 200% [S1]"],'
            ' "challenges": [], "learnings": ["Unsupported claim"], "next_focus": []}',
            "qwen-test",
            "reviews.period_review@v1",
            3,
        )

    svc = ReviewService(c.uow, clock, c.meetings, c.goals, fake)
    d = svc.draft_with_ai(r.id)
    assert seen["period_label"] == "November 2026" and seen["kind"] == "monthly"
    assert len(d.sections["highlights"]) == 1 and d.sections["learnings"] == []
    assert len(d.dropped) == 2 and d.model == "qwen-test"


def test_empty_period_and_api(client: TestClient) -> None:
    due = client.get("/api/reviews/due").json()
    assert {d["kind"] for d in due} == {"month", "bimonth", "quarter", "year"}
    r = client.post("/api/reviews", json={"kind": "quarter", "period": "2026-Q3"}).json()
    assert r["label"] == "Q3 2026" and r["snapshot"]["tasks"]["completed"] == 0
    r2 = client.patch(f"/api/reviews/{r['id']}", json={"learnings": "Plan less"}).json()
    assert r2["learnings"] == "Plan less"
    assert client.post(f"/api/reviews/{r['id']}/draft").status_code in (422, 503)
    assert client.post(f"/api/reviews/{r['id']}/finalize").json()["status"] == "final"
    assert (
        client.post(f"/api/reviews/{r['id']}/finalize", params={"final": False}).json()["status"]
        == "draft"
    )
    assert "Q3 2026" in client.get(f"/api/reviews/{r['id']}/markdown").text
    assert (
        client.post("/api/reviews", json={"kind": "bimonth", "period": "2026-B9"}).status_code
        == 422
    )
    assert client.delete(f"/api/reviews/{r['id']}").status_code == 204
    assert client.get("/api/reviews").json() == []
    _ = timedelta


def test_week_and_sprint_drafts(container: Container, clock: FixedClock) -> None:
    c = container
    _seed_month(c)
    seen: list[dict[str, str]] = []

    def fake(path: str, values: dict[str, str]) -> tuple[str, str, str, int]:
        seen.append(values)
        first = values["items"].splitlines()[0]
        item_id, text = first[1:3], first[5:]
        return (
            '{"highlights": ["' + text + " [" + item_id + ']"], "learnings": ["made up [Z9]"]}',
            "m",
            "t",
            1,
        )

    svc = ReviewService(c.uow, clock, c.meetings, c.goals, fake)
    d = svc.draft_week(date(2026, 11, 23))
    assert seen[-1]["kind"] == "weekly" and "23 Nov 2026" in seen[-1]["period_label"]
    assert len(d.sections["highlights"]) == 1 and d.dropped and d.sections["learnings"] == []
    with pytest.raises(ValidationError):
        svc.draft_week(date(2026, 11, 24))  # not a Monday
    sp = c.sprints.create(
        name="Sprint 1", start_date=date(2026, 11, 16), end_date=date(2026, 11, 29)
    )
    d2 = svc.draft_sprint(sp.id)
    assert seen[-1]["kind"] == "sprint" and seen[-1]["period_label"].startswith("Sprint 1")
    assert d2.sections["highlights"]
