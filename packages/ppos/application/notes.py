"""Note use cases: autosave with coalesced version history, restore, links."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Any

from ppos.application.ports import NoteQuery, UnitOfWork, UnitOfWorkFactory
from ppos.domain.notes import EntityType, Link, Note, NoteKind, NoteVersion
from ppos.domain.tasks import normalize_tags
from ppos.domain.wikilinks import (
    headings,
    link_first_mention,
    parse_links,
    rename_links,
    render_template,
    snippet,
    title_key,
    unlinked_mentions,
)
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
            _index_links(uow, note)
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
            old_title = note.title
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
                _index_links(uow, note)
            if "title" in changes and title_key(old_title) != title_key(note.title):
                note.links_updated = self._propagate_rename(uow, note, old_title, now)
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

    # ------------------------------------------------------------ [[wikilinks]]
    def _propagate_rename(self, uow: UnitOfWork, note: Note, old_title: str, now: Any) -> int:
        """Obsidian-style: links to the old title now point at the new one.

        Skipped when another note still carries the old title (the links stay
        valid for it). Every changed note gets a new version, so it is undoable.
        """
        old_key = title_key(old_title)
        if any(title_key(t) == old_key for i, t, _, _ in uow.notes.titles() if i != note.id):
            return 0
        changed = 0
        for source_id in uow.notes.sources_linking(old_key):
            src = note if source_id == note.id else uow.notes.get(source_id)
            if src is None:
                continue
            body, count = rename_links(src.body, old_title, note.title)
            if not count:
                continue
            src.body = body
            src.version += 1
            src.last_snapshot_at = now
            src.updated_at = now
            uow.notes.update(src)
            uow.notes.add_version(_snapshot(src, now))
            _index_links(uow, src)
            changed += source_id != note.id
        if changed:
            uow.audit.record(
                "note", note.id, "rename_links", details={"from": old_title, "notes": changed}
            )
        return changed

    def ensure_link_index(self) -> int:
        """Build the [[link]] index once for notes written before it existed."""
        with self._uow() as uow:
            if uow.notes.link_count() > 0:
                return 0
            notes = uow.notes.find(NoteQuery(limit=100_000))
            for n in notes:
                _index_links(uow, n)
            uow.commit()
            return len(notes)

    def titles(self) -> list[dict[str, str]]:
        with self._uow() as uow:
            return [
                {"id": i, "title": t, "kind": k, "updated_at": u}
                for i, t, k, u in uow.notes.titles()
            ]

    def connections(self, note_id: str) -> dict[str, Any]:
        """Outgoing links, backlinks (with context) and unlinked mentions of a note."""
        with self._uow() as uow:
            note = _require_note(uow, note_id)
            by_key = _resolver(uow)
            outgoing = []
            for key, target, heading, alias in uow.notes.links_from(note.id):
                hit = by_key.get(key)
                outgoing.append(
                    {
                        "title": hit[1] if hit else target,
                        "note_id": hit[0] if hit else None,
                        "heading": heading,
                        "alias": alias,
                    }
                )
            key = title_key(note.title)
            backlinks: list[dict[str, Any]] = []
            linked_ids = set(uow.notes.sources_linking(key)) - {note.id}
            for sid in linked_ids:
                src = uow.notes.get(sid)
                if src is None:
                    continue
                snips = [
                    snippet(src.body, lk.start, lk.end)
                    for lk in parse_links(src.body)
                    if lk.key == key
                ][:3]
                backlinks.append({"note_id": src.id, "title": src.title, "snippets": snips})
            unlinked: list[dict[str, Any]] = []
            for nid, title, _kind, _u in uow.notes.titles():
                if nid == note.id or nid in linked_ids:
                    continue
                src = uow.notes.get(nid)
                if src is None:
                    continue
                spans = unlinked_mentions(src.body, note.title)
                if spans:
                    unlinked.append(
                        {
                            "note_id": nid,
                            "title": title,
                            "count": len(spans),
                            "snippets": [snippet(src.body, a, b) for a, b in spans[:2]],
                        }
                    )
            backlinks.sort(key=lambda b: str(b["title"]).casefold())
            unlinked.sort(key=lambda u: (-int(u["count"]), str(u["title"]).casefold()))
            return {
                "outgoing": outgoing,
                "backlinks": backlinks,
                "unlinked": unlinked[:30],
                "outline": [{"level": lv, "text": tx} for lv, tx in headings(note.body)],
            }

    def link_mention(self, note_id: str, source_id: str) -> Note:
        """Turn the first unlinked mention of this note's title in ``source_id`` into a link."""
        target = self.get(note_id)
        source = self.get(source_id)
        body = link_first_mention(source.body, target.title)
        if body is None:
            raise ValidationError(f"no unlinked mention of “{target.title}” in that note")
        return self.update(source_id, {"body": body}, force_snapshot=True)

    def graph(self, note_id: str | None = None, depth: int = 1) -> dict[str, Any]:
        """Nodes and edges of the note graph — all notes, or ``depth`` steps around one."""
        with self._uow() as uow:
            by_key = _resolver(uow)
            info = {i: (t, k) for i, t, k, _ in uow.notes.titles()}
            edges: set[tuple[str, str]] = set()
            ghosts: dict[str, str] = {}
            for source_id, key in uow.notes.all_links():
                hit = by_key.get(key)
                if hit:
                    if hit[0] != source_id:
                        edges.add((source_id, hit[0]))
                else:
                    gid = f"ghost:{key}"
                    ghosts.setdefault(gid, key)
                    edges.add((source_id, gid))
            if note_id is not None:
                _require_note(uow, note_id)
                keep = {note_id}
                for _ in range(max(1, min(depth, 3))):
                    keep |= {b for a, b in edges if a in keep} | {a for a, b in edges if b in keep}
                edges = {(a, b) for a, b in edges if a in keep and b in keep}
                ids = keep
            else:
                ids = set(info) | {b for _, b in edges}
            degree: dict[str, int] = {}
            for a, b in edges:
                degree[a] = degree.get(a, 0) + 1
                degree[b] = degree.get(b, 0) + 1
            nodes = []
            for nid in ids:
                if nid in info:
                    title, kind = info[nid]
                    nodes.append({"id": nid, "title": title, "kind": kind, "ghost": False})
                elif nid in ghosts:
                    nodes.append({"id": nid, "title": ghosts[nid], "kind": "ghost", "ghost": True})
            for n in nodes:
                n["degree"] = degree.get(str(n["id"]), 0)
            return {
                "nodes": nodes,
                "edges": [{"source": a, "target": b} for a, b in sorted(edges)],
            }

    def from_template(self, template_id: str, title: str = "") -> Note:
        tpl = self.get(template_id)
        if tpl.kind != NoteKind.TEMPLATE:
            raise ValidationError("that note is not a template")
        today = self._clock.today()
        now = self._clock.now()
        name = title.strip() or f"{tpl.title} {today.isoformat()}"
        values = {
            "date": today.isoformat(),
            "time": now.strftime("%H:%M"),
            "weekday": today.strftime("%A"),
            "title": name,
        }
        return self.create(
            title=name,
            body=render_template(tpl.body, values),
            tags=[t for t in tpl.tags if t != "template"],
        )


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


def _index_links(uow: UnitOfWork, note: Note) -> None:
    uow.notes.replace_links(
        note.id,
        [(lk.key, lk.target, lk.heading, lk.alias, lk.start) for lk in parse_links(note.body)],
    )


def _resolver(uow: UnitOfWork) -> dict[str, tuple[str, str]]:
    """title key -> (note id, title); the most recently updated note wins a tie."""
    out: dict[str, tuple[str, str]] = {}
    for nid, title, _kind, _updated in uow.notes.titles():  # newest first
        out.setdefault(title_key(title), (nid, title))
    return out


def _snapshot(note: Note, at: Any) -> NoteVersion:
    return NoteVersion(note.id, note.version, note.title, note.body, at)


def _title_from_body(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            return stripped[:120]
    return "Untitled"
