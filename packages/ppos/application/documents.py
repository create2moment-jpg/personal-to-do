"""Knowledge inbox use cases: ingest → hash/dedupe → store → extract → chunk → index."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ppos.application.ports import UnitOfWorkFactory
from ppos.domain.documents import (
    DOC_KINDS,
    MAX_DOCUMENT_BYTES,
    DocStatus,
    Document,
    ExtractedPage,
    chunk_pages,
    first_heading,
)
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

log = logging.getLogger("ppos.documents")

EXTENSIONS = {
    "application/pdf": ".pdf",
    "text/markdown": ".md",
    "text/plain": ".txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


class FileStore(Protocol):
    def save(self, sha256: str, ext: str, data: bytes) -> str: ...
    def read(self, rel: str) -> bytes: ...
    def delete(self, rel: str) -> None: ...


class JobRunner(Protocol):
    def submit(self, name: str, fn: Callable[[], None]) -> None: ...
    def wait_idle(self, timeout: float = 30) -> None: ...


@dataclass
class Extractor:
    sniff: Callable[[str, bytes], str]
    pages: Callable[[str, bytes], list[ExtractedPage]]
    title: Callable[[str, bytes], str | None]  # (mime, data) -> title from metadata
    version: str
    # Optional OCR for scanned PDFs: () -> engine version ("" = not installed), data -> pages
    ocr_version: Callable[[], str] = lambda: ""
    ocr: Callable[[bytes], list[ExtractedPage]] | None = None


@dataclass
class IngestResult:
    document: Document
    duplicate: bool


@dataclass
class DocumentHit:
    document_id: str
    document_title: str
    chunk_id: str
    page_start: int | None
    page_end: int | None
    section: str | None
    snippet: str
    score: float


class DocumentService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        store: FileStore,
        extractor: Extractor,
        jobs: JobRunner,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._store = store
        self._x = extractor
        self.jobs = jobs

    # ------------------------------------------------------------------ ingest
    def ingest(
        self, filename: str, data: bytes, kind: str = "other", title: str | None = None
    ) -> IngestResult:
        if not data:
            raise ValidationError("the file is empty")
        if len(data) > MAX_DOCUMENT_BYTES:
            raise ValidationError("files up to 50 MB are supported")
        if kind not in DOC_KINDS:
            raise ValidationError(f"kind must be one of {', '.join(DOC_KINDS)}")
        safe_name = filename.replace("\\", "/").rsplit("/", 1)[-1][:255] or "document"
        mime = self._x.sniff(safe_name, data)  # validates type by content
        sha = hashlib.sha256(data).hexdigest()
        with self._uow() as uow:
            existing = uow.documents.by_sha(sha)
        if existing is not None:
            return IngestResult(existing, duplicate=True)
        rel = self._store.save(sha, EXTENSIONS[mime], data)
        now = self._clock.now()
        guessed = (
            title
            or self._x.title(mime, data)
            or (
                first_heading(data[:20000].decode("utf-8", "replace"))
                if mime.startswith("text/")
                else None
            )
            or safe_name.rsplit(".", 1)[0]
        )
        doc = Document(
            id=new_id(),
            title=guessed,
            filename=safe_name,
            mime=mime,
            sha256=sha,
            size_bytes=len(data),
            storage_path=rel,
            kind=kind,
            created_at=now,
            updated_at=now,
        )
        with self._uow() as uow:
            uow.documents.add(doc)
            uow.audit.record(
                "document",
                doc.id,
                "ingest",
                details={"sha256": sha, "bytes": len(data), "mime": mime},
            )
            uow.commit()
        self._enqueue(doc.id)
        return IngestResult(doc, duplicate=False)

    def _enqueue(self, doc_id: str) -> None:
        self.jobs.submit(f"process-document-{doc_id}", lambda: self.process(doc_id))

    def resume_pending(self) -> int:
        """After a restart, re-queue anything that was not finished."""
        with self._uow() as uow:
            pending = uow.documents.find((DocStatus.QUEUED, DocStatus.PROCESSING))
        for d in pending:
            self._enqueue(d.id)
        return len(pending)

    def process(self, doc_id: str) -> None:
        with self._uow() as uow:
            doc = self._require(uow, doc_id)
            doc.status = DocStatus.PROCESSING
            doc.error = None
            doc.updated_at = self._clock.now()
            uow.documents.update(doc)
            uow.commit()
        try:
            data = self._store.read(doc.storage_path)
            if hashlib.sha256(data).hexdigest() != doc.sha256:
                raise ValidationError("stored file no longer matches its checksum")
            pages = self._x.pages(doc.mime, data)
            chars = sum(len(p.text.strip()) for p in pages)
            scanned = doc.mime == "application/pdf" and _too_little_text(chars, len(pages))
            version, err = self._x.version, None
            if scanned:
                engine = self._x.ocr_version() if self._x.ocr is not None else ""
                if engine and self._x.ocr is not None:
                    pages = self._x.ocr(data)
                    chars = sum(len(p.text.strip()) for p in pages)
                    scanned = _too_little_text(chars, len(pages))
                    version = f"{self._x.version}+ocr({engine})"
                    if scanned:
                        err = "No text layer, and OCR found no readable text on these pages."

                else:
                    err = (
                        "No text layer found — this looks like a scanned PDF. To read it, "
                        "turn on Local AI with a model that understands images (llama.cpp: a "
                        "vision model started with --mmproj), or install Tesseract — then "
                        "Re-index."
                    )
            chunks = chunk_pages(pages)
            status = DocStatus.NEEDS_OCR if scanned else DocStatus.READY
        except Exception as exc:  # any extraction failure is recorded on the document
            log.warning("processing %s failed: %s", doc_id, exc)
            with self._uow() as uow:
                d = self._require(uow, doc_id)
                d.status = DocStatus.FAILED
                d.error = str(exc)[:500]
                d.updated_at = self._clock.now()
                uow.documents.update(d)
                uow.commit()
            return
        now = self._clock.now()
        with self._uow() as uow:
            d = self._require(uow, doc_id)
            uow.documents.replace_chunks(doc_id, chunks, version, now)
            d.status, d.error, d.pages, d.chars = status, err, len(pages), chars
            d.extractor_version, d.processed_at, d.updated_at = version, now, now
            uow.documents.update(d)
            uow.audit.record(
                "document",
                doc_id,
                "processed",
                actor="system",
                details={"chunks": len(chunks), "pages": len(pages), "ocr": "+ocr(" in version},
            )
            uow.commit()

    # ------------------------------------------------------------------ queries / edits
    def find(self) -> list[Document]:
        with self._uow() as uow:
            return uow.documents.find()

    def get(self, doc_id: str) -> tuple[Document, list[dict[str, object]]]:
        with self._uow() as uow:
            return self._require(uow, doc_id), uow.documents.chunks(doc_id)

    def original(self, doc_id: str) -> tuple[Document, bytes]:
        with self._uow() as uow:
            doc = self._require(uow, doc_id)
        return doc, self._store.read(doc.storage_path)

    def update(self, doc_id: str, changes: Mapping[str, Any]) -> Document:
        unknown = set(changes) - {"title", "kind"}
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            d = self._require(uow, doc_id)
            for k, v in changes.items():
                setattr(d, k, v)
            d.updated_at = self._clock.now()
            Document.__post_init__(d)
            uow.documents.update(d)
            uow.commit()
            return d

    def reindex(self, doc_id: str | None = None, only_outdated: bool = False) -> int:
        """Re-run extraction/chunking (e.g. after the extractor improves)."""
        with self._uow() as uow:
            docs = [self._require(uow, doc_id)] if doc_id else uow.documents.find()
        todo = [
            d
            for d in docs
            if not only_outdated
            or (d.extractor_version or "").split("+ocr(")[0] != self._x.version
            or d.status == DocStatus.NEEDS_OCR  # OCR may have been installed since
        ]
        for d in todo:
            self._enqueue(d.id)
        return len(todo)

    def delete(self, doc_id: str) -> None:
        with self._uow() as uow:
            d = self._require(uow, doc_id)
            uow.documents.delete(doc_id)
            uow.audit.record(
                "document", doc_id, "delete", details={"title": d.title, "sha256": d.sha256}
            )
            uow.commit()
        self._store.delete(d.storage_path)

    def search(self, query: str, limit: int = 20) -> list[DocumentHit]:
        with self._uow() as uow:
            hits = [
                h for h in uow.search.search(query, limit * 3) if h.entity_type.value == "chunk"
            ][:limit]
            ctx = uow.documents.chunk_context([h.entity_id for h in hits])
        out: list[DocumentHit] = []
        for h in hits:
            c = ctx.get(h.entity_id)
            if not c:
                continue
            out.append(
                DocumentHit(
                    document_id=str(c["document_id"]),
                    document_title=str(c["title"]),
                    chunk_id=h.entity_id,
                    page_start=_opt_int(c["page_start"]),
                    page_end=_opt_int(c["page_end"]),
                    section=str(c["section"]) if c["section"] else None,
                    snippet=h.snippet,
                    score=h.score,
                )
            )
        return out

    @staticmethod
    def _require(uow: Any, doc_id: str) -> Document:
        d: Document | None = uow.documents.get(doc_id)
        if d is None:
            raise NotFoundError("document", doc_id)
        return d


def _opt_int(v: object) -> int | None:
    return int(v) if isinstance(v, int) else None


def _too_little_text(chars: int, pages: int) -> bool:
    """A PDF with under ~20 characters per page has no usable text layer."""
    return chars < 20 * max(pages, 1)
