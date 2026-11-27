"""Knowledge inbox API. Uploads are the raw request body (no multipart dependency)."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response, status
from pydantic import BaseModel, Field

from ppos.domain.documents import MAX_DOCUMENT_BYTES, Document
from ppos.shared.errors import ValidationError
from ppos_api.deps import ContainerDep

router = APIRouter(tags=["knowledge"])


class DocumentOut(BaseModel):
    id: str
    title: str
    filename: str
    mime: str
    sha256: str
    size_bytes: int
    kind: str
    status: str
    error: str | None
    pages: int | None
    chars: int | None
    extractor_version: str | None
    created_at: datetime
    processed_at: datetime | None


class ChunkOut(BaseModel):
    id: str
    seq: int
    page_start: int | None
    page_end: int | None
    section: str | None
    text: str
    char_start: int
    char_end: int
    extractor_version: str


class DocumentDetail(DocumentOut):
    chunks: list[ChunkOut]


class IngestOut(BaseModel):
    document: DocumentOut
    duplicate: bool


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    kind: str | None = None


class HitOut(BaseModel):
    document_id: str
    document_title: str
    chunk_id: str
    page_start: int | None
    page_end: int | None
    section: str | None
    snippet: str


def out(d: Document) -> DocumentOut:
    return DocumentOut(
        **{k: getattr(d, k) for k in DocumentOut.model_fields if k != "status"},
        status=d.status.value,
    )


@router.get("/api/documents", response_model=list[DocumentOut])
def list_documents(c: ContainerDep) -> list[DocumentOut]:
    return [out(d) for d in c.documents.find()]


@router.post("/api/documents", response_model=IngestOut, status_code=status.HTTP_202_ACCEPTED)
async def upload(
    request: Request,
    c: ContainerDep,
    filename: str = Query(min_length=1, max_length=255),
    kind: str = "other",
) -> IngestOut:
    declared = int(request.headers.get("content-length") or 0)
    if declared > MAX_DOCUMENT_BYTES:
        raise ValidationError("files up to 50 MB are supported")
    data = await request.body()
    r = c.documents.ingest(filename, data, kind)
    return IngestOut(document=out(r.document), duplicate=r.duplicate)


@router.get("/api/documents/search", response_model=list[HitOut])
def search(
    c: ContainerDep,
    q: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[HitOut]:
    return [
        HitOut(**{k: getattr(h, k) for k in HitOut.model_fields})
        for h in c.documents.search(q, limit)
    ]


@router.post("/api/documents/reindex")
def reindex_all(c: ContainerDep, outdated: bool = True) -> dict[str, int]:
    return {"queued": c.documents.reindex(None, only_outdated=outdated)}


@router.get("/api/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: str, c: ContainerDep) -> DocumentDetail:
    d, chunks = c.documents.get(doc_id)
    return DocumentDetail(
        **out(d).model_dump(),
        chunks=[ChunkOut.model_validate(ch) for ch in chunks],
    )


@router.get("/api/documents/{doc_id}/file")
def original(doc_id: str, c: ContainerDep) -> Response:
    d, data = c.documents.original(doc_id)
    return Response(
        content=data,
        media_type=d.mime,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(d.filename)}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.patch("/api/documents/{doc_id}", response_model=DocumentOut)
def update(doc_id: str, body: DocumentPatch, c: ContainerDep) -> DocumentOut:
    return out(c.documents.update(doc_id, body.model_dump(exclude_unset=True)))


@router.post("/api/documents/{doc_id}/reindex")
def reindex(doc_id: str, c: ContainerDep) -> dict[str, int]:
    return {"queued": c.documents.reindex(doc_id)}


@router.delete("/api/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(doc_id: str, c: ContainerDep) -> Response:
    c.documents.delete(doc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- AI fact extraction


class FactOut(BaseModel):
    id: str
    document_id: str
    chunk_id: str | None
    page: int | None
    section: str | None
    kind: str
    statement: str
    quote: str
    confidence: float
    epistemic: str
    status: str
    model: str
    prompt_template: str
    note: str


class FactRunOut(BaseModel):
    id: str
    status: str
    model: str | None
    prompt_template: str | None
    chunks_total: int
    chunks_done: int
    facts_found: int
    facts_dropped: int
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class FactsOut(BaseModel):
    run: FactRunOut | None
    facts: list[FactOut]


class FactPatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(proposed|accepted|rejected)$")
    statement: str | None = Field(default=None, max_length=400)
    note: str | None = None


def _fact(f: object) -> FactOut:
    return FactOut.model_validate(f, from_attributes=True)


@router.post(
    "/api/documents/{doc_id}/facts/extract",
    response_model=FactRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def extract_facts(doc_id: str, c: ContainerDep) -> FactRunOut:
    return FactRunOut.model_validate(c.facts.start(doc_id), from_attributes=True)


@router.get("/api/documents/{doc_id}/facts", response_model=FactsOut)
def document_facts(doc_id: str, c: ContainerDep) -> FactsOut:
    s = c.facts.summary(doc_id)
    run = FactRunOut.model_validate(s.run, from_attributes=True) if s.run else None
    return FactsOut(run=run, facts=[_fact(f) for f in s.facts])


@router.get("/api/facts", response_model=list[FactOut])
def list_facts(
    c: ContainerDep,
    kind: str | None = None,
    status_: str | None = Query(default=None, alias="status"),
) -> list[FactOut]:
    return [_fact(f) for f in c.facts.find(kind, status_)]


@router.patch("/api/facts/{fact_id}", response_model=FactOut)
def review_fact(fact_id: str, body: FactPatch, c: ContainerDep) -> FactOut:
    return _fact(c.facts.review(fact_id, body.status, body.statement, body.note))


class OwnEvidenceIn(BaseModel):
    kind: str = Field(pattern="^(achievement|responsibility|competency|strength)$")
    statement: str = Field(min_length=8, max_length=400)
    detail: str = Field(default="", max_length=4000)
    expectation_id: str | None = None  # link it right away (optional)
    skill_id: str | None = None


@router.post("/api/facts/own", response_model=FactOut, status_code=status.HTTP_201_CREATED)
def add_own_evidence(body: OwnEvidenceIn, c: ContainerDep) -> FactOut:
    """Evidence you write yourself: stored as a note in your library, then accepted."""
    f = c.facts.add_own(c.documents, body.kind, body.statement, body.detail)
    if body.expectation_id:
        c.career.link(body.expectation_id, f.id)
    if body.skill_id:
        c.skills.link(body.skill_id, f.id)
    return _fact(f)
