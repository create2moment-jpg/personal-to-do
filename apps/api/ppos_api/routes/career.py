"""Career view API: expectations per level, user-confirmed evidence, gap tasks."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ppos.application.career import CareerMatrix, Suggestion
from ppos_api.deps import ContainerDep
from ppos_api.routes.documents import FactOut
from ppos_api.schemas import TaskOut

router = APIRouter(prefix="/api/career", tags=["career"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExpectationOut(_Out):
    id: str
    level: str
    text: str
    competency: str | None
    source_fact_id: str | None
    position: float
    created_at: datetime
    updated_at: datetime


class EvidenceOut(_Out):
    fact: FactOut
    document_title: str
    origin: str
    score: float | None
    note: str


class GoalRefOut(BaseModel):
    id: str
    title: str
    period: str
    progress: float | None
    status: str


class RowOut(_Out):
    expectation: ExpectationOut
    evidence: list[EvidenceOut]
    suggestion_count: int
    goals: list[GoalRefOut] = []


class LevelOut(_Out):
    level: str
    total: int
    covered: int
    rows: list[RowOut]


class MatrixOut(_Out):
    levels: list[LevelOut]
    evidence_pool: int
    disclaimer: str


class SuggestionOut(_Out):
    fact: FactOut
    document_title: str
    score: float
    shared: list[str]
    similarity: float | None = None


class ExpectationIn(BaseModel):
    level: str = Field(min_length=1, max_length=40)
    text: str = Field(min_length=1, max_length=400)
    competency: str | None = Field(default=None, max_length=80)


class ExpectationPatch(BaseModel):
    level: str | None = Field(default=None, max_length=40)
    text: str | None = Field(default=None, max_length=400)
    competency: str | None = Field(default=None, max_length=80)


class LinkIn(BaseModel):
    fact_id: str
    note: str = Field(default="", max_length=400)


def _matrix(m: CareerMatrix) -> MatrixOut:
    return MatrixOut.model_validate(m, from_attributes=True)


@router.get("", response_model=MatrixOut)
def matrix(c: ContainerDep) -> MatrixOut:
    out = _matrix(c.career.matrix())
    by_exp: dict[str, list[GoalRefOut]] = {}
    for n in c.goals.all_nodes().values():
        for e in n.expectation_ids:
            ref = GoalRefOut(id=n.goal.id, title=n.goal.title, period=n.goal.period,
                             progress=n.progress.value, status=n.goal.status)  # fmt: skip
            by_exp.setdefault(e, []).append(ref)
    for lvl in out.levels:
        for row in lvl.rows:
            row.goals = by_exp.get(row.expectation.id, [])
    return out


@router.post("/expectations", response_model=ExpectationOut, status_code=status.HTTP_201_CREATED)
def add_expectation(body: ExpectationIn, c: ContainerDep) -> ExpectationOut:
    return ExpectationOut.model_validate(
        c.career.add_expectation(body.level, body.text, body.competency)
    )


@router.patch("/expectations/{expectation_id}", response_model=ExpectationOut)
def update_expectation(
    expectation_id: str, body: ExpectationPatch, c: ContainerDep
) -> ExpectationOut:
    e = c.career.update_expectation(expectation_id, body.level, body.text, body.competency)
    return ExpectationOut.model_validate(e)


@router.delete("/expectations/{expectation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expectation(expectation_id: str, c: ContainerDep) -> Response:
    c.career.delete_expectation(expectation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/expectations/{expectation_id}/suggestions", response_model=list[SuggestionOut])
def suggestions(expectation_id: str, c: ContainerDep) -> list[SuggestionOut]:
    return [_suggestion(s) for s in c.career.suggestions(expectation_id)]


def _suggestion(s: Suggestion) -> SuggestionOut:
    return SuggestionOut(
        fact=FactOut.model_validate(s.fact, from_attributes=True),
        document_title=s.document_title,
        score=s.score,
        shared=list(s.shared),
        similarity=s.similarity,
    )


@router.post("/expectations/{expectation_id}/evidence", status_code=status.HTTP_201_CREATED)
def link(expectation_id: str, body: LinkIn, c: ContainerDep) -> dict[str, str]:
    lk = c.career.link(expectation_id, body.fact_id, body.note)
    return {"id": lk.id, "origin": lk.origin}


@router.delete(
    "/expectations/{expectation_id}/evidence/{fact_id}", status_code=status.HTTP_204_NO_CONTENT
)
def unlink(expectation_id: str, fact_id: str, c: ContainerDep) -> Response:
    c.career.unlink(expectation_id, fact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/expectations/{expectation_id}/gap-task", response_model=TaskOut, status_code=201)
def gap_task(expectation_id: str, c: ContainerDep) -> TaskOut:
    return TaskOut.model_validate(c.career.gap_task(expectation_id))
