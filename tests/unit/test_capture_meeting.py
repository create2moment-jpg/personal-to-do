from datetime import date

from ppos.domain.capture import CaptureKind, parse_capture

TUE = date(2026, 11, 24)


def p(text: str):  # type: ignore[no-untyped-def]
    return parse_capture(text, TUE)


def test_one_off_meeting_tokens() -> None:
    r = p("meeting: Architecture review @thu @14:15 ~50m with Priya, Marcus #adr")
    assert r.kind == CaptureKind.MEETING and r.title == "Architecture review"
    assert r.scheduled_date == date(2026, 11, 26) and r.start_time == "14:15"
    assert r.estimate_minutes == 50 and r.people == ["Priya", "Marcus"] and r.tags == ["adr"]
    assert r.recurrence is None


def test_recurring_phrases() -> None:
    assert p("mtg: Stand-up @09:30 ~15m weekdays").recurrence.describe() == "Every weekday"  # type: ignore[union-attr]
    r = p("meeting: Planning @mon @10:00 ~1h30 every 2 weeks with Ana and Ben")
    assert r.title == "Planning" and r.estimate_minutes == 90 and r.people == ["Ana", "Ben"]
    assert r.recurrence is not None and r.recurrence.describe() == "Every 2 weeks"
    r = p("meeting: 1:1 Priya every tue, thu ~30m until 2027-01-31")
    assert r.title == "1:1 Priya"
    assert (
        r.recurrence is not None
        and r.recurrence.describe() == "Weekly on Tue, Thu until 2027-01-31"
    )
    r = p("meeting: Retro weekly on fri 6 times")
    assert r.recurrence is not None and r.recurrence.describe() == "Weekly on Fri, 6 times"
    r = p("meeting: Ops review monthly @2026-12-03")
    assert r.recurrence is not None and r.recurrence.freq == "monthly"
    assert r.scheduled_date == date(2026, 12, 3)


def test_on_day_without_repeat_is_a_one_off_and_slash_people() -> None:
    r = p("meeting: Ana, Ben / Budget check on fri")
    assert r.recurrence is None and r.scheduled_date == date(2026, 11, 27)
    assert r.people == ["Ana", "Ben"] and r.title == "Budget check"
