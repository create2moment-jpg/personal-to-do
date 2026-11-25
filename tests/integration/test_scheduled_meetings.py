from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container, build_container
from ppos.domain.meetings import Meeting, MeetingSeries, Recurrence
from ppos.infrastructure.config import Settings
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError

TUE = date(2026, 11, 24)  # the test clock's day (09:00 UTC = 10:00 Berlin)


def test_recurrence_rules() -> None:
    weekly = Recurrence("weekly", weekdays=(1, 3))
    assert weekly.describe() == "Weekly on Tue, Thu"
    assert weekly.days(TUE, TUE + timedelta(days=9)) == [
        TUE, TUE + timedelta(days=2), TUE + timedelta(days=7), TUE + timedelta(days=9)
    ]  # fmt: skip
    assert Recurrence("weekly", weekdays=(0, 1, 2, 3, 4)).describe() == "Every weekday"
    assert Recurrence("weekly", 2).describe() == "Every 2 weeks"
    assert len(Recurrence("daily", count=3).days(TUE, TUE + timedelta(days=30))) == 3
    assert Recurrence("monthly", until=date(2027, 2, 1)).days(TUE, date(2028, 1, 1))[-1] == date(
        2027, 1, 24
    )
    with pytest.raises(ValidationError):
        Recurrence("daily", weekdays=(1,))
    with pytest.raises(ValidationError):
        Recurrence("weekly", until=TUE, count=2)


def test_one_off_meeting_with_custom_duration(container: Container) -> None:
    m = container.meetings.schedule(
        "Architecture review", TUE + timedelta(days=1), "14:15", 50, people=["Priya"], topic="ADR"
    )
    assert isinstance(m, Meeting) and m.duration_minutes == 50 and m.source == "manual"
    assert m.start_at.hour == 13 and m.start_at.minute == 15  # 14:15 Berlin = 13:15 UTC
    day = container.meetings.day_time(TUE + timedelta(days=1))
    assert day.meeting_minutes == 50


def test_recurring_series_lifecycle(container: Container, clock: FixedClock) -> None:
    c = container
    s = c.meetings.schedule(
        "Team stand-up", TUE, "09:30", 15, people=["Ana", "Ben"], topic="Team",
        recurrence=Recurrence("weekly", weekdays=(0, 1, 2, 3, 4)),
    )  # fmt: skip
    assert isinstance(s, MeetingSeries) and s.cadence == "Every weekday" and s.source == "app"
    week, _ = c.meetings.between(TUE, TUE + timedelta(days=6))
    standups = [m for m in week if m.series_key == s.series_key]
    assert len(standups) == 5  # Tue–Fri and next Monday
    assert all(m.duration_minutes == 15 and len(m.people_ids) == 2 for m in standups)
    overview = {o.series.series_key: o for o in c.meetings.series_overview()}
    assert overview[s.series_key].series.plan and overview[s.series_key].topic_name == "Team"

    # skip one future occurrence, then change the series: the skip survives
    thu = next(m for m in standups if m.start_at.date() == TUE + timedelta(days=2))
    c.meetings.update(thu.id, {"status": "skipped", "note": "offsite"})
    c.meetings.edit_series(s.series_key, {"minutes": 20, "start_time": "09:45"})
    week, _ = c.meetings.between(TUE, TUE + timedelta(days=6))
    standups = [m for m in week if m.series_key == s.series_key]
    future = [m for m in standups if m.start_at.date() > TUE]
    assert all(m.duration_minutes == 20 for m in future)
    thu2 = next(m for m in standups if m.start_at.date() == TUE + timedelta(days=2))
    assert thu2.status is not None and thu2.status.value == "skipped" and thu2.note == "offsite"

    # deleting one occurrence cancels it and regeneration keeps it away
    fri = next(m for m in standups if m.start_at.date() == TUE + timedelta(days=3))
    c.meetings.delete(fri.id)
    c.meetings.edit_series(s.series_key, {"title": "Daily stand-up"})
    with c.uow() as uow:
        fri2 = next(
            m
            for m in uow.meetings.occurrences(s.series_key)
            if m.start_at.date() == fri.start_at.date()
        )
    assert fri2.cancelled and fri2.title == "Daily stand-up"
    assert fri.start_at.date() not in {
        m.start_at.date() for m in c.meetings.between(TUE, TUE + timedelta(days=6))[0]
        if m.series_key == s.series_key
    }  # fmt: skip

    # end the series a week later: history kept, future removed
    clock.advance(days=7)
    removed = c.meetings.end_series(s.series_key)
    assert removed > 0
    left = c.meetings.between(TUE, TUE + timedelta(days=60))[0]
    keyed = [m for m in left if m.series_key == s.series_key]
    assert keyed and all(m.start_at < clock.now() for m in keyed)
    assert "until" in (c.meetings.series_overview()[0].series.cadence or "")


def test_open_ended_series_is_topped_up_on_start(settings: Settings, clock: FixedClock) -> None:
    c = build_container(settings, clock)
    s = c.meetings.schedule("1:1", TUE, "15:00", 30, recurrence=Recurrence("weekly", 2))
    assert isinstance(s, MeetingSeries)
    clock.advance(days=60)
    c2 = build_container(settings, clock)  # app restart two months later
    far = clock.today() + timedelta(days=100)
    ms = [m for m in c2.meetings.between(far, far + timedelta(days=14))[0] if m.series_key]
    assert len(ms) == 1


def test_imported_series_cannot_be_edited(container: Container) -> None:
    with container.uow() as uow:
        uow.meetings.upsert_series("ics:abc", "Imported", "Weekly")
        uow.commit()
    with pytest.raises(ValidationError, match="read-only"):
        container.meetings.edit_series("ics:abc", {"minutes": 10})


def test_schedule_api(client: TestClient) -> None:
    r = client.post(
        "/api/meetings/schedule",
        json={"title": "Design sync", "day": "2026-11-26", "start_time": "11:10", "minutes": 25},
    )
    assert r.status_code == 201 and r.json()["meeting"]["title"] == "Design sync"
    r = client.post(
        "/api/meetings/schedule",
        json={
            "title": "Planning",
            "day": "2026-11-30",
            "start_time": "10:00",
            "minutes": 90,
            "recurrence": {"freq": "weekly", "interval": 2, "weekdays": [0], "count": 4},
        },
    )
    key = r.json()["series_key"]
    assert r.status_code == 201 and r.json()["cadence"] == "Every 2 weeks on Mon, 4 times"
    series = {s["series_key"]: s for s in client.get("/api/meeting-series").json()}
    assert series[key]["source"] == "app" and series[key]["plan"]["minutes"] == 90
    r = client.patch(f"/api/meeting-series/{key}/plan", json={"minutes": 60})
    assert r.status_code == 200
    ms = client.get("/api/meetings", params={"start": "2026-11-30", "end": "2027-02-01"}).json()
    planning = [m for m in ms if m["series_key"] == key]
    assert len(planning) == 4 and {m["duration_minutes"] for m in planning} == {60}
    assert client.delete(f"/api/meeting-series/{key}").json()["removed"] == 4
    bad = client.post(
        "/api/meetings/schedule",
        json={"title": "x", "day": "2026-11-26", "start_time": "25:00", "minutes": 5},
    )
    assert bad.status_code == 422
