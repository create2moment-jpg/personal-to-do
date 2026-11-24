from fastapi.testclient import TestClient

from tests.conftest import latest_schema_version


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["schema_version"] == latest_schema_version()
    assert body["ai"]["enabled"] is False


def test_task_lifecycle(client: TestClient) -> None:
    r = client.post(
        "/api/tasks", json={"title": "API task", "estimate_minutes": 30, "tags": ["#A"]}
    )
    assert r.status_code == 201
    task = r.json()
    assert task["tags"] == ["a"]
    r = client.post(f"/api/tasks/{task['id']}/move", json={"scheduled_date": "2026-11-24"})
    assert r.json()["status"] == "planned"
    r = client.patch(f"/api/tasks/{task['id']}", json={"actual_minutes": 10, "priority": 1})
    assert r.json()["priority"] == 1
    today = client.get("/api/today").json()
    assert today["capacity"]["planned_minutes"] == 20
    assert [t["id"] for t in today["tasks"]] == [task["id"]]
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404


def test_validation_errors(client: TestClient) -> None:
    assert client.post("/api/tasks", json={"title": ""}).status_code == 422
    assert client.post("/api/tasks", json={"title": "x", "priority": 9}).status_code == 422
    t = client.post("/api/tasks", json={"title": "x"}).json()
    r = client.patch(f"/api/tasks/{t['id']}", json={"tags": ["bad tag"]})
    assert r.status_code == 422 and r.json()["error"] == "ValidationError"
    r = client.put(f"/api/tasks/{t['id']}/dependencies/{t['id']}")
    assert r.status_code == 409


def test_notes_versions_and_restore(client: TestClient) -> None:
    n = client.post("/api/notes", json={"body": "# Heading\ntext"}).json()
    assert n["title"] == "Heading"
    client.patch(f"/api/notes/{n['id']}", json={"body": "changed", "snapshot": True})
    versions = client.get(f"/api/notes/{n['id']}/versions").json()
    assert [v["version"] for v in versions] == [2, 1]
    restored = client.post(f"/api/notes/{n['id']}/versions/1/restore").json()
    assert restored["body"] == "# Heading\ntext" and restored["version"] == 3


def test_day_plan_review_capture_search(client: TestClient) -> None:
    r = client.patch("/api/days/2026-11-24", json={"objective": "Ship", "capacity_minutes": 300})
    assert r.json()["objective"] == "Ship"
    r = client.put("/api/days/2026-11-24/review", json={"learning": "FTS5", "complete": True})
    assert r.json()["review"]["completed_at"] is not None
    r = client.post("/api/capture", json={"text": "Plan sprint @today ~1h"})
    assert r.status_code == 201 and r.json()["task"]["estimate_minutes"] == 60
    hits = client.get("/api/search", params={"q": "sprint"}).json()
    assert hits and hits[0]["entity_type"] == "task"
    j = client.post("/api/days/2026-11-24/journal").json()
    assert j["kind"] == "journal"
    assert client.get("/api/today").json()["journal"]["id"] == j["id"]


def test_projects(client: TestClient) -> None:
    p = client.post("/api/projects", json={"name": "Thesis"}).json()
    assert client.post("/api/projects", json={"name": "thesis"}).status_code == 422
    r = client.patch(f"/api/projects/{p['id']}", json={"status": "archived"})
    assert r.json()["status"] == "archived"
    assert client.get("/api/projects").json() == []
    assert len(client.get("/api/projects", params={"include_archived": True}).json()) == 1


def test_unknown_api_route_is_404(client: TestClient) -> None:
    assert client.get("/api/nope").status_code == 404


def test_capture_preview_does_not_save(client: TestClient) -> None:
    client.post("/api/projects", json={"name": "ML Platform"})
    r = client.post(
        "/api/capture/preview", json={"text": "Ship it #release !1 ~2h @tomorrow +ml-platform"}
    )
    body = r.json()
    assert body["title"] == "Ship it" and body["priority"] == 1 and body["estimate_minutes"] == 120
    assert body["scheduled_date"] == "2026-11-25" and body["project_name"] == "ML Platform"
    assert client.get("/api/tasks").json() == []


def test_health_reports_demo_flag(client: TestClient) -> None:
    assert client.get("/api/health").json()["demo"] is False
