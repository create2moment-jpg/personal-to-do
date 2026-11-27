import pytest

from ppos.domain.timebox import Span, free_slots, parse_start, propose, to_hhmm, to_minutes
from ppos.shared.errors import ValidationError


def test_parse_and_format() -> None:
    assert parse_start("09:30") == "09:30" and parse_start("") is None and parse_start(None) is None
    for bad in ("9:30", "24:00", "12:60", "noon"):
        with pytest.raises(ValidationError):
            parse_start(bad)
    assert to_minutes("13:05") == 785 and to_hhmm(785) == "13:05" and to_hhmm(5000) == "23:59"


def test_free_slots_skip_meetings_and_tiny_gaps() -> None:
    work = Span(480, 1020)  # 08:00–17:00
    busy = [Span(540, 600), Span(590, 630), Span(640, 700), Span(1000, 1100)]
    assert free_slots(work, busy) == [Span(480, 540), Span(700, 1000)]  # 10-min gap dropped
    assert free_slots(None, busy) == []
    assert free_slots(work, []) == [work]


def test_propose_first_fit_in_order_never_splits() -> None:
    free = [Span(480, 540), Span(700, 1000)]
    placed, unplaced = propose([("a", 90), ("b", 45), ("c", 400), ("d", 15)], free)
    assert [(p.task_id, to_hhmm(p.start)) for p in placed] == [
        ("a", "11:40"),  # 90 min does not fit before 09:00
        ("b", "08:00"),
        ("d", "08:45"),  # the 15 minutes left before 09:00
    ]
    assert unplaced == ["c"]


def test_propose_respects_now_and_snaps() -> None:
    placed, _ = propose([("a", 30)], [Span(480, 1020)], not_before=8 * 60 + 7)
    assert to_hhmm(placed[0].start) == "08:10"
