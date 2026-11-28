from datetime import date, timedelta

from ppos.domain.habits import rate, streak

TODAY = date(2026, 11, 27)  # Friday


def days(*offsets: int) -> set[date]:
    return {TODAY - timedelta(days=o) for o in offsets}


def test_daily_streak_is_kind_about_today() -> None:
    assert streak("daily", days(0, 1, 2), TODAY) == 3
    assert streak("daily", days(1, 2), TODAY) == 2  # today still open
    assert streak("daily", days(2, 3), TODAY) == 0
    assert streak("daily", set(), TODAY) == 0


def test_weekday_streak_skips_weekends() -> None:
    # Fri done, Thu, Wed, Tue, Mon done, weekend not needed, previous Fri done
    assert streak("weekdays", days(0, 1, 2, 3, 4, 7), TODAY) == 6


def test_weekly_streak_and_rates() -> None:
    assert streak("weekly", days(1, 8, 15), TODAY) == 3
    assert streak("weekly", days(8, 15), TODAY) == 2  # this week still open
    assert rate("daily", days(*range(1, 16)), TODAY) == 0.5
    assert rate("weekly", days(8, 15), TODAY, days=28) == 0.5
