from datetime import date

import pytest

from ppos.domain.repeat import describe_rule, next_after, normalize_rule
from ppos.shared.errors import ValidationError

TUE = date(2026, 11, 24)


def test_rules_round_trip_and_describe() -> None:
    assert normalize_rule("freq=weekly;byday=th,mo") == "FREQ=WEEKLY;BYDAY=MO,TH"
    assert normalize_rule("RRULE:FREQ=DAILY;INTERVAL=1") == "FREQ=DAILY"
    assert normalize_rule("") is None and normalize_rule(None) is None
    assert describe_rule("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR") == "Every weekday"
    assert describe_rule("FREQ=WEEKLY;INTERVAL=2") == "Every 2 weeks"
    for bad in (
        "FREQ=YEARLY",
        "FREQ=WEEKLY;COUNT=3",
        "FREQ=WEEKLY;BYDAY=XX",
        "nonsense",
        "FREQ=DAILY;BYDAY=MO",
    ):
        with pytest.raises(ValidationError):
            normalize_rule(bad)


def test_next_dates() -> None:
    assert next_after("FREQ=DAILY", TUE) == date(2026, 11, 25)
    assert next_after("FREQ=WEEKLY", TUE) == date(2026, 12, 1)
    assert next_after("FREQ=WEEKLY;INTERVAL=2", TUE) == date(2026, 12, 8)
    assert next_after("FREQ=WEEKLY;BYDAY=MO,TH", TUE) == date(2026, 11, 26)  # Thursday
    assert next_after("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR", date(2026, 11, 27)) == date(
        2026, 11, 30
    )  # Fri → Mon
    jan31 = date(2026, 1, 31)
    assert next_after("FREQ=MONTHLY", jan31) == date(2026, 2, 28)  # clamped, never skipped
    assert next_after("FREQ=MONTHLY;INTERVAL=3", date(2026, 11, 24)) == date(2027, 2, 24)
