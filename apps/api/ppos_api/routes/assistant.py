"""Assistant API: hybrid search, grounded answers, day-plan proposals."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ppos_api.deps import ContainerDep

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class PlanIn(BaseModel):
    day: date | None = None


class ApplyIn(BaseModel):
    day: date
    top: list[str] = Field(max_length=3)


@router.get("/status")
def status(c: ContainerDep) -> dict[str, object]:
    s = c.assistant.status()
    return asdict(s) | {"ai": c.ai.name != "none"}


@router.post("/index")
def index(c: ContainerDep) -> dict[str, object]:
    return asdict(c.assistant.start_index())


@router.get("/search")
def search(c: ContainerDep, q: str = Query(min_length=2, max_length=500)) -> dict[str, object]:
    sources, semantic = c.assistant.search(q, 12)
    return {"sources": [asdict(s) for s in sources], "semantic": semantic}


@router.post("/ask")
def ask(body: AskIn, c: ContainerDep) -> dict[str, object]:
    return asdict(c.assistant.ask(body.question))


@router.post("/plan-day")
def plan_day(body: PlanIn, c: ContainerDep) -> dict[str, object]:
    p = c.assistant.plan_day(body.day)
    return {
        "day": p.day.isoformat(),
        "top": [
            {"id": t, "title": p.candidates[t], "why": p.plan.reasons.get(t, "")}
            for t in p.plan.top
        ],
        "note": p.plan.note,
        "dropped": p.dropped,
        "model": p.model,
        "capacity_minutes": p.capacity_minutes,
        "meeting_minutes": p.meeting_minutes,
        "current_top": [{"id": t, "title": p.candidates.get(t, "")} for t in p.current_top],
    }


@router.post("/plan-day/apply")
def apply_plan(body: ApplyIn, c: ContainerDep) -> dict[str, object]:
    return {"top": c.assistant.apply_plan(body.day, body.top)}


class RewriteIn(BaseModel):
    text: str = Field(min_length=1, max_length=12_000)
    style: str = Field(max_length=20)


@router.get("/rewrite-styles")
def rewrite_styles() -> dict[str, str]:
    from ppos.application.assistant import REWRITE_STYLES

    return REWRITE_STYLES


@router.post("/rewrite")
def rewrite(body: RewriteIn, c: ContainerDep) -> dict[str, object]:
    """Writing assistant for notes: returns a proposal; nothing is saved."""
    return asdict(c.assistant.rewrite(body.text, body.style))
