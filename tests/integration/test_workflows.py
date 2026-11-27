from datetime import date

import pytest
from fastapi.testclient import TestClient

from ppos.application.ports import NoteQuery, TaskQuery
from ppos.bootstrap import Container
from ppos.domain.tasks import TaskStatus
from ppos.shared.errors import ValidationError

MON, TUE, THU = date(2026, 11, 23), date(2026, 11, 24), date(2026, 11, 26)


def test_plan_week_proposes_then_applies_only_what_you_keep(container: Container) -> None:
    c = container
    overdue = c.tasks.create("Finish ADR", scheduled_date=MON, estimate_minutes=60)
    due = c.tasks.create("Prepare demo", estimate_minutes=120, due_date=THU)
    c.tasks.create("Someday idea", due_date=date(2026, 12, 20))
    huge = c.tasks.create("Rewrite everything", estimate_minutes=3000, due_date=THU)
    c.goals.create("Ship hybrid retrieval", "month", "2026-11")

    run = c.workflows.run("plan_week")
    assert run.status == "proposed" and run.workflow == "plan_week"
    kinds = {a.params.get("task_id"): a for a in run.actions if a.kind == "schedule_task"}
    assert set(kinds) == {overdue.id, due.id}  # the far-off backlog item is left alone
    assert kinds[overdue.id].params["day"] == TUE.isoformat()
    assert date.fromisoformat(kinds[due.id].params["day"]) <= THU
    assert "overdue" in kinds[overdue.id].detail
    assert any("Rewrite everything" in n for n in run.notes)
    [obj] = [a for a in run.actions if a.kind == "set_objectives"]
    assert obj.params["objectives"] == ["Ship hybrid retrieval"]
    assert c.tasks.get(due.id).scheduled_date is None  # proposing changes nothing
    assert c.tasks.get(huge.id).scheduled_date is None

    applied = c.workflows.apply(run.id, [kinds[due.id].id, obj.id])
    assert c.tasks.get(due.id).scheduled_date is not None
    assert c.tasks.get(overdue.id).scheduled_date == MON  # not kept → untouched
    assert [o.text for o in c.weeks.view(TUE).plan.objectives] == ["Ship hybrid retrieval"]
    outcomes = {a.id: a.outcome for a in applied.actions}
    assert outcomes[obj.id] == "applied" and outcomes[kinds[overdue.id].id] == "skipped"
    assert c.workflows.get(run.id).status == "applied"
    with pytest.raises(ValidationError):
        c.workflows.apply(run.id, [])  # a run is applied once
    again = c.workflows.run("plan_week")
    with pytest.raises(ValidationError):
        c.workflows.apply(again.id, ["nope"])  # only actions of this run


def test_week_review_moves_unfinished_and_fills_wins_without_ai(container: Container) -> None:
    c = container
    done = c.tasks.create("Ship eval harness", scheduled_date=TUE)
    c.tasks.move(done.id, status=TaskStatus.DONE)
    left = c.tasks.create("Write docs", scheduled_date=THU)
    run = c.workflows.run("week_review")
    [move] = [a for a in run.actions if a.kind == "schedule_task"]
    assert move.params == {"task_id": left.id, "day": "2026-11-30"}
    [fill] = [a for a in run.actions if a.kind == "set_week_review"]
    assert fill.params["fields"] == {"review_wins": "- Ship eval harness"}
    assert any("No AI draft" in n for n in run.notes)
    c.weeks.update_plan(MON, {"review_wins": "My own words"})
    c.workflows.apply(run.id, [move.id, fill.id])
    assert c.tasks.get(left.id).scheduled_date == date(2026, 11, 30)
    assert c.weeks.view(TUE).plan.review_wins == "My own words\n- Ship eval harness"


def test_evidence_pack_links_suggests_gaps_and_writes_a_grounded_note(
    container: Container,
) -> None:
    c = container
    mentor = c.career.add_expectation("L5", "Mentors engineers on code review")
    oncall = c.career.add_expectation("L5", "Owns incident response for the platform")
    fact = c.facts.add_own(
        c.documents, "achievement", "Mentored two engineers through code review", "Weekly."
    )
    run = c.workflows.run("evidence_pack")
    assert run.title.endswith("L5") and "0 of 2" in run.summary
    by_kind = {a.kind: a for a in run.actions}
    assert by_kind["link_evidence"].params == {"expectation_id": mentor.id, "fact_id": fact.id}
    assert by_kind["gap_task"].params == {"expectation_id": oncall.id}
    assert run.actions[-1].kind == "evidence_note"
    assert any("not an assessment" in n for n in run.notes)

    c.workflows.apply(run.id, [a.id for a in run.actions])
    assert c.career.matrix().levels[0].covered == 1
    assert any("Build evidence" in t.title for t in c.tasks.find(TaskQuery(limit=500)))
    [note] = [n for n in c.notes.find(NoteQuery()) if n.title.startswith("Evidence pack — L5")]
    body = c.notes.get(note.id).body
    assert "Mentored two engineers through code review" in body and "No evidence yet" in body


def test_workflows_api(client: TestClient) -> None:
    assert "plan_week" in client.get("/api/workflows").json()
    r = client.post("/api/workflows/plan_week/run", json={})
    assert r.status_code == 200
    run = r.json()
    assert client.post("/api/workflows/nope/run", json={}).status_code == 422
    d = client.post(f"/api/workflows/runs/{run['id']}/dismiss").json()
    assert d["status"] == "dismissed"
    assert (
        client.post(f"/api/workflows/runs/{run['id']}/apply", json={"action_ids": []}).status_code
        == 422
    )
    assert client.get("/api/workflows/runs").json()[0]["id"] == run["id"]
    assert (
        client.post("/api/workflows/evidence_pack/run", json={}).status_code == 422
    )  # no framework
