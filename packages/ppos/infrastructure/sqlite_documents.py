"""SQLite repository for documents and chunks."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ppos.domain.documents import Chunk, DocStatus, Document
from ppos.shared.clock import new_id


def _ts(v: datetime | None) -> str | None:
    return v.astimezone(timezone.utc).isoformat() if v else None


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


_COLS = (
    "id, title, filename, mime, sha256, size_bytes, storage_path, kind, status, error, pages, chars,"
    " extractor_version, supersedes_id, created_at, updated_at, processed_at"
)


class SqliteDocumentRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    @staticmethod
    def _from(r: sqlite3.Row) -> Document:
        created, updated = _dt(r["created_at"]), _dt(r["updated_at"])
        assert created and updated
        return Document(
            id=r["id"], title=r["title"], filename=r["filename"], mime=r["mime"], sha256=r["sha256"],
            size_bytes=r["size_bytes"], storage_path=r["storage_path"], kind=r["kind"],
            status=DocStatus(r["status"]), error=r["error"], pages=r["pages"], chars=r["chars"],
            extractor_version=r["extractor_version"], supersedes_id=r["supersedes_id"],
            created_at=created, updated_at=updated, processed_at=_dt(r["processed_at"]),
        )  # fmt: skip

    def _row(self, d: Document) -> tuple[object, ...]:
        return (
            d.id, d.title, d.filename, d.mime, d.sha256, d.size_bytes, d.storage_path, d.kind, d.status.value,
            d.error, d.pages, d.chars, d.extractor_version, d.supersedes_id, _ts(d.created_at),
            _ts(d.updated_at), _ts(d.processed_at),
        )  # fmt: skip

    def add(self, d: Document) -> None:
        self._c.execute(
            f"INSERT INTO documents ({_COLS}) VALUES ({','.join('?' * 17)})", self._row(d)
        )

    def update(self, d: Document) -> None:
        cols = [c.strip() for c in _COLS.split(",")][1:]
        self._c.execute(
            f"UPDATE documents SET {', '.join(f'{c}=?' for c in cols)} WHERE id=?",
            (*self._row(d)[1:], d.id),
        )

    def get(self, doc_id: str) -> Document | None:
        r = self._c.execute(f"SELECT {_COLS} FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return self._from(r) if r else None

    def by_sha(self, sha: str) -> Document | None:
        r = self._c.execute(f"SELECT {_COLS} FROM documents WHERE sha256 = ?", (sha,)).fetchone()
        return self._from(r) if r else None

    def find(self, statuses: tuple[DocStatus, ...] = ()) -> list[Document]:
        sql = f"SELECT {_COLS} FROM documents"
        args: list[str] = []
        if statuses:
            sql += f" WHERE status IN ({','.join('?' * len(statuses))})"
            args = [s.value for s in statuses]
        return [self._from(r) for r in self._c.execute(sql + " ORDER BY created_at DESC", args)]

    def delete(self, doc_id: str) -> None:
        self._c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    def replace_chunks(
        self, doc_id: str, chunks: list[Chunk], extractor_version: str, at: datetime
    ) -> None:
        self._c.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
        for ch in chunks:
            self._c.execute(
                "INSERT INTO document_chunks (id, document_id, seq, page_start, page_end, section, text, char_start,"
                " char_end, extractor_version, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (new_id(), doc_id, ch.seq, ch.page_start, ch.page_end, ch.section, ch.text, ch.char_start,
                 ch.char_end, extractor_version, _ts(at)),
            )  # fmt: skip

    def chunks(self, doc_id: str) -> list[dict[str, object]]:
        rows = self._c.execute(
            "SELECT * FROM document_chunks WHERE document_id = ? ORDER BY seq", (doc_id,)
        )
        return [dict(r) for r in rows]

    def chunk_context(self, chunk_ids: list[str]) -> dict[str, dict[str, object]]:
        if not chunk_ids:
            return {}
        q = (
            "SELECT c.id, c.document_id, c.page_start, c.page_end, c.section, c.text, d.title"
            " FROM document_chunks c"
            f" JOIN documents d ON d.id = c.document_id WHERE c.id IN ({','.join('?' * len(chunk_ids))})"
        )
        return {r["id"]: dict(r) for r in self._c.execute(q, chunk_ids)}
