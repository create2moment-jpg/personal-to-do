"""SQLite repository for the Prompt Book."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ppos.domain.book import Book, BookNode, NodeKind, PromptVersion, VersionSource


def _ts(v: datetime | None) -> str | None:
    return v.astimezone(timezone.utc).isoformat() if v else None


def _dt(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v) if v else None


def _req(v: str | None) -> datetime:
    d = _dt(v)
    assert d is not None
    return d


class SqliteBookRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._c = conn

    # books
    @staticmethod
    def _book(r: sqlite3.Row) -> Book:
        return Book(
            r["id"],
            r["title"],
            _req(r["created_at"]),
            _req(r["updated_at"]),
            r["emoji"],
            r["description"],
            r["position"],
        )

    def add_book(self, b: Book) -> None:
        self._c.execute(
            "INSERT INTO books (id, title, emoji, description, position, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (
                b.id,
                b.title,
                b.emoji,
                b.description,
                b.position,
                _ts(b.created_at),
                _ts(b.updated_at),
            ),
        )

    def update_book(self, b: Book) -> None:
        self._c.execute(
            "UPDATE books SET title=?, emoji=?, description=?, position=?, updated_at=? WHERE id=?",
            (b.title, b.emoji, b.description, b.position, _ts(b.updated_at), b.id),
        )

    def get_book(self, book_id: str) -> Book | None:
        r = self._c.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        return self._book(r) if r else None

    def books(self) -> list[Book]:
        return [
            self._book(r)
            for r in self._c.execute("SELECT * FROM books ORDER BY position, created_at")
        ]

    def delete_book(self, book_id: str) -> None:
        self._c.execute("DELETE FROM books WHERE id = ?", (book_id,))

    # nodes
    @staticmethod
    def _node(r: sqlite3.Row) -> BookNode:
        return BookNode(
            id=r["id"],
            book_id=r["book_id"],
            kind=NodeKind(r["kind"]),
            title=r["title"],
            created_at=_req(r["created_at"]),
            updated_at=_req(r["updated_at"]),
            parent_id=r["parent_id"],
            emoji=r["emoji"],
            body=r["body"],
            tags=json.loads(r["tags"]),
            position=r["position"],
            version=r["version"],
            use_count=r["use_count"],
            last_used_at=_dt(r["last_used_at"]),
            rating=r["rating"],
        )

    def add_node(self, n: BookNode) -> None:
        self._c.execute(
            "INSERT INTO book_nodes (id, book_id, parent_id, kind, title, emoji, body, tags, position, version,"
            " use_count, last_used_at, rating, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                n.id,
                n.book_id,
                n.parent_id,
                n.kind.value,
                n.title,
                n.emoji,
                n.body,
                json.dumps(n.tags),
                n.position,
                n.version,
                n.use_count,
                _ts(n.last_used_at),
                n.rating,
                _ts(n.created_at),
                _ts(n.updated_at),
            ),
        )

    def update_node(self, n: BookNode) -> None:
        self._c.execute(
            "UPDATE book_nodes SET parent_id=?, title=?, emoji=?, body=?, tags=?, position=?, version=?, use_count=?,"
            " last_used_at=?, rating=?, updated_at=? WHERE id=?",
            (
                n.parent_id,
                n.title,
                n.emoji,
                n.body,
                json.dumps(n.tags),
                n.position,
                n.version,
                n.use_count,
                _ts(n.last_used_at),
                n.rating,
                _ts(n.updated_at),
                n.id,
            ),
        )

    def get_node(self, node_id: str) -> BookNode | None:
        r = self._c.execute("SELECT * FROM book_nodes WHERE id = ?", (node_id,)).fetchone()
        return self._node(r) if r else None

    def nodes(self, book_id: str) -> list[BookNode]:
        rows = self._c.execute(
            "SELECT * FROM book_nodes WHERE book_id = ? ORDER BY position, created_at", (book_id,)
        )
        return [self._node(r) for r in rows]

    def delete_node(self, node_id: str) -> None:
        self._c.execute("DELETE FROM book_nodes WHERE id = ?", (node_id,))

    def max_position(self, book_id: str, parent_id: str | None) -> float:
        r = self._c.execute(
            "SELECT max(position) FROM book_nodes WHERE book_id = ? AND parent_id IS ?",
            (book_id, parent_id),
        ).fetchone()
        return float(r[0] or 0)

    # versions
    def add_version(self, v: PromptVersion) -> None:
        self._c.execute(
            "INSERT OR REPLACE INTO prompt_versions (node_id, version, body, source, model, prompt_template, note,"
            " created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                v.node_id,
                v.version,
                v.body,
                v.source.value,
                v.model,
                v.prompt_template,
                v.note,
                _ts(v.created_at),
            ),
        )

    def versions(self, node_id: str) -> list[PromptVersion]:
        rows = self._c.execute(
            "SELECT * FROM prompt_versions WHERE node_id = ? ORDER BY version DESC", (node_id,)
        )
        return [
            PromptVersion(
                r["node_id"],
                r["version"],
                r["body"],
                VersionSource(r["source"]),
                _req(r["created_at"]),
                r["model"],
                r["prompt_template"],
                r["note"],
            )
            for r in rows
        ]
