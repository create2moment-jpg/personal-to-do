from fastapi.testclient import TestClient


def test_project_emoji_create_change_clear(client: TestClient) -> None:
    p = client.post("/api/projects", json={"name": "Retrieval", "emoji": "🔎"}).json()
    assert p["emoji"] == "🔎"
    p = client.patch(f"/api/projects/{p['id']}", json={"emoji": "🚀"}).json()
    assert p["emoji"] == "🚀"
    assert [x["emoji"] for x in client.get("/api/projects").json()] == ["🚀"]
    p = client.patch(f"/api/projects/{p['id']}", json={"emoji": ""}).json()
    assert p["emoji"] is None
    bad = client.post("/api/projects", json={"name": "Words", "emoji": "not an emoji"})
    assert bad.status_code == 422
    plain = client.post("/api/projects", json={"name": "Plain"}).json()
    assert plain["emoji"] is None


def test_weekly_objective_emoji(client: TestClient) -> None:
    r = client.patch(
        "/api/weeks/2026-11-24",
        json={"objectives": [{"text": "Ship ADR", "emoji": "📝"}, {"text": "Evals"}]},
    )
    assert r.status_code == 200, r.text
    objs = client.get("/api/weeks/2026-11-24").json()["plan"]["objectives"]
    assert objs == [
        {"text": "Ship ADR", "done": False, "emoji": "📝"},
        {"text": "Evals", "done": False, "emoji": None},
    ]
