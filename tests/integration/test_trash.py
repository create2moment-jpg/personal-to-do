import pytest
from fastapi.testclient import TestClient

from ppos.application.ports import TaskQuery
from ppos.bootstrap import Container
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import FixedClock
from ppos.shared.errors import NotFoundError


def test_delete_goes_to_trash_and_restores(container: Container, clock: FixedClock) -> None:
    c = container
    parent = c.tasks.create("Plan the offsite", estimate_minutes=60)
    child = c.tasks.create("Book the room", parent_id=parent.id)
    other = c.tasks.create("Unrelated")
    ids = c.tasks.delete(parent.id)
    assert set(ids) == {parent.id, child.id}
    assert [t.id for t in c.tasks.find(TaskQuery(limit=50))] == [other.id]
    assert c.search("offsite") == []  # out of search too
    with pytest.raises(NotFoundError):
        c.tasks.get(child.id)
    assert {t.id for t in c.tasks.trash()} == {parent.id, child.id}

    c.tasks.restore(parent.id)
    assert {t.id for t in c.tasks.find(TaskQuery(limit=50))} == {parent.id, child.id, other.id}
    assert c.search("offsite")[0].entity_id == parent.id
    assert c.tasks.trash() == []

    # restoring a subtask brings its parent back
    c.tasks.delete(parent.id)
    c.tasks.restore(child.id)
    assert c.tasks.get(parent.id).deleted_at is None


def test_trashed_dependency_does_not_block_and_purge(
    container: Container, clock: FixedClock
) -> None:
    c = container
    a = c.tasks.create("A")
    b = c.tasks.create("B")
    c.tasks.add_dependency(b.id, a.id)
    c.tasks.delete(a.id)
    c.tasks.move(b.id, status=TaskStatus.DONE)  # no longer blocked by a deleted task
    clock.advance(days=31)
    assert c.tasks.purge_trash() == 1
    assert c.tasks.trash() == []
    with pytest.raises(NotFoundError):
        c.tasks.restore(a.id)


def test_trash_api(client: TestClient) -> None:
    t = client.post("/api/tasks", json={"title": "Oops"}).json()
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    trash = client.get("/api/tasks/trash").json()
    assert trash[0]["id"] == t["id"] and trash[0]["deleted_at"]
    assert client.get(f"/api/tasks/{t['id']}").status_code == 404
    assert client.post(f"/api/tasks/{t['id']}/restore").json()["title"] == "Oops"
    assert client.get(f"/api/tasks/{t['id']}").status_code == 200
