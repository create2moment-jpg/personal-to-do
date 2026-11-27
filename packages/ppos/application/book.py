"""Prompt Book use cases: tree editing, versions, copy for Copilot, AI improvement."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

from ppos.application.ports import UnitOfWork, UnitOfWorkFactory
from ppos.domain.book import (
    Book,
    BookNode,
    NodeKind,
    PromptVersion,
    VersionSource,
    check_move,
    fill_variables,
)
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

IMPROVE_STYLES: dict[str, str] = {
    "clearer": (
        "Make it clearer and better structured: state the goal first, then context, "
        "then the exact ask."
    ),
    "specific": (
        "Make it more specific: name the expected inputs, outputs, edge cases and "
        "acceptance criteria."
    ),
    "context": (
        "Add the context an assistant needs: language/framework, relevant files or functions, "
        "constraints. Use [placeholders] for anything unknown."
    ),
    "format": (
        "Add an explicit output format and constraints (e.g. code only, tests included, "
        "step-by-step), keeping it short."
    ),
    "concise": "Make it shorter and sharper without losing any requirement.",
}


@dataclass
class Improvement:
    original: str
    improved: str
    style: str
    model: str
    template: str
    latency_ms: int
    version: int  # version number stored for the AI suggestion


# (system, prompt, style) -> (text, model, template_ref, latency_ms)
Improver = Callable[[str, str], tuple[str, str, str, int]]
# (original, style_instruction) -> (text chunks, model, template_ref)
ImproverStream = Callable[[str, str], tuple[Iterator[str], str, str]]
# (original, improved) -> (bullet points, model)
Explainer = Callable[[str, str], tuple[list[str], str]]


class BookService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        clock: Clock,
        improver: Improver | None = None,
        *,
        improver_stream: ImproverStream | None = None,
        explainer: Explainer | None = None,
        cleaner: Callable[[str], str] = str.strip,
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._improver = improver
        self._improver_stream = improver_stream
        self._explainer = explainer
        self._clean = cleaner

    # books --------------------------------------------------------------
    def books(self) -> list[Book]:
        with self._uow() as uow:
            return uow.books.books()

    def create_book(self, title: str, emoji: str | None = None, description: str = "") -> Book:
        now = self._clock.now()
        with self._uow() as uow:
            pos = max((b.position for b in uow.books.books()), default=0) + 1
            b = Book(new_id(), title, now, now, emoji, description, pos)
            uow.books.add_book(b)
            uow.commit()
            return b

    def update_book(self, book_id: str, changes: Mapping[str, Any]) -> Book:
        with self._uow() as uow:
            b = self._book(uow, book_id)
            for k in ("title", "emoji", "description"):
                if k in changes:
                    setattr(b, k, changes[k])
            b.updated_at = self._clock.now()
            Book.__post_init__(b)
            uow.books.update_book(b)
            uow.commit()
            return b

    def delete_book(self, book_id: str) -> None:
        with self._uow() as uow:
            self._book(uow, book_id)
            uow.books.delete_book(book_id)
            uow.audit.record("book", book_id, "delete")
            uow.commit()

    def tree(self, book_id: str) -> tuple[Book, list[BookNode]]:
        with self._uow() as uow:
            return self._book(uow, book_id), uow.books.nodes(book_id)

    # nodes --------------------------------------------------------------
    def node(self, node_id: str) -> BookNode:
        with self._uow() as uow:
            return self._node(uow, node_id)

    def create_node(
        self,
        book_id: str,
        kind: NodeKind,
        title: str = "",
        parent_id: str | None = None,
        body: str = "",
        emoji: str | None = None,
        tags: list[str] | None = None,
    ) -> BookNode:
        now = self._clock.now()
        with self._uow() as uow:
            self._book(uow, book_id)
            nodes = {n.id: n for n in uow.books.nodes(book_id)}
            check_move(nodes, "", parent_id)
            n = BookNode(
                id=new_id(),
                book_id=book_id,
                kind=kind,
                title=title,
                parent_id=parent_id,
                body=body,
                emoji=emoji,
                tags=tags or [],
                created_at=now,
                updated_at=now,
                position=uow.books.max_position(book_id, parent_id) + 1,
            )
            uow.books.add_node(n)
            if kind == NodeKind.PAGE:
                uow.books.add_version(PromptVersion(n.id, 1, body, VersionSource.ORIGINAL, now))
            uow.commit()
            return n

    def update_node(self, node_id: str, changes: Mapping[str, Any]) -> BookNode:
        allowed = {"title", "emoji", "body", "tags", "rating"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        with self._uow() as uow:
            n = self._node(uow, node_id)
            for k, v in changes.items():
                setattr(n, k, v)
            n.updated_at = self._clock.now()
            BookNode.__post_init__(n)
            uow.books.update_node(n)
            uow.commit()
            return n

    def move(self, node_id: str, parent_id: str | None, position: float | None = None) -> BookNode:
        with self._uow() as uow:
            n = self._node(uow, node_id)
            nodes = {x.id: x for x in uow.books.nodes(n.book_id)}
            check_move(nodes, node_id, parent_id)
            n.parent_id = parent_id
            n.position = (
                position
                if position is not None
                else uow.books.max_position(n.book_id, parent_id) + 1
            )
            n.updated_at = self._clock.now()
            uow.books.update_node(n)
            uow.commit()
            return n

    def delete_node(self, node_id: str) -> None:
        with self._uow() as uow:
            n = self._node(uow, node_id)
            uow.books.delete_node(node_id)  # children cascade
            uow.audit.record("book_node", node_id, "delete", details={"title": n.title})
            uow.commit()

    # versions -----------------------------------------------------------
    def versions(self, node_id: str) -> list[PromptVersion]:
        with self._uow() as uow:
            self._node(uow, node_id)
            return uow.books.versions(node_id)

    def snapshot(
        self, node_id: str, source: VersionSource = VersionSource.EDITED, note: str = ""
    ) -> PromptVersion:
        with self._uow() as uow:
            n = self._page(uow, node_id)
            v = self._add_version(uow, n, n.body, source, note=note)
            uow.commit()
            return v

    def restore(self, node_id: str, version: int) -> BookNode:
        with self._uow() as uow:
            n = self._page(uow, node_id)
            old = next((v for v in uow.books.versions(node_id) if v.version == version), None)
            if old is None:
                raise NotFoundError("prompt version", f"{node_id}@{version}")
            n.body = old.body
            self._add_version(uow, n, old.body, VersionSource.RESTORED, note=f"restored v{version}")
            uow.books.update_node(n)
            uow.commit()
            return n

    def use(
        self, node_id: str, values: dict[str, str] | None = None, body: str | None = None
    ) -> str:
        """Prepare text for Copilot: fill variables, count the use, keep a version."""
        with self._uow() as uow:
            n = self._page(uow, node_id)
            text = fill_variables(body if body is not None else n.body, values or {})
            n.use_count += 1
            n.last_used_at = self._clock.now()
            latest = uow.books.versions(node_id)
            if not latest or latest[0].body != text:
                self._add_version(uow, n, text, VersionSource.USED, note="copied for an assistant")
            uow.books.update_node(n)
            uow.commit()
            return text

    def _improve_input(self, node_id: str, style: str, body: str | None) -> str:
        if style not in IMPROVE_STYLES:
            raise ValidationError(f"style must be one of {sorted(IMPROVE_STYLES)}")
        with self._uow() as uow:
            original = body if body is not None else self._page(uow, node_id).body
        if not original.strip():
            raise ValidationError("write something first — there is nothing to improve")
        return original

    @staticmethod
    def _no_ai() -> Exception:
        from ppos.ai.provider import AIUnavailableError

        return AIUnavailableError("Local AI is not configured.")

    def improve(self, node_id: str, style: str, body: str | None = None) -> Improvement:
        original = self._improve_input(node_id, style, body)
        if self._improver is None:
            raise self._no_ai()
        text, model, template, latency = self._improver(original, IMPROVE_STYLES[style])
        return self._store_suggestion(node_id, original, text, style, model, template, latency)

    def improve_stream(
        self, node_id: str, style: str, body: str | None = None
    ) -> Iterator[dict[str, Any]]:
        """Validate now, then yield ``delta`` events while the model writes and one
        final ``done`` event carrying the stored suggestion (or an ``error`` event)."""
        original = self._improve_input(node_id, style, body)
        if self._improver_stream is None:
            raise self._no_ai()
        chunks, model, template = self._improver_stream(original, IMPROVE_STYLES[style])

        def events() -> Iterator[dict[str, Any]]:
            start = time.perf_counter()
            parts: list[str] = []
            try:
                for piece in chunks:
                    parts.append(piece)
                    yield {"type": "delta", "text": piece}
                text = self._clean("".join(parts))
                latency = int((time.perf_counter() - start) * 1000)
                r = self._store_suggestion(node_id, original, text, style, model, template, latency)
                yield {"type": "done", **r.__dict__}
            except Exception as exc:  # reported to the client; nothing is stored
                yield {"type": "error", "message": str(exc) or type(exc).__name__}
            finally:  # stopped or disconnected: release the model server right away
                close = getattr(chunks, "close", None)
                if close is not None:
                    close()

        return events()

    def explain(self, original: str, improved: str) -> tuple[list[str], str]:
        """Short, plain-language list of what the suggestion changed (AI, read-only)."""
        if not original.strip() or not improved.strip():
            raise ValidationError("both the original and the suggestion are needed")
        if self._explainer is None:
            raise self._no_ai()
        return self._explainer(original, improved)

    def _store_suggestion(
        self,
        node_id: str,
        original: str,
        text: str,
        style: str,
        model: str,
        template: str,
        latency: int,
    ) -> Improvement:
        with self._uow() as uow:
            n = self._page(uow, node_id)
            v = self._add_version(
                uow,
                n,
                text,
                VersionSource.AI,
                model=model,
                template=template,
                note=f"suggestion: {style}",
            )
            uow.books.update_node(n)
            uow.audit.record(
                "book_node",
                node_id,
                "ai_improve",
                actor="ai",
                details={"model": model, "template": template, "style": style},
            )
            uow.commit()
        return Improvement(original, text, style, model, template, latency, v.version)

    def accept(self, node_id: str, version: int) -> BookNode:
        """Make an AI suggestion the page text. The original stays in history."""
        with self._uow() as uow:
            n = self._page(uow, node_id)
            v = next((x for x in uow.books.versions(node_id) if x.version == version), None)
            if v is None:
                raise NotFoundError("prompt version", f"{node_id}@{version}")
            n.body = v.body
            n.updated_at = self._clock.now()
            uow.books.update_node(n)
            uow.audit.record("book_node", node_id, "accept_ai", details={"version": version})
            uow.commit()
            return n

    # helpers ------------------------------------------------------------
    def _add_version(
        self,
        uow: UnitOfWork,
        n: BookNode,
        body: str,
        source: VersionSource,
        model: str | None = None,
        template: str | None = None,
        note: str = "",
    ) -> PromptVersion:
        n.version = max((v.version for v in uow.books.versions(n.id)), default=0) + 1
        v = PromptVersion(n.id, n.version, body, source, self._clock.now(), model, template, note)
        uow.books.add_version(v)
        return v

    @staticmethod
    def _book(uow: UnitOfWork, book_id: str) -> Book:
        b = uow.books.get_book(book_id)
        if b is None:
            raise NotFoundError("book", book_id)
        return b

    @staticmethod
    def _node(uow: UnitOfWork, node_id: str) -> BookNode:
        n = uow.books.get_node(node_id)
        if n is None:
            raise NotFoundError("page", node_id)
        return n

    def _page(self, uow: UnitOfWork, node_id: str) -> BookNode:
        n = self._node(uow, node_id)
        if n.kind != NodeKind.PAGE:
            raise ValidationError("only pages have text and versions")
        return n
