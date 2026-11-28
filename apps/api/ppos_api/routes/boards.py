"""Whiteboards (Miro-style): boards, items, batched saves."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

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


@router.get("/files/{name}")
def board_image(name: str, c: ContainerDep) -> Response:
    """An image placed on a board (content-addressed, served as an image only)."""
    data, mime = c.boards.image(name)
    return Response(
        content=data,
        media_type=mime,
        headers={
            "Cache-Control": "private, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


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


@router.post("/{board_id}/images")
async def upload_image(board_id: str, request: Request, c: ContainerDep) -> dict[str, str]:
    """Store an image (PNG, JPEG, GIF, WebP; type checked from the bytes) for this board."""
    data = await request.body()
    name = await run_in_threadpool(c.boards.save_image, board_id, data)
    return {"name": name, "url": f"/api/boards/files/{name}"}
