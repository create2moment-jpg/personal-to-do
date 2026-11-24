import pytest

from ppos.bootstrap import Container
from ppos.demo import DEMO_MARKER, seed_demo
from ppos.shared.errors import ValidationError


def test_demo_seed_builds_a_believable_workspace(container: Container) -> None:
    counts = seed_demo(container)
    assert counts["projects"] == 4 and counts["tasks"] > 15 and counts["notes"] >= 6
    view = container.days.today_view()
    assert view.plan.objective and len(view.plan.top_priority_ids) == 3
    assert view.overdue and view.completed
    assert (container.settings.local_data_dir / DEMO_MARKER).exists()
    with pytest.raises(ValidationError):
        seed_demo(container)  # never mixes into a non-empty workspace
