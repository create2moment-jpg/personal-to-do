from datetime import date

import pytest

from ppos.domain.reviews import (
    check_draft,
    parse_draft,
    period_containing,
    period_label,
    previous_period,
    review_bounds,
)
from ppos.shared.errors import ValidationError


def test_periods() -> None:
    d = date(2026, 11, 24)
    assert period_containing("bimonth", d) == "2026-B6"
    assert review_bounds("bimonth", "2026-B6") == (date(2026, 11, 1), date(2026, 12, 31))
    assert review_bounds("bimonth", "2026-B1") == (date(2026, 1, 1), date(2026, 2, 28))
    assert previous_period("month", d) == "2026-10"
    assert previous_period("bimonth", d) == "2026-B5"
    assert previous_period("quarter", d) == "2026-Q3"
    assert previous_period("year", d) == "2025"
    assert previous_period("month", date(2026, 1, 5)) == "2025-12"
    assert period_label("bimonth", "2026-B6") == "Nov–Dec 2026"
    assert period_label("month", "2026-11") == "November 2026"
    with pytest.raises(ValidationError):
        review_bounds("bimonth", "2026-B7")


def test_grounding_rules() -> None:
    items = {"S1": "12 tasks completed, 9h estimated", "W1": "2026-11-03: shipped the benchmark"}
    raw = parse_draft(
        "<think>hmm</think>```json\n"
        '{"highlights": ["I completed 12 tasks [S1]", "I shipped the benchmark [W1]",'
        ' "I completed 40 tasks [S1]", "I was promoted", "Great month [X9]"],'
        ' "learnings": ["Estimates were close [S1]"]}\n```'
    )
    checked = check_draft(raw, items)
    assert checked.sections["highlights"] == [
        "I completed 12 tasks [S1]",
        "I shipped the benchmark [W1]",
    ]
    assert checked.sections["learnings"] == ["Estimates were close [S1]"]
    reasons = [r for _, r in checked.dropped]
    assert any("number 40" in r for r in reasons)
    assert any("cites nothing" in r for r in reasons)
    assert any("unknown item X9" in r for r in reasons)
    assert parse_draft("not json") == {}
