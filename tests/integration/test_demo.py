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


def test_demo_career_view_is_populated_and_grounded(container: Container) -> None:
    seed_demo(container)
    m = container.career.matrix()
    assert [g.level for g in m.levels] == ["L4", "L5", "L6"]
    assert sum(g.covered for g in m.levels) == 2 and sum(g.total for g in m.levels) == 6
    assert m.evidence_pool == 4  # development areas are not evidence
    lead = next(r for r in m.levels[1].rows if r.expectation.text.startswith("Leads projects"))
    assert lead.suggestion_count >= 1  # waiting for the user to confirm


def test_demo_goals(container: Container) -> None:
    seed_demo(container)
    tree = container.goals.tree()
    titles = [n.goal.title for n in tree.roots]
    assert (
        "Grow into a senior engineer" in titles and "Share what we learn outside the team" in titles
    )
    senior = next(n for n in tree.roots if n.goal.title == "Grow into a senior engineer")
    launch = next(n for n in senior.children if n.goal.horizon == "quarter" and n.project_ids)
    assert launch.expectation_ids and launch.children[0].progress.total >= 2
    assert senior.progress.value is not None


def test_demo_skills(container: Container) -> None:
    seed_demo(container)
    m = container.skills.matrix()
    rows = {r.skill.name: r for _, rs in m.categories for r in rs}
    assert rows["System design"].level == 3 and rows["System design"].previous == 2
    assert rows["System design"].evidence and rows["Technical writing"].level is None
    assert rows["Mentoring"].goal_ids  # linked to the mentoring goal
