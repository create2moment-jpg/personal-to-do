import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.shared.errors import NotFoundError, ValidationError


def test_templates_items_changes_and_arrows(container: Container) -> None:
    b = container.boards
    retro = b.create(template="retro")
    view = b.get(retro.id)
    assert retro.title == "Retrospective" and [i.text for i in view.items][:3] == [
        "Went well",
        "To improve",
        "Actions",
    ]
    v = b.apply_changes(
        retro.id,
        [
            {
                "id": "s1",
                "kind": "sticky",
                "x": 10,
                "y": 20,
                "w": 160,
                "h": 120,
                "text": "Ship it",
                "color": "yellow",
            },
            {"id": "s2", "kind": "sticky", "x": 300, "y": 20, "w": 160, "h": 120, "text": "Docs"},
            {
                "id": "a1",
                "kind": "connector",
                "from_id": "s1",
                "to_id": "s2",
                "style": {"end": "arrow"},
            },
        ],
        [],
    )
    assert v == 2
    assert {i.id for i in b.get(retro.id).items} >= {"s1", "s2", "a1"}
    b.apply_changes(retro.id, [{"id": "s1", "x": 99}], [])  # partial update keeps the rest
    s1 = next(i for i in b.get(retro.id).items if i.id == "s1")
    assert s1.x == 99 and s1.text == "Ship it" and s1.color == "yellow"
    b.apply_changes(retro.id, [], ["s2"])  # its arrow goes with it
    assert {i.id for i in b.get(retro.id).items} & {"s2", "a1"} == set()

    with pytest.raises(ValidationError):
        b.apply_changes(
            retro.id, [{"id": "a2", "kind": "connector", "from_id": "s1", "to_id": "nope"}], []
        )
    with pytest.raises(ValidationError):
        b.apply_changes(retro.id, [{"id": "bad id!", "kind": "sticky"}], [])
    with pytest.raises(ValidationError):
        b.apply_changes(retro.id, [{"id": "x", "kind": "sticky", "x": float("inf")}], [])
    with pytest.raises(NotFoundError):
        b.apply_changes(
            retro.id, [{"id": "c", "kind": "card", "ref_type": "task", "ref_id": "missing"}], []
        )
    assert {i.id for i in b.get(retro.id).items} >= {"s1"}  # failed batches change nothing


def test_sticky_becomes_a_task_card_with_live_data(container: Container) -> None:
    b = container.boards
    board = b.create("Planning")
    b.apply_changes(
        board.id,
        [
            {
                "id": "s1",
                "kind": "sticky",
                "x": 5,
                "y": 5,
                "w": 160,
                "h": 100,
                "text": "Write the ADR",
            }
        ],
        [],
    )
    card = b.to_task(board.id, "s1")
    assert card.kind == "card" and card.ref_type == "task" and card.x == 5
    task = container.tasks.get(card.ref_id or "")
    assert task.title == "Write the ADR" and "board" in task.tags
    view = b.get(board.id)
    assert view.refs[f"task:{task.id}"]["title"] == "Write the ADR"
    note = container.notes.create(title="Context", body="Why we chose RRF")
    b.apply_changes(
        board.id,
        [
            {
                "id": "n1",
                "kind": "card",
                "ref_type": "note",
                "ref_id": note.id,
                "x": 300,
                "y": 0,
                "w": 220,
                "h": 90,
            }
        ],
        [],
    )
    assert b.get(board.id).refs[f"note:{note.id}"]["title"] == "Context"


def test_boards_api(client: TestClient) -> None:
    assert "retro" in client.get("/api/boards/templates").json()
    r = client.post("/api/boards", json={"title": "Brainstorm", "template": "blank"})
    assert r.status_code == 201
    bid = r.json()["id"]
    ch = client.post(
        f"/api/boards/{bid}/changes",
        json={
            "upserts": [
                {"id": "t1", "kind": "text", "text": "Hello", "x": 1, "y": 2, "w": 100, "h": 30}
            ]
        },
    )
    assert ch.json() == {"version": 2}
    got = client.get(f"/api/boards/{bid}").json()
    assert got["items"][0]["text"] == "Hello" and got["board"]["item_count"] == 1
    assert client.patch(
        f"/api/boards/{bid}", json={"viewport": {"x": 10, "y": -5, "zoom": 1.5}}
    ).json()["viewport"] == {"x": 10.0, "y": -5.0, "zoom": 1.5}
    assert client.get("/api/boards").json()[0]["item_count"] == 1
    assert (
        client.post(
            f"/api/boards/{bid}/changes", json={"upserts": [{"id": "z", "kind": "laser"}]}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/boards/{bid}").status_code == 204
    assert client.get(f"/api/boards/{bid}").status_code == 404
