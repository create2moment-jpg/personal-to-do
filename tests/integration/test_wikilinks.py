from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.domain.notes import NoteKind


def test_backlinks_rename_and_graph(container: Container) -> None:
    n = container.notes
    target = n.create(title="Hybrid retrieval", body="# Decision\nUse RRF.\n## Risks\n")
    a = n.create(title="Standup", body="Discussed [[Hybrid retrieval]] and [[Ghost idea]].")
    b = n.create(title="Retro", body="Hybrid retrieval took longer than planned.")

    conn = n.connections(target.id)
    assert [x["title"] for x in conn["backlinks"]] == ["Standup"]
    assert "Discussed" in conn["backlinks"][0]["snippets"][0]
    assert [x["title"] for x in conn["unlinked"]] == ["Retro"]
    assert conn["outline"] == [{"level": 1, "text": "Decision"}, {"level": 2, "text": "Risks"}]
    out = n.connections(a.id)["outgoing"]
    assert [(o["title"], o["note_id"]) for o in out] == [
        ("Hybrid retrieval", target.id),
        ("Ghost idea", None),
    ]

    linked = n.link_mention(target.id, b.id)
    assert linked.body.startswith("[[Hybrid retrieval]] took longer")
    assert {x["title"] for x in n.connections(target.id)["backlinks"]} == {"Standup", "Retro"}

    renamed = n.update(target.id, {"title": "Hybrid search"})
    assert renamed.links_updated == 2
    assert n.get(a.id).body == "Discussed [[Hybrid search]] and [[Ghost idea]]."
    assert n.get(b.id).body.startswith("[[Hybrid search]]")
    assert len(n.versions(a.id)) >= 2  # the rewrite is a new, undoable version

    g = n.graph()
    ids = {node["id"] for node in g["nodes"]}
    assert {target.id, a.id, b.id, "ghost:ghost idea"} <= ids
    assert {"source": a.id, "target": target.id} in g["edges"]
    local = n.graph(target.id)
    assert {node["id"] for node in local["nodes"]} == {target.id, a.id, b.id}


def test_templates(container: Container) -> None:
    n = container.notes
    tpl = n.create(
        title="1:1 template",
        body="# {{title}}\nDate: {{date}} ({{weekday}})\n- [ ] Follow-ups",
        kind=NoteKind.TEMPLATE,
        tags=["template", "one-on-one"],
    )
    note = n.from_template(tpl.id, "1:1 with Priya")
    assert note.title == "1:1 with Priya" and note.kind == NoteKind.GENERAL
    assert note.body.startswith("# 1:1 with Priya\nDate: 2026-11-24 (Tuesday)")
    assert note.tags == ["one-on-one"]


def test_wikilink_api(client: TestClient) -> None:
    t = client.post("/api/notes", json={"title": "Eval harness", "body": "x"}).json()
    s = client.post("/api/notes", json={"title": "Plan", "body": "see [[Eval harness]]"}).json()
    titles = client.get("/api/notes/titles").json()
    assert {x["title"] for x in titles} >= {"Eval harness", "Plan"}
    conn = client.get(f"/api/notes/{t['id']}/connections").json()
    assert conn["backlinks"][0]["note_id"] == s["id"]
    graph = client.get("/api/notes/graph").json()
    assert {"source": s["id"], "target": t["id"]} in graph["edges"]
    r = client.patch(f"/api/notes/{t['id']}", json={"title": "Eval suite"}).json()
    assert r["links_updated"] == 1
    assert client.get(f"/api/notes/{s['id']}").json()["body"] == "see [[Eval suite]]"
