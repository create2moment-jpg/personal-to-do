"""Notes, note versions and the generic cross-entity link."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum

from ppos.domain.tasks import normalize_tags
from ppos.shared.errors import ValidationError

MAX_NOTE_BYTES = 2_000_000


class NoteKind(str, Enum):
    GENERAL = "general"
    JOURNAL = "journal"
    MEETING = "meeting"
    TECHNICAL = "technical"
    PROJECT = "project"
    IDEA = "idea"
    LEARNING = "learning"
    CAREER_EVIDENCE = "career_evidence"
    TEMPLATE = "template"  # a reusable starting point ({{date}}, {{title}} …)


@dataclass
class Note:
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    body: str = ""
    kind: NoteKind = NoteKind.GENERAL
    project_id: str | None = None
    note_date: date | None = None
    tags: list[str] = field(default_factory=list)
    version: int = 1
    last_snapshot_at: datetime | None = None
    links_updated: int = 0  # set by a rename: other notes whose [[links]] were updated (not stored)

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split()) or "Untitled"
        self.tags = normalize_tags(self.tags)
        if len(self.body.encode()) > MAX_NOTE_BYTES:
            raise ValidationError("note body is too large")

    def needs_snapshot(self, at: datetime, interval: timedelta) -> bool:
        """Autosave coalescing: snapshot at most once per ``interval``.

        The *current* content always lives on the note row; versions are the
        immutable history, so nothing is ever silently lost.
        """
        return self.last_snapshot_at is None or at - self.last_snapshot_at >= interval


@dataclass(frozen=True)
class NoteVersion:
    note_id: str
    version: int
    title: str
    body: str
    created_at: datetime


class EntityType(str, Enum):
    TASK = "task"
    NOTE = "note"
    PROJECT = "project"
    DAY = "day"
    PAGE = "page"
    CHUNK = "chunk"


@dataclass(frozen=True)
class Link:
    id: str
    source_type: EntityType
    source_id: str
    target_type: EntityType
    target_id: str
    created_at: datetime
