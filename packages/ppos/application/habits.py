"""Habits (B-030): tick today, see the streak; nothing nags."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ppos.application.ports import UnitOfWorkFactory
from ppos.domain.habits import Habit, rate, streak
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError

HISTORY_DAYS = 400


@dataclass
class HabitStatus:
    habit: Habit
    done_today: bool
    streak: int
    rate_30d: float
    last_7: list[bool]  # oldest first, ending today


class HabitService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    def overview(self, day: date | None = None) -> list[HabitStatus]:
        today = day or self._clock.today()
        with self._uow() as uow:
            habits = uow.habits.all()
            done = uow.habits.done_days(today - timedelta(days=HISTORY_DAYS))
        out = []
        for h in habits:
            d = {x for x in done.get(h.id, set()) if x <= today}
            out.append(
                HabitStatus(
                    h,
                    today in d,
                    streak(h.cadence, d, today),
                    rate(h.cadence, d, today),
                    [(today - timedelta(days=6 - i)) in d for i in range(7)],
                )
            )
        return out

    def add(self, name: str, cadence: str = "daily", emoji: str | None = None) -> Habit:
        with self._uow() as uow:
            pos = max((h.position for h in uow.habits.all(True)), default=0.0) + 1
            h = Habit(new_id(), name, self._clock.now(), emoji, cadence, position=pos)
            uow.habits.save(h)
            uow.commit()
            return h

    def check(self, habit_id: str, done: bool, day: date | None = None) -> None:
        when = day or self._clock.today()
        with self._uow() as uow:
            if uow.habits.get(habit_id) is None:
                raise NotFoundError("habit", habit_id)
            uow.habits.set_done(habit_id, when, done)
            uow.commit()

    def archive(self, habit_id: str) -> None:
        with self._uow() as uow:
            h = uow.habits.get(habit_id)
            if h is None:
                raise NotFoundError("habit", habit_id)
            h.archived = True
            uow.habits.save(h)
            uow.commit()
