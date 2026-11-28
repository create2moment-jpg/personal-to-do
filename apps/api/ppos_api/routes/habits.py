"""Habits: tick today, see streaks."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from ppos_api.deps import ContainerDep

router = APIRouter(prefix="/api/habits", tags=["habits"])


@router.get("")
def habits(c: ContainerDep, day: date | None = None) -> list[dict[str, Any]]:
    return [
        {
            **asdict(s.habit),
            "done_today": s.done_today,
            "streak": s.streak,
            "rate_30d": s.rate_30d,
            "last_7": s.last_7,
        }
        for s in c.habits.overview(day)
    ]


class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    cadence: str = "daily"
    emoji: str | None = Field(default=None, max_length=16)


@router.post("", status_code=status.HTTP_201_CREATED)
def add(body: HabitIn, c: ContainerDep) -> dict[str, Any]:
    return asdict(c.habits.add(body.name, body.cadence, body.emoji))


class CheckIn(BaseModel):
    done: bool = True
    day: date | None = None


@router.post("/{habit_id}/check", status_code=status.HTTP_204_NO_CONTENT)
def check(habit_id: str, body: CheckIn, c: ContainerDep) -> None:
    c.habits.check(habit_id, body.done, body.day)


@router.post("/{habit_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive(habit_id: str, c: ContainerDep) -> None:
    c.habits.archive(habit_id)
