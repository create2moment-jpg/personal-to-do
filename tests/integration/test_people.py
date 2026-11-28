from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from ppos.bootstrap import Container

NOW = datetime(2026, 11, 24, 9, 0, tzinfo=timezone.utc)


def test_person_page_time_follow_ups_notes_and_prep(container: Container) -> None:
    c = container
    c.meetings.log_call(
        "Design review", NOW - timedelta(days=2), 45, people=["Priya Sharma"], note="Agreed on RRF."
    )
    c.meetings.log_call("Sync", NOW - timedelta(days=40), 30, people=["Priya Sharma", "Ana"])
    c.meetings.log_call("Old chat", NOW - timedelta(days=200), 20, people=["Priya Sharma"])
    c.meetings.log_call("Planning", NOW + timedelta(days=3), 30, people=["Priya Sharma"])
    c.tasks.create("Send Priya Sharma the eval numbers")
    c.tasks.create("Unrelated task")
    c.notes.create(title="Retro", body="[[Priya Sharma]] suggested timeboxing reviews.")
    c.notes.create(title="Hiring", body="Talked with priya sharma about the loop.")

    people = {s.person.name: s for s in c.people.all()}
    priya = people["Priya Sharma"]
    assert priya.meetings_90d == 2 and priya.minutes_90d == 75
    assert priya.last_met == NOW - timedelta(days=2) and priya.next_meeting == NOW + timedelta(
        days=3
    )
    assert priya.follow_ups == 1 and people["Ana"].follow_ups == 0

    c.people.update(priya.person.id, "Staff engineer", "- Promotion packet\n- Mentoring Ana")
    d = c.people.detail(priya.person.id)
    assert d.summary.role == "Staff engineer" and d.minutes_30d == 45
    assert [m["title"] for m in d.meetings] == ["Planning", "Design review", "Sync", "Old chat"]
    assert d.meetings[0]["upcoming"] is True
    assert [t["title"] for t in d.follow_ups] == ["Send Priya Sharma the eval numbers"]
    assert {n["title"] for n in d.notes} == {"Retro", "Hiring"}
    assert next(n for n in d.notes if n["title"] == "Retro")["linked"] is True

    note = c.people.prep_note(priya.person.id)
    body = c.notes.get(note.id).body
    assert "[[Priya Sharma]]" in body and "- Promotion packet" in body
    assert "- [ ] Send Priya Sharma the eval numbers" in body and "Agreed on RRF." in body


def test_people_api(client: TestClient) -> None:
    r = client.post("/api/people-overview", json={"name": "  Lee  Chen ", "role": "PM"})
    assert r.status_code == 201 and r.json()["name"] == "Lee Chen" and r.json()["role"] == "PM"
    pid = r.json()["id"]
    assert (
        client.patch(f"/api/people-overview/{pid}", json={"talking_points": "Roadmap"}).status_code
        == 204
    )
    d = client.get(f"/api/people-overview/{pid}").json()
    assert d["talking_points"] == "Roadmap" and d["meetings"] == []
    assert client.get("/api/people-overview/nope").status_code == 404
    assert (
        client.post(f"/api/people-overview/{pid}/prep-note")
        .json()["title"]
        .startswith("1:1 Lee Chen")
    )
