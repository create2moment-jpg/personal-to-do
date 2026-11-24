"""Prompt Book: books → chapters/sections (any depth) → pages, with versions."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ppos.domain.tasks import normalize_tags
from ppos.shared.errors import ValidationError

MAX_PAGE_BYTES = 500_000
MAX_DEPTH = 8
_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.-]{0,40})\s*\}\}")


class NodeKind(str, Enum):
    CHAPTER = "chapter"
    SECTION = "section"
    PAGE = "page"

    @property
    def is_container(self) -> bool:
        return self is not NodeKind.PAGE


class VersionSource(str, Enum):
    ORIGINAL = "original"
    EDITED = "edited"
    AI = "ai"
    USED = "used"
    RESTORED = "restored"


@dataclass
class Book:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    emoji: str | None = None
    description: str = ""
    position: float = 0.0

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split()) or "Untitled book"
        self.emoji = clean_emoji(self.emoji)


@dataclass
class BookNode:
    id: str
    book_id: str
    kind: NodeKind
    title: str
    created_at: datetime
    updated_at: datetime
    parent_id: str | None = None
    emoji: str | None = None
    body: str = ""
    tags: list[str] = field(default_factory=list)
    position: float = 0.0
    version: int = 1
    use_count: int = 0
    last_used_at: datetime | None = None
    rating: int | None = None

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split()) or (
            "Untitled page" if self.kind == NodeKind.PAGE else "Untitled"
        )
        self.emoji = clean_emoji(self.emoji)
        self.tags = normalize_tags(self.tags)
        if self.kind.is_container and self.body:
            raise ValidationError("only pages hold text")
        if len(self.body.encode()) > MAX_PAGE_BYTES:
            raise ValidationError("page is too large")
        if self.rating is not None and not 1 <= self.rating <= 5:
            raise ValidationError("rating must be 1–5")

    @property
    def variables(self) -> list[str]:
        return list(dict.fromkeys(_VAR_RE.findall(self.body)))


@dataclass(frozen=True)
class PromptVersion:
    node_id: str
    version: int
    body: str
    source: VersionSource
    created_at: datetime
    model: str | None = None
    prompt_template: str | None = None
    note: str = ""


def clean_emoji(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    if len(v) > 8:  # one emoji (possibly with modifiers / ZWJ sequence)
        raise ValidationError("emoji must be a single emoji")
    return v


def fill_variables(body: str, values: dict[str, str]) -> str:
    """Replace {{name}} placeholders; unknown ones are left as-is."""
    return _VAR_RE.sub(lambda m: values.get(m.group(1), m.group(0)), body)


def check_move(nodes: dict[str, BookNode], node_id: str, new_parent_id: str | None) -> None:
    """Validate moving ``node_id`` under ``new_parent_id`` (None = book root)."""
    if new_parent_id is None:
        return
    parent = nodes.get(new_parent_id)
    if parent is None:
        raise ValidationError("target does not exist")
    if not parent.kind.is_container:
        raise ValidationError("pages can only live inside chapters or sections")
    depth = 1
    current: str | None = new_parent_id
    while current is not None:
        if current == node_id:
            raise ValidationError("cannot move a chapter inside itself")
        current = nodes[current].parent_id if current in nodes else None
        depth += 1
        if depth > MAX_DEPTH:
            raise ValidationError(f"books can nest at most {MAX_DEPTH} levels")
