import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.domain.tasks import TaskStatus
from ppos.shared.errors import NotFoundError, ValidationError


def test_goal_tree_progress_and_links(container: Container) -> None:
    c = container
    year = c.goals.create("Grow to senior", "year", "2026")
    q4 = c.goals.create("Lead the retrieval launch", "quarter", "2026-Q4", parent_id=year.id)
    nov = c.goals.create("Ship the benchmark", "month", "2026-11", parent_id=q4.id)
    t1 = c.goals.add_task(nov.id, "Write the eval harness", 120)
    c.goals.add_task(nov.id, "Run baselines")
    c.tasks.move(t1.id, status=TaskStatus.DONE)
    # a project linked to the quarter goal counts too
    p = c.projects.create("Retrieval Platform")
    c.tasks.create("Project task", project_id=p.id)
    c.goals.link(q4.id, "project", p.id)

    tree = c.goals.tree(2026)
    assert [n.goal.id for n in tree.roots] == [year.id]
    q = tree.roots[0].children[0]
    m = q.children[0]
    assert m.progress.value == 0.5 and m.progress.basis == "1 of 2 tasks done"
    assert q.progress.basis == "0 of 1 tasks done" and q.project_ids == [p.id]
    assert tree.roots[0].progress.value == 0.0  # average of its one measured child
    assert {t.title for t in c.goals.tasks_of(q4.id)} == {"Project task"}

    c.goals.update(nov.id, {"status": "achieved"})
    nodes = c.goals.all_nodes()
    assert nodes[nov.id].progress.value == 1.0 and nodes[nov.id].goal.achieved_at
    c.goals.update(nov.id, {"status": "active"})
    assert c.goals.all_nodes()[nov.id].goal.achieved_at is None

    with pytest.raises(ValidationError):
        c.goals.update(q4.id, {"period": "2027-Q1"})  # would leave the year goal's period
    with pytest.raises(ValidationError):
        c.goals.create("Bad", "quarter", "2026-Q1", parent_id=nov.id)
    with pytest.raises(NotFoundError):
        c.tasks.create("x", goal_id="missing")

    # deleting a goal keeps its tasks and sub-goals
    c.goals.delete(q4.id)
    assert c.tasks.get(t1.id).goal_id == nov.id
    assert c.goals.all_nodes()[nov.id].goal.parent_id is None


def test_goal_links_career_expectation(container: Container) -> None:
    c = container
    e = c.career.add_expectation("L5", "Leads projects across a team")
    goal = c.goals.create("Lead the Q4 launch", "quarter", "2026-Q4")
    c.goals.link(goal.id, "expectation", e.id)
    assert c.goals.all_nodes()[goal.id].expectation_ids == [e.id]
    c.goals.link(goal.id, "expectation", e.id, on=False)
    with pytest.raises(NotFoundError):
        c.goals.link(goal.id, "expectation", "nope")


def test_goals_api(client: TestClient) -> None:
    body = {"title": "Speak at conferences", "horizon": "year", "period": "2026"}
    body |= {"progress_mode": "metric", "metric_target": 4, "metric_unit": "talks"}
    r = client.post("/api/goals", json=body)
    assert r.status_code == 201
    gid = r.json()["id"]
    client.patch(f"/api/goals/{gid}", json={"metric_current": 3})
    t = client.get("/api/goals", params={"year": 2026}).json()
    node = t["roots"][0]
    assert node["progress"]["value"] == 0.75 and node["progress"]["basis"] == "3 of 4 talks"
    assert node["period_start"] == "2026-01-01" and node["pace"] in ("ahead", "on track", "behind")
    q = client.post(
        "/api/goals", json={"title": "Q4 talk", "horizon": "quarter", "parent_id": gid}
    ).json()
    assert q["period"] == "2026-Q4"  # defaults to the current period
    task = client.post(
        f"/api/goals/{q['id']}/tasks", json={"title": "Submit CFP", "estimate_minutes": 45}
    ).json()
    assert task["goal_id"] == q["id"]
    assert [x["title"] for x in client.get(f"/api/goals/{q['id']}/tasks").json()] == ["Submit CFP"]
    e = client.post(
        "/api/career/expectations", json={"level": "L5", "text": "Shares knowledge widely"}
    ).json()
    assert (
        client.post(f"/api/goals/{q['id']}/expectations", json={"id": e["id"]}).status_code == 204
    )
    rows = client.get("/api/career").json()["levels"][0]["rows"]
    assert rows[0]["goals"][0]["title"] == "Q4 talk"
    assert client.delete(f"/api/goals/{q['id']}/expectations/{e['id']}").status_code == 204
    assert (
        client.post(
            "/api/goals", json={"title": "x", "horizon": "quarter", "period": "2026-Q9"}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/goals/{gid}").status_code == 204
    assert len(client.get("/api/goals/flat").json()) == 1
