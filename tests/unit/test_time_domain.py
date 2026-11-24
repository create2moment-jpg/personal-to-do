from datetime import date, datetime, timedelta, timezone

import pytest

from ppos.domain.capture import CaptureKind, parse_capture
from ppos.domain.meetings import Attendance, Meeting, MeetingSeries, day_time, union_minutes
from ppos.domain.planning import ScopeEvent, Sprint, WeeklyObjective, WeeklyPlan, burndown
from ppos.domain.settings import WorkspaceSettings
from ppos.domain.tasks import Task, TaskStatus
from ppos.shared.errors import ValidationError

UTC = timezone.utc
T0 = datetime(2026, 11, 1, tzinfo=UTC)
S = WorkspaceSettings()  # Europe/Berlin, 08:00-17:00, 10 % buffer
TUE = date(2026, 11, 24)


def mt(start_h: float, minutes: int, **kw: object) -> Meeting:
    # local Berlin time on TUE (UTC+1 in November)
    start = datetime(2026, 11, 24, tzinfo=S.tz) + timedelta(hours=start_h)
    return Meeting(
        id=str(kw.pop("id", start_h)),
        source="manual",
        title="m",
        start_at=start.astimezone(UTC),
        end_at=(start + timedelta(minutes=minutes)).astimezone(UTC),
        created_at=T0,
        updated_at=T0,
        **kw,
    )  # type: ignore[arg-type]


def test_settings_defaults_and_validation() -> None:
    assert S.timezone == "Europe/Berlin" and S.work_minutes == 540
    with pytest.raises(ValidationError):
        WorkspaceSettings(timezone="Mars/Olympus")
    with pytest.raises(ValidationError):
        WorkspaceSettings(work_start="17:00", work_end="08:00")
    assert S.merged({"work_start": "09:00"}).work_minutes == 480


def test_union_counts_overlap_once() -> None:
    a = datetime(2026, 1, 1, 9, tzinfo=UTC)
    assert (
        union_minutes(
            [(a, a + timedelta(hours=1)), (a + timedelta(minutes=30), a + timedelta(hours=2))]
        )
        == 120
    )
    assert union_minutes([]) == 0


def test_day_time_skips_partial_overlap_and_outside_hours() -> None:
    series = {"s": MeetingSeries("s", "Weekly", T0, default_status="skipped")}
    meetings = [
        mt(9, 60, id="a"),
        mt(9.5, 60, id="b"),  # overlaps a → union 90
        mt(13, 60, id="c", series_key="s"),  # series skipped
        mt(15, 60, id="d", status=Attendance.PARTIAL, attended_minutes=20),
        mt(18, 60, id="e"),  # after work hours: total only
        mt(11, 30, id="f", cancelled=True),
    ]
    dt = day_time(TUE, meetings, series, S)
    assert dt.meeting_minutes == 90 + 20
    assert dt.meeting_minutes_total == 90 + 20 + 60
    assert dt.available_minutes == 540 - 110
    assert dt.capacity_minutes == int((540 - 110) * 0.9)
    weekend = day_time(date(2026, 11, 28), [], {}, S)
    assert weekend.work_minutes == 0 and weekend.capacity_minutes == 0


def test_override_beats_series_default() -> None:
    series = MeetingSeries("s", "W", T0, default_status="skipped")
    m = mt(9, 30, series_key="s", status=Attendance.ATTENDED)
    assert m.effective_status(series) == Attendance.ATTENDED and m.counted_minutes(series) == 30


def test_call_capture_grammar() -> None:
    p = parse_capture("call: Priya, Marcus / ADR review ~45m #retrieval @14:30", TUE)
    assert p.kind == CaptureKind.CALL
    assert p.people == ["Priya", "Marcus"] and p.title == "ADR review"
    assert p.estimate_minutes == 45 and p.tags == ["retrieval"] and p.start_time == "14:30"
    q = parse_capture("call: Priya quick sync", TUE)
    assert q.people == ["Priya"] and q.title == "quick sync"


def test_weekly_plan_rules() -> None:
    with pytest.raises(ValidationError):
        WeeklyPlan(week_start=TUE)  # not a Monday
    with pytest.raises(ValidationError):
        WeeklyPlan(
            week_start=date(2026, 11, 23), objectives=[WeeklyObjective(str(i)) for i in range(4)]
        )


def test_burndown_tracks_completion_and_scope() -> None:
    sp = Sprint("s", "S1", date(2026, 11, 23), date(2026, 11, 27), T0, T0)

    def task(i: str, est: int, done_day: date | None = None) -> Task:
        t = Task(id=i, title=i, created_at=T0, updated_at=T0, estimate_minutes=est, sprint_id="s")
        if done_day:
            t.status = TaskStatus.DONE
            t.completed_at = datetime.combine(
                done_day, datetime.min.time(), tzinfo=UTC
            ) + timedelta(hours=10)
        return t

    tasks = [task("a", 60, date(2026, 11, 24)), task("b", 120), task("late", 30)]
    events = [
        ScopeEvent("s", "late", "add", "committed", True, datetime(2026, 11, 25, 12, tzinfo=UTC))
    ]
    pts = burndown(sp, tasks, events, today=date(2026, 11, 25))
    assert [p.remaining_minutes for p in pts[:3]] == [180, 120, 150]
    assert pts[3].remaining_minutes == -1  # future
    assert pts[0].ideal_minutes == pytest.approx(180 * 4 / 5)
