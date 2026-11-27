"""Periodic reviews API: due list, open/refresh/edit/finalize, AI draft, Markdown export."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from ppos.domain.reviews import period_label
from ppos_api.deps import ContainerDep

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

Kind = Literal["month", "bimonth", "quarter", "year"]


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    period: str
    label: str = ""
    status: str
    highlights: str
    challenges: str
    learnings: str
    next_focus: str
    snapshot: dict[str, Any]
    ai_model: str | None
    ai_template: str | None
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None


class DueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    kind: str
    period: str
    label: str
    review_id: str | None
    status: str | None
    in_progress: bool


class OpenIn(BaseModel):
    kind: Kind
    period: str = Field(max_length=10)


class ReviewPatch(BaseModel):
    highlights: str | None = Field(default=None, max_length=20_000)
    challenges: str | None = Field(default=None, max_length=20_000)
    learnings: str | None = Field(default=None, max_length=20_000)
    next_focus: str | None = Field(default=None, max_length=20_000)
    ai_model: str | None = Field(default=None, max_length=200)
    ai_template: str | None = Field(default=None, max_length=200)


class DraftOut(BaseModel):
    sections: dict[str, list[str]]
    dropped: list[tuple[str, str]]
    model: str
    template: str


def _out(r: Any) -> ReviewOut:
    out = ReviewOut.model_validate(r)
    out.label = period_label(r.kind, r.period)
    return out


@router.get("/due", response_model=list[DueOut])
def due(c: ContainerDep) -> list[DueOut]:
    return [DueOut.model_validate(d) for d in c.reviews.due()]


@router.get("", response_model=list[ReviewOut])
def all_reviews(c: ContainerDep) -> list[ReviewOut]:
    return [_out(r) for r in c.reviews.all()]


@router.post("", response_model=ReviewOut)
def open_review(body: OpenIn, c: ContainerDep) -> ReviewOut:
    return _out(c.reviews.open(body.kind, body.period))


@router.get("/{review_id}", response_model=ReviewOut)
def get(review_id: str, c: ContainerDep) -> ReviewOut:
    return _out(c.reviews.get(review_id))


@router.patch("/{review_id}", response_model=ReviewOut)
def update(review_id: str, body: ReviewPatch, c: ContainerDep) -> ReviewOut:
    return _out(c.reviews.update(review_id, body.model_dump(exclude_unset=True)))


@router.post("/{review_id}/refresh", response_model=ReviewOut)
def refresh(review_id: str, c: ContainerDep) -> ReviewOut:
    return _out(c.reviews.refresh(review_id))


@router.post("/{review_id}/finalize", response_model=ReviewOut)
def finalize(review_id: str, c: ContainerDep, final: bool = True) -> ReviewOut:
    return _out(c.reviews.finalize(review_id, final))


@router.post("/{review_id}/draft", response_model=DraftOut)
def draft(review_id: str, c: ContainerDep) -> DraftOut:
    d = c.reviews.draft_with_ai(review_id)
    return DraftOut(sections=d.sections, dropped=d.dropped, model=d.model, template=d.template)


@router.get("/{review_id}/markdown", response_class=PlainTextResponse)
def markdown(review_id: str, c: ContainerDep) -> str:
    return c.reviews.markdown(review_id)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(review_id: str, c: ContainerDep) -> Response:
    c.reviews.delete(review_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/week/{monday}/draft", response_model=DraftOut)
def draft_week(monday: date, c: ContainerDep) -> DraftOut:
    """Grounded AI draft for Week → Review (wins, lessons, risks, next focus)."""
    d = c.reviews.draft_week(monday)
    return DraftOut(sections=d.sections, dropped=d.dropped, model=d.model, template=d.template)


@router.post("/sprint/{sprint_id}/draft", response_model=DraftOut)
def draft_sprint(sprint_id: str, c: ContainerDep) -> DraftOut:
    """Grounded AI draft for a sprint's summary and lessons."""
    d = c.reviews.draft_sprint(sprint_id)
    return DraftOut(sections=d.sections, dropped=d.dropped, model=d.model, template=d.template)
