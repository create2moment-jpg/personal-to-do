import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.domain.facts import Fact
from ppos.shared.clock import FixedClock, new_id
from ppos.shared.errors import ConflictError, ValidationError


def _fact(c: Container, clock: FixedClock, kind: str, text: str, status: str = "accepted") -> Fact:
    doc = c.documents.ingest(
        f"{new_id()}.md", f"# Review\n\n{text}\n".encode(), kind="performance_report"
    )
    now = clock.now()
    f = Fact(new_id(), doc.document.id, kind, text, text, 0.9, "m", "t", now, now, status=status)
    with c.uow() as uow:
        uow.facts.add(f)
        uow.commit()
    return f


def test_ratings_history_trend_and_gap(container: Container, clock: FixedClock) -> None:
    c = container
    s = c.skills.create("System design", "Engineering", target_level=4, level=2)
    clock.advance(days=100)
    c.skills.rate(s.id, 3, "led the retrieval design")
    row = c.skills.matrix().categories[0][1][0]
    assert row.level == 3 and row.previous == 2 and row.gap == 1
    assert [r.level for r in row.history] == [3, 2]
    with pytest.raises(ValidationError):
        c.skills.rate(s.id, 6)
    with pytest.raises(ConflictError):
        c.skills.create("system design")


def test_evidence_suggestions_and_links(container: Container, clock: FixedClock) -> None:
    c = container
    s = c.skills.create("Mentoring", "Leadership", description="coaching engineers")
    good = _fact(c, clock, "achievement", "Mentored two engineers through their first design docs")
    _fact(c, clock, "achievement", "Improved recall by 11 percent")
    proposed = _fact(c, clock, "achievement", "Mentored interns", status="proposed")
    dev = _fact(c, clock, "development_area", "Mentoring could be more structured")
    hints = c.skills.suggestions(s.id)
    assert [h.fact.id for h in hints] == [good.id] and "mentoring" in hints[0].shared
    assert c.skills.link(s.id, good.id) == "suggestion"
    with pytest.raises(ConflictError):
        c.skills.link(s.id, good.id)
    for bad in (proposed, dev):
        with pytest.raises(ValidationError):
            c.skills.link(s.id, bad.id)
    row = c.skills.matrix().categories[0][1][0]
    assert row.evidence[0].fact.id == good.id and row.suggestion_count == 0
    c.facts.review(good.id, status="rejected")
    assert c.skills.matrix().categories[0][1][0].evidence == []  # rejected evidence stops counting
    c.facts.review(good.id, status="accepted")
    c.skills.unlink(s.id, good.id)


def test_competency_candidates_and_growth_goal(container: Container, clock: FixedClock) -> None:
    c = container
    comp = _fact(c, clock, "competency", "Technical writing")
    m = c.skills.matrix()
    assert [f.id for f in m.candidates] == [comp.id] and m.levels[3][0] == "Practitioner"
    s = c.skills.create(
        "Technical writing", "Communication", level=2, target_level=4, from_fact_id=comp.id
    )
    assert c.skills.matrix().candidates == []
    goal = c.skills.growth_goal(s.id)
    assert goal.horizon == "quarter" and "Working (2) → Advanced (4)" in goal.title
    assert c.goals.all_nodes()[goal.id].skill_ids == [s.id]
    assert c.skills.matrix().categories[0][1][0].goal_ids == [goal.id]


def test_skills_api(client: TestClient) -> None:
    r = client.post(
        "/api/skills",
        json={"name": "Python", "category": "Engineering", "level": 4, "target_level": 5},
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    assert (
        client.post(f"/api/skills/{sid}/ratings", json={"level": 5, "note": "x"}).status_code == 201
    )
    m = client.get("/api/skills").json()
    row = m["categories"][0]["rows"][0]
    assert row["level"] == 5 and row["gap"] == 0 and m["levels"]["5"][0] == "Expert"
    assert (
        client.patch(f"/api/skills/{sid}", json={"category": "Languages"}).json()["category"]
        == "Languages"
    )
    assert client.get(f"/api/skills/{sid}/suggestions").json() == []
    g = client.post(f"/api/skills/{sid}/goal").json()
    assert g["horizon"] == "quarter"
    tree = client.get("/api/goals").json()
    assert any(n["skill_ids"] == [sid] for n in tree["roots"])
    assert client.post(f"/api/skills/{sid}/ratings", json={"level": 0}).status_code == 422
    assert client.delete(f"/api/skills/{sid}").status_code == 204


def test_skills_api_serialises_evidence(client: TestClient) -> None:
    from ppos.demo import seed_demo

    seed_demo(client.app.state.container)  # type: ignore[attr-defined]
    m = client.get("/api/skills")
    assert m.status_code == 200
    rows = [r for cat in m.json()["categories"] for r in cat["rows"]]
    assert any(r["evidence"] and r["evidence"][0]["fact"]["quote"] for r in rows)
    assert all(len(r["history"]) <= 12 for r in rows)
