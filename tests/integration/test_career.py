import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.domain.facts import Fact
from ppos.shared.clock import FixedClock, new_id
from ppos.shared.errors import ConflictError, ValidationError


def _doc(c: Container, name: str = "framework.md") -> str:
    body = f"# {name}\n\nSome text about levels and expectations for engineers.\n".encode()
    return c.documents.ingest(name, body, kind="framework").document.id


def _fact(
    c: Container,
    clock: FixedClock,
    doc_id: str,
    kind: str,
    statement: str,
    status: str = "accepted",
    section: str | None = None,
) -> Fact:
    now = clock.now()
    f = Fact(
        id=new_id(),
        document_id=doc_id,
        kind=kind,
        statement=statement,
        quote=statement,
        confidence=0.9,
        model="m",
        prompt_template="t",
        created_at=now,
        updated_at=now,
        section=section,
        status=status,
    )
    with c.uow() as uow:
        uow.facts.add(f)
        uow.commit()
    return f


def test_framework_sync_is_idempotent_and_follows_review(
    container: Container, clock: FixedClock
) -> None:
    c = container
    d = _doc(c)
    e5 = _fact(
        c,
        clock,
        d,
        "level_expectation",
        "Leads technical design across teams",
        section="L5 — Senior",
    )
    _fact(c, clock, d, "level_expectation", "Mentors engineers", section="L6 Staff")
    _fact(c, clock, d, "level_expectation", "Still proposed", status="proposed", section="L5")
    _fact(c, clock, d, "level_expectation", "No level here")
    assert c.career.sync() == 3
    assert c.career.sync() == 0
    m = c.career.matrix()
    assert [g.level for g in m.levels] == ["L5", "L6", "Unlevelled"]
    assert m.levels[0].total == 1 and m.levels[0].covered == 0
    # rejecting the source fact removes the (unlinked) expectation on next sync
    c.facts.review(e5.id, status="rejected")
    assert [g.level for g in c.career.matrix().levels] == ["L6", "Unlevelled"]


def test_evidence_links_suggestions_and_coverage(container: Container, clock: FixedClock) -> None:
    c = container
    d = _doc(c, "review.md")
    exp = c.career.add_expectation("L5", "Leads technical design of systems used by several teams")
    good = _fact(c, clock, d, "achievement", "Led the retrieval system design adopted by two teams")
    _fact(c, clock, d, "achievement", "Improved recall at 10 by 11 percent")
    pending = _fact(c, clock, d, "achievement", "Designed systems for teams", status="proposed")
    goal = _fact(c, clock, d, "goal", "Design systems for more teams")

    sugg = c.career.suggestions(exp.id)
    assert [s.fact.id for s in sugg] == [good.id]  # proposed facts and goals are never evidence
    assert set(sugg[0].shared) >= {"design", "systems", "teams"}
    assert c.career.matrix().levels[0].rows[0].suggestion_count == 1

    with pytest.raises(ValidationError):
        c.career.link(exp.id, pending.id)
    with pytest.raises(ValidationError):
        c.career.link(exp.id, goal.id)
    link = c.career.link(exp.id, good.id)
    assert link.origin == "suggestion" and link.score
    with pytest.raises(ConflictError):
        c.career.link(exp.id, good.id)

    g = c.career.matrix().levels[0]
    assert g.covered == 1 and g.total == 1 and g.rows[0].evidence[0].document_title
    assert c.career.suggestions(exp.id) == []

    # evidence that is later rejected stops counting
    c.facts.review(good.id, status="rejected")
    assert c.career.matrix().levels[0].covered == 0
    c.facts.review(good.id, status="accepted")
    c.career.unlink(exp.id, good.id)
    assert c.career.matrix().levels[0].covered == 0


def test_gap_task_and_delete(container: Container, clock: FixedClock) -> None:
    c = container
    d = _doc(c)
    f = _fact(c, clock, d, "level_expectation", "Owns the roadmap of a product area", section="L6")
    c.career.sync()
    exp = c.career.matrix().levels[0].rows[0].expectation
    task = c.career.gap_task(exp.id)
    assert "L6" in task.title and "career" in task.tags
    c.career.delete_expectation(exp.id)  # framework row → its fact is rejected, sync keeps it away
    assert c.career.matrix().levels == []
    with c.uow() as uow:
        got = uow.facts.get(f.id)
        assert got is not None and got.status == "rejected"


def test_career_api(client: TestClient) -> None:
    r = client.get("/api/career")
    assert r.status_code == 200 and r.json()["levels"] == [] and "not" in r.json()["disclaimer"]
    r = client.post(
        "/api/career/expectations", json={"level": "L5", "text": "Drives design reviews"}
    )
    assert r.status_code == 201
    eid = r.json()["id"]
    assert (
        client.patch(f"/api/career/expectations/{eid}", json={"competency": "Craft"}).json()[
            "competency"
        ]
        == "Craft"
    )
    m = client.get("/api/career").json()
    assert m["levels"][0]["level"] == "L5" and m["levels"][0]["covered"] == 0
    assert client.get(f"/api/career/expectations/{eid}/suggestions").json() == []
    r = client.post(f"/api/career/expectations/{eid}/evidence", json={"fact_id": "nope"})
    assert r.status_code == 404
    t = client.post(f"/api/career/expectations/{eid}/gap-task")
    assert t.status_code == 201 and t.json()["title"].startswith("Build evidence (L5)")
    assert client.delete(f"/api/career/expectations/{eid}").status_code == 204
    assert client.get("/api/career").json()["levels"] == []


def test_career_api_serialises_linked_evidence(client: TestClient) -> None:
    from ppos.demo import seed_demo

    seed_demo(client.app.state.container)  # type: ignore[attr-defined]
    m = client.get("/api/career").json()
    evidence = [ev for lvl in m["levels"] for r in lvl["rows"] for ev in r["evidence"]]
    assert len(evidence) == 2 and all(
        ev["fact"]["quote"] and ev["document_title"] for ev in evidence
    )
    row = next(r for r in m["levels"][1]["rows"] if r["suggestion_count"])
    s = client.get(f"/api/career/expectations/{row['expectation']['id']}/suggestions").json()
    assert s and s[0]["shared"] and s[0]["fact"]["status"] == "accepted"
    r = client.post(
        f"/api/career/expectations/{row['expectation']['id']}/evidence",
        json={"fact_id": s[0]["fact"]["id"]},
    )
    assert r.status_code == 201 and r.json()["origin"] == "suggestion"


def test_own_evidence_is_a_grounded_note(container: Container, clock: FixedClock) -> None:
    c = container
    exp = c.career.add_expectation("L5", "Mentors engineers")
    f = c.facts.add_own(
        c.documents,
        "achievement",
        "Mentored Ana through her first design review",
        "Weekly pairing in October.",
    )
    assert f.status == "accepted" and f.epistemic == "self_reported" and f.quote == f.statement
    doc, _ = c.documents.get(f.document_id)
    assert doc.kind == "own_note" and doc.title.startswith("My note:")
    c.career.link(exp.id, f.id)
    assert c.career.matrix().levels[0].covered == 1
    again = c.facts.add_own(
        c.documents,
        "achievement",
        "Mentored Ana through her first design review",
        "Weekly pairing in October.",
    )
    assert again.id == f.id  # same note → same fact, no duplicates
    with pytest.raises(ValidationError):
        c.facts.add_own(c.documents, "goal", "Not evidence at all")


def test_own_evidence_api_links(client: TestClient) -> None:
    e = client.post(
        "/api/career/expectations", json={"level": "L5", "text": "Leads design reviews"}
    ).json()
    s = client.post("/api/skills", json={"name": "Design reviews"}).json()
    r = client.post(
        "/api/facts/own",
        json={
            "kind": "responsibility",
            "statement": "I run the weekly design review",
            "expectation_id": e["id"],
            "skill_id": s["id"],
        },
    )
    assert r.status_code == 201 and r.json()["epistemic"] == "self_reported"
    assert client.get("/api/career").json()["levels"][0]["covered"] == 1
    assert (
        client.get("/api/skills").json()["categories"][0]["rows"][0]["evidence"][0]["fact"]["id"]
        == r.json()["id"]
    )
    client.app.state.container.documents.jobs.wait_idle()  # type: ignore[attr-defined]
    hits = client.get("/api/documents/search", params={"q": "weekly design review"}).json()
    assert hits and hits[0]["document_title"].startswith("My note:")
