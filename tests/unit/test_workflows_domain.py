from datetime import date, datetime, timezone

import pytest

from ppos.domain.workflows import Action, Candidate, WorkflowRun, fit_week
from ppos.shared.errors import ValidationError

TUE, WED, THU = date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 26)


def test_fit_week_earliest_day_with_room_never_after_due() -> None:
    free = {TUE: 60, WED: 240, THU: 240}
    placed, unplaced = fit_week(
        [
            Candidate("a", 60, None),
            Candidate("b", 120, WED),  # Tue is full now → Wed
            Candidate("c", 200, WED),  # Wed has 120 left → nowhere before its due date
            Candidate("d", 30, None),
        ],
        free,
    )
    assert placed == [("a", TUE), ("b", WED), ("d", WED)]
    assert unplaced == ["c"]


def test_only_allow_listed_actions_and_known_workflows() -> None:
    with pytest.raises(ValidationError):
        Action("a1", "delete_everything", "x", {})
    with pytest.raises(ValidationError):
        WorkflowRun("r", "hack", datetime.now(timezone.utc), "t", "")
