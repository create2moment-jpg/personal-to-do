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
