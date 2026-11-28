"""Reusable checklists: list, edit, apply (parent task + one subtask per line)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from ppos_api.deps import ContainerDep
from ppos_api.schemas import TaskOut

router = APIRouter(prefix="/api/checklists", tags=["checklists"])


@router.get("")
def checklists(c: ContainerDep) -> list[dict[str, Any]]:
    return [asdict(x) for x in c.checklists.all()]


class ChecklistIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    lines: str = Field(min_length=1, max_length=20_000)


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: ChecklistIn, c: ContainerDep) -> dict[str, Any]:
    return asdict(c.checklists.save(body.name, body.lines))


@router.post("/starters")
def starters(c: ContainerDep) -> list[dict[str, Any]]:
    return [asdict(x) for x in c.checklists.add_starters()]


@router.put("/{checklist_id}")
def update(checklist_id: str, body: ChecklistIn, c: ContainerDep) -> dict[str, Any]:
    return asdict(c.checklists.save(body.name, body.lines, checklist_id))


@router.delete("/{checklist_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(checklist_id: str, c: ContainerDep) -> Response:
    c.checklists.delete(checklist_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ApplyIn(BaseModel):
    day: date | None = None
    title: str = Field(default="", max_length=200)


@router.post("/{checklist_id}/apply", response_model=TaskOut)
def apply(checklist_id: str, body: ApplyIn, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(c.checklists.apply(checklist_id, body.day, body.title))
