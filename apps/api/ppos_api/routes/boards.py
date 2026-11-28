"""Whiteboards (Miro-style): boards, items, batched saves."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Response, status
from pydantic import BaseModel, Field

from ppos.domain.boards import TEMPLATES, Board
from ppos_api.deps import ContainerDep

router = APIRouter(prefix="/api/boards", tags=["boards"])


class BoardOut(BaseModel):
    id: str
    title: str
    emoji: str | None
    viewport: dict[str, float]
    version: int
    created_at: datetime
    updated_at: datetime
    item_count: int = 0


def _board(b: Board, n: int = 0) -> BoardOut:
    return BoardOut(**asdict(b), item_count=n)


@router.get("", response_model=list[BoardOut])
def list_boards(c: ContainerDep) -> list[BoardOut]:
    return [_board(b, n) for b, n in c.boards.all()]


@router.get("/templates")
def templates() -> dict[str, str]:
    return {k: v[0] for k, v in TEMPLATES.items()}


class BoardIn(BaseModel):
    title: str = Field(default="", max_length=200)
    template: str = "blank"
    emoji: str | None = Field(default=None, max_length=16)


@router.post("", response_model=BoardOut, status_code=status.HTTP_201_CREATED)
def create(body: BoardIn, c: ContainerDep) -> BoardOut:
    return _board(c.boards.create(body.title, body.template, body.emoji))


@router.get("/{board_id}")
def get_board(board_id: str, c: ContainerDep) -> dict[str, Any]:
    v = c.boards.get(board_id)
    return {
        "board": _board(v.board, len(v.items)).model_dump(mode="json"),
        "items": [
            {k: val for k, val in asdict(i).items() if k not in ("board_id", "created_at")}
            | {"updated_at": i.updated_at.isoformat()}
            for i in v.items
        ],
        "refs": v.refs,
    }


class BoardPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    emoji: str | None = Field(default=None, max_length=16)
    viewport: dict[str, float] | None = None


@router.patch("/{board_id}", response_model=BoardOut)
def update(board_id: str, body: BoardPatch, c: ContainerDep) -> BoardOut:
    return _board(c.boards.update(board_id, body.model_dump(exclude_unset=True)))


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(board_id: str, c: ContainerDep) -> Response:
    c.boards.delete(board_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


class ChangesIn(BaseModel):
    upserts: list[dict[str, Any]] = Field(default_factory=list, max_length=2000)
    deletes: list[str] = Field(default_factory=list, max_length=2000)


@router.post("/{board_id}/changes")
def changes(board_id: str, body: ChangesIn, c: ContainerDep) -> dict[str, int]:
    return {"version": c.boards.apply_changes(board_id, body.upserts, body.deletes)}


@router.post("/{board_id}/items/{item_id}/to-task")
def to_task(board_id: str, item_id: str, c: ContainerDep) -> dict[str, Any]:
    card = c.boards.to_task(board_id, item_id)
    return {"id": card.id, "ref_type": card.ref_type, "ref_id": card.ref_id}
