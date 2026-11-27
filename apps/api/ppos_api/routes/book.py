"""Prompt Book and local-AI status."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime

from fastapi import APIRouter, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ppos.domain.book import Book, BookNode, NodeKind, PromptVersion
from ppos_api.deps import ContainerDep

router = APIRouter(tags=["prompt-book"])


class BookOut(BaseModel):
    id: str
    title: str
    emoji: str | None
    description: str


class NodeOut(BaseModel):
    id: str
    book_id: str
    parent_id: str | None
    kind: str
    title: str
    emoji: str | None
    position: float
    updated_at: datetime
    use_count: int
    variables: list[str] = []


class PageOut(NodeOut):
    body: str
    tags: list[str]
    version: int
    last_used_at: datetime | None
    rating: int | None
    created_at: datetime


class TreeOut(BaseModel):
    book: BookOut
    nodes: list[NodeOut]


class BookIn(BaseModel):
    title: str = Field(default="", max_length=200)
    emoji: str | None = None
    description: str = ""


class BookPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    emoji: str | None = None
    description: str | None = None


class NodeIn(BaseModel):
    book_id: str
    kind: str = Field(pattern="^(chapter|section|page)$")
    title: str = Field(default="", max_length=300)
    parent_id: str | None = None
    body: str = ""
    emoji: str | None = None


class NodePatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    emoji: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


class MoveIn(BaseModel):
    parent_id: str | None = None
    position: float | None = None


class UseIn(BaseModel):
    values: dict[str, str] = {}
    body: str | None = None


class ImproveIn(BaseModel):
    style: str = "clearer"
    body: str | None = None


class VersionOut(BaseModel):
    version: int
    body: str
    source: str
    model: str | None
    prompt_template: str | None
    note: str
    created_at: datetime


def book_out(b: Book) -> BookOut:
    return BookOut(id=b.id, title=b.title, emoji=b.emoji, description=b.description)


def node_out(n: BookNode) -> NodeOut:
    return NodeOut(
        id=n.id,
        book_id=n.book_id,
        parent_id=n.parent_id,
        kind=n.kind.value,
        title=n.title,
        emoji=n.emoji,
        position=n.position,
        updated_at=n.updated_at,
        use_count=n.use_count,
        variables=n.variables,
    )


def page_out(n: BookNode) -> PageOut:
    return PageOut(
        **node_out(n).model_dump(),
        body=n.body,
        tags=n.tags,
        version=n.version,
        last_used_at=n.last_used_at,
        rating=n.rating,
        created_at=n.created_at,
    )


def version_out(v: PromptVersion) -> VersionOut:
    return VersionOut(
        version=v.version,
        body=v.body,
        source=v.source.value,
        model=v.model,
        prompt_template=v.prompt_template,
        note=v.note,
        created_at=v.created_at,
    )


@router.get("/api/books", response_model=list[BookOut])
def list_books(c: ContainerDep) -> list[BookOut]:
    return [book_out(b) for b in c.book.books()]


@router.post("/api/books", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(body: BookIn, c: ContainerDep) -> BookOut:
    return book_out(c.book.create_book(body.title, body.emoji, body.description))


@router.patch("/api/books/{book_id}", response_model=BookOut)
def update_book(book_id: str, body: BookPatch, c: ContainerDep) -> BookOut:
    return book_out(c.book.update_book(book_id, body.model_dump(exclude_unset=True)))


@router.delete("/api/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: str, c: ContainerDep) -> Response:
    c.book.delete_book(book_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/books/{book_id}/tree", response_model=TreeOut)
def tree(book_id: str, c: ContainerDep) -> TreeOut:
    b, nodes = c.book.tree(book_id)
    return TreeOut(book=book_out(b), nodes=[node_out(n) for n in nodes])


@router.post("/api/book-nodes", response_model=PageOut, status_code=status.HTTP_201_CREATED)
def create_node(body: NodeIn, c: ContainerDep) -> PageOut:
    n = c.book.create_node(
        body.book_id, NodeKind(body.kind), body.title, body.parent_id, body.body, body.emoji
    )
    return page_out(n)


@router.get("/api/book-nodes/{node_id}", response_model=PageOut)
def get_node(node_id: str, c: ContainerDep) -> PageOut:
    return page_out(c.book.node(node_id))


@router.patch("/api/book-nodes/{node_id}", response_model=PageOut)
def update_node(node_id: str, body: NodePatch, c: ContainerDep) -> PageOut:
    return page_out(c.book.update_node(node_id, body.model_dump(exclude_unset=True)))


@router.post("/api/book-nodes/{node_id}/move", response_model=PageOut)
def move_node(node_id: str, body: MoveIn, c: ContainerDep) -> PageOut:
    return page_out(c.book.move(node_id, body.parent_id, body.position))


@router.delete("/api/book-nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: str, c: ContainerDep) -> Response:
    c.book.delete_node(node_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/book-nodes/{node_id}/versions", response_model=list[VersionOut])
def versions(node_id: str, c: ContainerDep) -> list[VersionOut]:
    return [version_out(v) for v in c.book.versions(node_id)]


@router.post("/api/book-nodes/{node_id}/snapshot", response_model=VersionOut)
def snapshot(node_id: str, c: ContainerDep) -> VersionOut:
    return version_out(c.book.snapshot(node_id))


@router.post("/api/book-nodes/{node_id}/versions/{version}/restore", response_model=PageOut)
def restore(node_id: str, version: int, c: ContainerDep) -> PageOut:
    return page_out(c.book.restore(node_id, version))


@router.post("/api/book-nodes/{node_id}/use")
def use(node_id: str, body: UseIn, c: ContainerDep) -> dict[str, str]:
    return {"text": c.book.use(node_id, body.values, body.body)}


@router.post("/api/book-nodes/{node_id}/improve")
def improve(node_id: str, body: ImproveIn, c: ContainerDep) -> dict[str, object]:
    r = c.book.improve(node_id, body.style, body.body)
    return r.__dict__


@router.post("/api/book-nodes/{node_id}/improve/stream")
def improve_stream(node_id: str, body: ImproveIn, c: ContainerDep) -> StreamingResponse:
    """Newline-delimited JSON: ``delta`` events while the model writes, then ``done``."""
    events = c.book.improve_stream(node_id, body.style, body.body)  # validates before streaming

    def lines() -> Iterator[bytes]:
        for e in events:
            yield (json.dumps(e) + "\n").encode()

    return StreamingResponse(
        lines(), media_type="application/x-ndjson", headers={"Cache-Control": "no-store"}
    )


class ExplainIn(BaseModel):
    original: str = Field(min_length=1, max_length=40_000)
    improved: str = Field(min_length=1, max_length=40_000)


@router.post("/api/book/explain-changes")
def explain_changes(body: ExplainIn, c: ContainerDep) -> dict[str, object]:
    notes, model = c.book.explain(body.original, body.improved)
    return {"notes": notes, "model": model}


@router.post("/api/book-nodes/{node_id}/versions/{version}/accept", response_model=PageOut)
def accept(node_id: str, version: int, c: ContainerDep) -> PageOut:
    return page_out(c.book.accept(node_id, version))
