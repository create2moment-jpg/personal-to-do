from datetime import date, datetime, timezone

import pytest

from ppos.domain.goals import (
    Goal,
    Progress,
    check_parent,
    combine,
    own_progress,
    pace,
    period_bounds,
    period_of,
)
from ppos.shared.errors import ValidationError

NOW = datetime(2026, 11, 24, tzinfo=timezone.utc)


def g(horizon: str, period: str, **kw: object) -> Goal:
    return Goal(
        id="x", title="G", horizon=horizon, period=period, created_at=NOW, updated_at=NOW, **kw
    )  # type: ignore[arg-type]


def test_periods() -> None:
    assert period_of("quarter", date(2026, 11, 24)) == "2026-Q4"
    assert period_of("month", date(2026, 2, 3)) == "2026-02"
    assert period_bounds("quarter", "2026-Q1") == (date(2026, 1, 1), date(2026, 3, 31))
    assert period_bounds("month", "2024-02") == (date(2024, 2, 1), date(2024, 2, 29))
    assert period_bounds("month", "2026-12") == (date(2026, 12, 1), date(2026, 12, 31))
    with pytest.raises(ValidationError):
        period_bounds("quarter", "2026-Q5")


def test_hierarchy_rules() -> None:
    year, q4 = g("year", "2026"), g("quarter", "2026-Q4")
    check_parent(q4, year)
    check_parent(g("month", "2026-11"), q4)
    with pytest.raises(ValidationError):
        check_parent(year, q4)  # longer under shorter
    with pytest.raises(ValidationError):
        check_parent(g("month", "2026-01"), q4)  # outside the parent period


def test_progress_modes_and_pace() -> None:
    assert own_progress(g("quarter", "2026-Q4"), 3, 4).value == 0.75  # type: ignore[union-attr]
    assert own_progress(g("quarter", "2026-Q4"), 0, 0) is None
    manual = own_progress(g("quarter", "2026-Q4", progress_mode="manual", manual_progress=40), 0, 0)
    assert manual and manual.value == 0.4
    metric = own_progress(
        g(
            "year",
            "2026",
            progress_mode="metric",
            metric_start=0,
            metric_target=12,
            metric_current=9,
            metric_unit="talks",
        ),
        0,
        0,
    )
    assert metric and metric.value == 0.75 and metric.basis == "9 of 12 talks"
    parent = combine(
        g("year", "2026"), None, [Progress(0.5, ""), Progress(1.0, ""), Progress(None, "")]
    )
    assert parent.value == 0.75
    q4 = g("quarter", "2026-Q4")
    today = date(2026, 11, 15)  # ~50% through Q4
    assert pace(q4, Progress(0.9, ""), today) == "ahead"
    assert pace(q4, Progress(0.45, ""), today) == "on track"
    assert pace(q4, Progress(0.1, ""), today) == "behind"
    assert pace(q4, Progress(None, ""), today) == "not started"
    assert pace(g("quarter", "2027-Q1"), Progress(None, ""), today) == "upcoming"
    with pytest.raises(ValidationError):
        g("year", "2026", progress_mode="metric")  # needs a target
