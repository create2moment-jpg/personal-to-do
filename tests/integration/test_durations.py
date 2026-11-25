from ppos.bootstrap import Container
from ppos.domain.tasks import TaskStatus
from ppos.shared.clock import FixedClock


def test_default_task_time_is_a_setting(container: Container, clock: FixedClock) -> None:
    c = container
    today = clock.today()
    c.tasks.create("No estimate", status=TaskStatus.PLANNED, scheduled_date=today)
    c.tasks.create("Odd estimate", scheduled_date=today, estimate_minutes=7)
    assert c.days.today_view().capacity.planned_minutes == 30 + 7
    c.settings_service.update({"default_task_minutes": 50})
    view = c.days.today_view()
    assert view.capacity.planned_minutes == 50 + 7 and view.capacity.unestimated_count == 1
    c.settings_service.update({"default_task_minutes": 0})
    assert c.days.today_view().capacity.planned_minutes == 7
