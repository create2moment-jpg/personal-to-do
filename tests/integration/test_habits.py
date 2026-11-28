from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container
from ppos.shared.errors import NotFoundError, ValidationError

TODAY = date(2026, 11, 24)


def test_habits_streaks_and_archive(container: Container) -> None:
    h = container.habits
    walk = h.add("Walk 20 min", "daily", "🚶")
    for i in range(1, 4):
        h.check(walk.id, True, TODAY - timedelta(days=i))
    [s] = h.overview()
    assert s.streak == 3 and not s.done_today and s.last_7[-1] is False
    h.check(walk.id, True)
    [s] = h.overview()
    assert s.streak == 4 and s.done_today and s.last_7[-4:] == [True, True, True, True]
    h.check(walk.id, False)
    assert h.overview()[0].streak == 3
    h.archive(walk.id)
    assert h.overview() == []
    with pytest.raises(ValidationError):
        h.add("x", "hourly")
    with pytest.raises(NotFoundError):
        h.check("nope", True)


def test_habits_api(client: TestClient) -> None:
    hid = client.post("/api/habits", json={"name": "Read", "cadence": "weekdays"}).json()["id"]
    assert client.post(f"/api/habits/{hid}/check", json={"done": True}).status_code == 204
    [row] = client.get("/api/habits").json()
    assert row["name"] == "Read" and row["done_today"] is True and row["streak"] == 1
