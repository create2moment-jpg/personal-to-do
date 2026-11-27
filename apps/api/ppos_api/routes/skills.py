"""Skills matrix API: self-ratings with history, targets, evidence, growth goals."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, ConfigDict, Field

from ppos.application.skills import EvidenceHint, SkillMatrix
from ppos_api.deps import ContainerDep
from ppos_api.routes.documents import FactOut
from ppos_api.routes.goals import GoalOut

router = APIRouter(prefix="/api/skills", tags=["skills"])


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SkillOut(_Out):
    id: str
    name: str
    category: str
    description: str
    target_level: int | None
    position: float
    created_at: datetime
    updated_at: datetime


class RatingOut(_Out):
    id: str
    level: int
    note: str
    rated_at: datetime


class EvidenceOut(_Out):
    fact: FactOut
    document_title: str
    origin: str


class RowOut(_Out):
    skill: SkillOut
    level: int | None
    previous: int | None
    rated_at: str | None
    gap: int | None
    history: list[RatingOut]
    evidence: list[EvidenceOut]
    suggestion_count: int
    goal_ids: list[str]


class CategoryOut(BaseModel):
    category: str
    rows: list[RowOut]


class MatrixOut(BaseModel):
    categories: list[CategoryOut]
    levels: dict[int, tuple[str, str]]
    candidates: list[FactOut]


class HintOut(BaseModel):
    fact: FactOut
    document_title: str
    score: float
    shared: list[str]
    similarity: float | None = None


class SkillIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: str = Field(default="General", max_length=60)
    description: str = Field(default="", max_length=2000)
    target_level: int | None = Field(default=None, ge=1, le=5)
    level: int | None = Field(default=None, ge=1, le=5)
    from_fact_id: str | None = None


class SkillPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, max_length=60)
    description: str | None = Field(default=None, max_length=2000)
    target_level: int | None = Field(default=None, ge=1, le=5)
    position: float | None = None


class RatingIn(BaseModel):
    level: int = Field(ge=1, le=5)
    note: str = Field(default="", max_length=1000)


class FactRef(BaseModel):
    fact_id: str


def _matrix(m: SkillMatrix) -> MatrixOut:
    return MatrixOut(
        categories=[
            CategoryOut(
                category=cat, rows=[RowOut.model_validate(r, from_attributes=True) for r in rows]
            )
            for cat, rows in m.categories
        ],
        levels=m.levels,
        candidates=[FactOut.model_validate(f, from_attributes=True) for f in m.candidates],
    )


def _hint(h: EvidenceHint) -> HintOut:
    return HintOut(
        fact=FactOut.model_validate(h.fact, from_attributes=True),
        document_title=h.document_title,
        score=h.score,
        shared=list(h.shared),
        similarity=h.similarity,
    )


@router.get("", response_model=MatrixOut)
def matrix(c: ContainerDep) -> MatrixOut:
    return _matrix(c.skills.matrix())


@router.post("", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
def create(body: SkillIn, c: ContainerDep) -> SkillOut:
    return SkillOut.model_validate(c.skills.create(**body.model_dump()))


@router.patch("/{skill_id}", response_model=SkillOut)
def update(skill_id: str, body: SkillPatch, c: ContainerDep) -> SkillOut:
    return SkillOut.model_validate(c.skills.update(skill_id, body.model_dump(exclude_unset=True)))


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(skill_id: str, c: ContainerDep) -> Response:
    c.skills.delete(skill_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{skill_id}/ratings", response_model=RatingOut, status_code=status.HTTP_201_CREATED)
def rate(skill_id: str, body: RatingIn, c: ContainerDep) -> RatingOut:
    return RatingOut.model_validate(c.skills.rate(skill_id, body.level, body.note))


@router.get("/{skill_id}/suggestions", response_model=list[HintOut])
def suggestions(skill_id: str, c: ContainerDep) -> list[HintOut]:
    return [_hint(h) for h in c.skills.suggestions(skill_id)]


@router.post("/{skill_id}/evidence", status_code=status.HTTP_201_CREATED)
def link(skill_id: str, body: FactRef, c: ContainerDep) -> dict[str, str]:
    return {"origin": c.skills.link(skill_id, body.fact_id)}


@router.delete("/{skill_id}/evidence/{fact_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink(skill_id: str, fact_id: str, c: ContainerDep) -> Response:
    c.skills.unlink(skill_id, fact_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{skill_id}/goal", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def growth_goal(skill_id: str, c: ContainerDep) -> GoalOut:
    return GoalOut.model_validate(c.skills.growth_goal(skill_id))
