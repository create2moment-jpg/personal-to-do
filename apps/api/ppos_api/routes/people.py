"""People: a page per person — time together, meetings, follow-ups, notes, 1:1 prep."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from ppos.application.people import PersonSummary
from ppos_api.deps import ContainerDep

router = APIRouter(prefix="/api/people-overview", tags=["people"])


def _summary(s: PersonSummary) -> dict[str, Any]:
    d = asdict(s)
    person = d.pop("person")
    return {
        "id": person["id"],
        "name": person["name"],
        **d,
        "last_met": s.last_met.isoformat() if s.last_met else None,
        "next_meeting": s.next_meeting.isoformat() if s.next_meeting else None,
    }


@router.get("")
def people(c: ContainerDep) -> list[dict[str, Any]]:
    return [_summary(s) for s in c.people.all()]


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(default="", max_length=120)


@router.post("", status_code=status.HTTP_201_CREATED)
def add(body: PersonIn, c: ContainerDep) -> dict[str, Any]:
    return _summary(c.people.add(body.name, body.role))


@router.get("/{person_id}")
def detail(person_id: str, c: ContainerDep) -> dict[str, Any]:
    d = c.people.detail(person_id)
    return {
        **_summary(d.summary),
        "talking_points": d.talking_points,
        "minutes_30d": d.minutes_30d,
        "avg_rating": d.avg_rating,
        "meetings": d.meetings,
        "follow_ups": d.follow_ups,
        "notes": d.notes,
    }


class PersonPatch(BaseModel):
    role: str | None = Field(default=None, max_length=120)
    talking_points: str | None = Field(default=None, max_length=20_000)


@router.patch("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def update(person_id: str, body: PersonPatch, c: ContainerDep) -> None:
    c.people.update(person_id, body.role, body.talking_points)


@router.post("/{person_id}/prep-note")
def prep(person_id: str, c: ContainerDep) -> dict[str, str]:
    n = c.people.prep_note(person_id)
    return {"id": n.id, "title": n.title}
