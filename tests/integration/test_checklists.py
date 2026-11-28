from datetime import date

import pytest
from fastapi.testclient import TestClient

from ppos.application.ports import TaskQuery
from ppos.bootstrap import Container
from ppos.domain.tasks import Priority, TaskStatus
from ppos.shared.errors import NotFoundError, ValidationError


def test_apply_creates_parent_with_subtasks(container: Container) -> None:
    c = container.checklists
    cl = c.save("Release", "- [ ] Tag the release ~15m !1 #release\n* Announce ~10m\n\n  ")
    assert cl.lines == ["Tag the release ~15m !1 #release", "Announce ~10m"]
    parent = c.apply(cl.id, date(2026, 11, 26))
    assert parent.title == "Release — 2026-11-26" and parent.status == TaskStatus.PLANNED
    subs = container.tasks.find(TaskQuery(parent_id=parent.id))
    by = {t.title: t for t in subs}
    assert set(by) == {"Tag the release", "Announce"}
    assert (
        by["Tag the release"].estimate_minutes == 15
        and by["Tag the release"].priority == Priority.P1
    )
    assert by["Tag the release"].tags == ["release"] and by["Announce"].scheduled_date == date(
        2026, 11, 26
    )
    assert c.get(cl.id).uses == 1
    loose = c.apply(cl.id)  # no day: backlog
    assert loose.status == TaskStatus.BACKLOG and loose.scheduled_date is None
    with pytest.raises(ValidationError):
        c.save("Empty", "  \n ")
    with pytest.raises(NotFoundError):
        c.apply("missing")


def test_starters_are_added_once(container: Container) -> None:
    first = container.checklists.add_starters()
    again = container.checklists.add_starters()
    assert len(first) == len(again) == 4
    assert "Release checklist" in {c.name for c in again}


def test_checklists_api(client: TestClient) -> None:
    r = client.post("/api/checklists", json={"name": "Trip", "lines": "Book flights\nPack ~30m"})
    assert r.status_code == 201
    cid = r.json()["id"]
    t = client.post(f"/api/checklists/{cid}/apply", json={"title": "Berlin trip"}).json()
    assert t["title"] == "Berlin trip"
    assert len(client.get("/api/tasks", params={"parent_id": t["id"]}).json()) == 2
    assert client.put(f"/api/checklists/{cid}", json={"name": "Trip v2", "lines": "Book"}).json()[
        "lines"
    ] == ["Book"]
    assert client.delete(f"/api/checklists/{cid}").status_code == 204
