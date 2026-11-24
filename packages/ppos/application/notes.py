"""Note use cases: autosave with coalesced version history, restore, links."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from ppos.application.ports import NoteQuery, UnitOfWork, UnitOfWorkFactory
from ppos.domain.notes import EntityType, Link, Note, NoteKind, NoteVersion
from ppos.domain.tasks import normalize_tags
from ppos.shared.clock import Clock, new_id
from ppos.shared.errors import NotFoundError, ValidationError

NOTE_EDITABLE_FIELDS = frozenset({"title", "body", "kind", "project_id", "note_date", "tags"})


class NoteService:
    def __init__(
        self, uow_factory: UnitOfWorkFactory, clock: Clock, snapshot_interval: timedelta
    ) -> None:
        self._uow = uow_factory
        self._clock = clock
        self._interval = snapshot_interval

    def get(self, note_id: str) -> Note:
        with self._uow() as uow:
            return _require_note(uow, note_id)

    def find(self, query: NoteQuery) -> list[Note]:
        with self._uow() as uow:
            return uow.notes.find(query)

    def create(self, title: str = "", body: str = "", **fields: Any) -> Note:
        unknown = set(fields) - NOTE_EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"unknown note fields: {sorted(unknown)}")
        now = self._clock.now()
        with self._uow() as uow:
            if fields.get("project_id") and uow.projects.get(fields["project_id"]) is None:
                raise NotFoundError("project", fields["project_id"])
            note = Note(
                id=new_id(),
                title=title or _title_from_body(body),
                body=body,
                created_at=now,
                updated_at=now,
                last_snapshot_at=now,
                **fields,
            )
            uow.notes.add(note)
            uow.notes.add_version(_snapshot(note, now))
            uow.audit.record("note", note.id, "create", details={"title": note.title})
            uow.commit()
            return note

    def update(
        self, note_id: str, changes: Mapping[str, Any], *, force_snapshot: bool = False
    ) -> Note:
        """Autosave entry point.

        Content is written to the note row immediately. History keeps one
        version per editing window: while the window is open, autosaves keep
        the current version row up to date; once the window (snapshot
        interval) has elapsed, or ``force_snapshot`` is set, a new version
        number starts. Earlier windows' versions are never modified, so rapid
        autosaves do not flood history and nothing is silently discarded.
        """
        unknown = set(changes) - NOTE_EDITABLE_FIELDS
        if unknown:
            raise ValidationError(f"fields not editable: {sorted(unknown)}")
        now = self._clock.now()
        with self._uow() as uow:
            note = _require_note(uow, note_id)
            content_changed = any(
                k in changes and changes[k] != getattr(note, k) for k in ("title", "body")
            )
            if content_changed and (force_snapshot or note.needs_snapshot(now, self._interval)):
                note.version += 1
                note.last_snapshot_at = now
            for key, value in changes.items():
                if key == "tags":
                    value = normalize_tags(value)
                elif key == "kind":
                    value = NoteKind(value)
                elif key == "title":
                    value = " ".join(str(value).split()) or "Untitled"
                setattr(note, key, value)
            note.updated_at = now
            Note.__post_init__(note)  # re-validate size limits etc.
            uow.notes.update(note)
            if content_changed:
                uow.notes.add_version(_snapshot(note, now))  # upsert (note_id, version)
            uow.audit.record(
                "note",
                note.id,
                "update",
                details={"fields": sorted(changes), "version": note.version},
            )
            uow.commit()
            return note

    def versions(self, note_id: str) -> list[NoteVersion]:
        with self._uow() as uow:
            _require_note(uow, note_id)
            return uow.notes.versions(note_id)

    def get_version(self, note_id: str, version: int) -> NoteVersion:
        with self._uow() as uow:
            found = uow.notes.get_version(note_id, version)
            if found is None:
                raise NotFoundError("note version", f"{note_id}@{version}")
            return found

    def restore(self, note_id: str, version: int) -> Note:
        """Restoring creates a *new* version; history is append-only."""
        old = self.get_version(note_id, version)
        return self.update(note_id, {"title": old.title, "body": old.body}, force_snapshot=True)

    def delete(self, note_id: str) -> None:
        with self._uow() as uow:
            note = _require_note(uow, note_id)
            uow.notes.delete(note_id)
            uow.links.delete_for_entity(EntityType.NOTE, note_id)
            uow.audit.record("note", note_id, "delete", details={"title": note.title})
            uow.commit()

    def journal_for(self, day: date, create: bool = False) -> Note | None:
        with self._uow() as uow:
            existing = uow.notes.find_daily_journal(day)
        if existing is not None or not create:
            return existing
        title = f"Journal · {day.strftime('%A')}, {day.strftime('%B')} {day.day}"
        return self.create(title=title, kind=NoteKind.JOURNAL, note_date=day)


class LinkService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow_factory
        self._clock = clock

    def link(
        self, source_type: EntityType, source_id: str, target_type: EntityType, target_id: str
    ) -> Link:
        if (source_type, source_id) == (target_type, target_id):
            raise ValidationError("cannot link an entity to itself")
        with self._uow() as uow:
            for etype, eid in ((source_type, source_id), (target_type, target_id)):
                _require_entity(uow, etype, eid)
            for existing in uow.links.for_entity(source_type, source_id):
                if {
                    (existing.source_type, existing.source_id),
                    (existing.target_type, existing.target_id),
                } == {
                    (source_type, source_id),
                    (target_type, target_id),
                }:
                    return existing
            link = Link(new_id(), source_type, source_id, target_type, target_id, self._clock.now())
            uow.links.add(link)
            uow.commit()
            return link

    def unlink(self, link_id: str) -> None:
        with self._uow() as uow:
            uow.links.delete(link_id)
            uow.commit()

    def links_for(self, entity_type: EntityType, entity_id: str) -> list[Link]:
        with self._uow() as uow:
            return uow.links.for_entity(entity_type, entity_id)


def _require_note(uow: UnitOfWork, note_id: str) -> Note:
    note = uow.notes.get(note_id)
    if note is None:
        raise NotFoundError("note", note_id)
    return note


def _require_entity(uow: UnitOfWork, etype: EntityType, eid: str) -> None:
    found: object
    if etype == EntityType.TASK:
        found = uow.tasks.get(eid)
    elif etype == EntityType.NOTE:
        found = uow.notes.get(eid)
    elif etype == EntityType.PROJECT:
        found = uow.projects.get(eid)
    else:
        try:
            date.fromisoformat(eid)
            found = True
        except ValueError:
            found = None
    if found is None:
        raise NotFoundError(etype.value, eid)


def _snapshot(note: Note, at: Any) -> NoteVersion:
    return NoteVersion(note.id, note.version, note.title, note.body, at)


def _title_from_body(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return "Untitled"
