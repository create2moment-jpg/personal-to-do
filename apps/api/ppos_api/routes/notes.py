from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, Field

from ppos.application.ports import NoteQuery
from ppos.domain.notes import EntityType, NoteKind
from ppos_api.deps import ContainerDep
from ppos_api.schemas import (
    LinkCreate,
    LinkOut,
    NoteCreate,
    NoteOut,
    NoteSummaryOut,
    NoteUpdate,
    NoteVersionOut,
)

router = APIRouter(tags=["notes"])


@router.get("/api/notes", response_model=list[NoteSummaryOut])
def list_notes(
    c: ContainerDep,
    kind: NoteKind | None = None,
    project_id: str | None = None,
    note_date: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[NoteSummaryOut]:
    notes = c.notes.find(
        NoteQuery(kind=kind, project_id=project_id, note_date=note_date, limit=limit, offset=offset)
    )
    return [NoteSummaryOut.model_validate(n) for n in notes]


@router.post("/api/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(body: NoteCreate, c: ContainerDep) -> NoteOut:
    data = body.model_dump()
    return NoteOut.model_validate(c.notes.create(data.pop("title"), data.pop("body"), **data))


@router.get("/api/notes/titles")
def note_titles(c: ContainerDep) -> list[dict[str, str]]:
    """Every note's id and title, for [[link]] autocomplete and resolving."""
    return c.notes.titles()


@router.get("/api/notes/graph")
def note_graph(c: ContainerDep, note: str | None = None, depth: int = 1) -> dict[str, Any]:
    """The [[link]] graph: all notes, or ``depth`` steps around one note."""
    return c.notes.graph(note, depth)


class FromTemplateIn(BaseModel):
    template_id: str
    title: str = Field(default="", max_length=300)


@router.post(
    "/api/notes/from-template", response_model=NoteOut, status_code=status.HTTP_201_CREATED
)
def from_template(body: FromTemplateIn, c: ContainerDep) -> NoteOut:
    return NoteOut.model_validate(c.notes.from_template(body.template_id, body.title))


@router.get("/api/notes/{note_id}/connections")
def connections(note_id: str, c: ContainerDep) -> dict[str, Any]:
    """Outgoing links, backlinks, unlinked mentions and the outline of a note."""
    return c.notes.connections(note_id)


class LinkMentionIn(BaseModel):
    source_id: str


@router.post("/api/notes/{note_id}/link-mention", response_model=NoteOut)
def link_mention(note_id: str, body: LinkMentionIn, c: ContainerDep) -> NoteOut:
    """Turn an unlinked mention of this note in another note into a [[link]]."""
    return NoteOut.model_validate(c.notes.link_mention(note_id, body.source_id))


@router.get("/api/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: str, c: ContainerDep) -> NoteOut:
    return NoteOut.model_validate(c.notes.get(note_id))


@router.patch("/api/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: str, body: NoteUpdate, c: ContainerDep) -> NoteOut:
    changes = body.model_dump(exclude_unset=True)
    snapshot = bool(changes.pop("snapshot", False))
    return NoteOut.model_validate(c.notes.update(note_id, changes, force_snapshot=snapshot))


@router.delete("/api/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: str, c: ContainerDep) -> Response:
    c.notes.delete(note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/notes/{note_id}/versions", response_model=list[NoteVersionOut])
def list_versions(note_id: str, c: ContainerDep) -> list[NoteVersionOut]:
    return [NoteVersionOut.model_validate(v) for v in c.notes.versions(note_id)]


@router.get("/api/notes/{note_id}/versions/{version}", response_model=NoteVersionOut)
def get_version(note_id: str, version: int, c: ContainerDep) -> NoteVersionOut:
    return NoteVersionOut.model_validate(c.notes.get_version(note_id, version))


@router.post("/api/notes/{note_id}/versions/{version}/restore", response_model=NoteOut)
def restore_version(note_id: str, version: int, c: ContainerDep) -> NoteOut:
    return NoteOut.model_validate(c.notes.restore(note_id, version))


@router.get("/api/links", response_model=list[LinkOut])
def list_links(entity_type: EntityType, entity_id: str, c: ContainerDep) -> list[LinkOut]:
    return [LinkOut.model_validate(l) for l in c.links.links_for(entity_type, entity_id)]  # noqa: E741


@router.post("/api/links", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
def create_link(body: LinkCreate, c: ContainerDep) -> LinkOut:
    return LinkOut.model_validate(
        c.links.link(body.source_type, body.source_id, body.target_type, body.target_id)
    )


@router.delete("/api/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_link(link_id: str, c: ContainerDep) -> Response:
    c.links.unlink(link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
