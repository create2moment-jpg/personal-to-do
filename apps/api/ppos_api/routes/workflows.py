"""Agentic workflows: propose a checklist, apply what you keep."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ppos.domain.workflows import WorkflowRun
from ppos_api.deps import ContainerDep

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


class ActionOut(BaseModel):
    id: str
    kind: str
    label: str
    detail: str
    selected: bool
    outcome: str | None
    params: dict[str, Any]


class RunOut(BaseModel):
    id: str
    workflow: str
    created_at: datetime
    title: str
    summary: str
    actions: list[ActionOut]
    notes: list[str]
    status: str
    applied_at: datetime | None


def run_out(r: WorkflowRun) -> RunOut:
    return RunOut.model_validate(asdict(r))


@router.get("")
def catalog(c: ContainerDep) -> dict[str, str]:
    return c.workflows.catalog()


@router.get("/runs", response_model=list[RunOut])
def runs(c: ContainerDep, limit: int = 20) -> list[RunOut]:
    return [run_out(r) for r in c.workflows.recent(min(max(limit, 1), 100))]


class RunIn(BaseModel):
    day: str | None = Field(default=None, max_length=10)
    level: str | None = Field(default=None, max_length=40)


@router.post("/{workflow}/run", response_model=RunOut)
def start(workflow: str, body: RunIn, c: ContainerDep) -> RunOut:
    return run_out(c.workflows.run(workflow, body.model_dump(exclude_none=True)))


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: str, c: ContainerDep) -> RunOut:
    return run_out(c.workflows.get(run_id))


class ApplyIn(BaseModel):
    action_ids: list[str] = Field(max_length=100)


@router.post("/runs/{run_id}/apply", response_model=RunOut)
def apply(run_id: str, body: ApplyIn, c: ContainerDep) -> RunOut:
    return run_out(c.workflows.apply(run_id, body.action_ids))


@router.post("/runs/{run_id}/dismiss", response_model=RunOut)
def dismiss(run_id: str, c: ContainerDep) -> RunOut:
    return run_out(c.workflows.dismiss(run_id))
