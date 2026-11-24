"""Injectable clock and id generation so domain logic stays deterministic in tests."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timezone, tzinfo
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today(self) -> date:
        # "Today" is the user's local calendar day.
        return datetime.now().astimezone().date()


class FixedClock:
    """Test clock; advance() moves time forward."""

    def __init__(self, at: datetime) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at

    def today(self) -> date:
        return self._at.date()

    def advance(self, **kwargs: float) -> None:
        from datetime import timedelta

        self._at = self._at + timedelta(**kwargs)


class ZonedClock:
    """System clock whose "today" follows the workspace time zone setting."""

    def __init__(self, tz_provider: Callable[[], tzinfo]) -> None:
        self._tz = tz_provider

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def today(self) -> date:
        return datetime.now(self._tz()).date()


def new_id() -> str:
    return uuid.uuid4().hex
