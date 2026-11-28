"""Markdown vault export / import, Obsidian-compatible (B-031).

Export: a zip with one ``.md`` file per note in a folder per kind, YAML front
matter (kind, tags, dates, id) and the body with ``[[links]]`` unescaped, so
the zip opens as an Obsidian vault. Import: a vault zip or single ``.md``
files; titles come from front matter or the file name, links resolve by title.
Nothing is written to disk on import; archives are size-capped and only
``.md`` members are read.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date

from ppos.application.notes import NoteService
from ppos.application.ports import NoteQuery
from ppos.domain.notes import Note, NoteKind
from ppos.shared.errors import ValidationError

MAX_ARCHIVE = 50 * 1024 * 1024
MAX_FILE = 2 * 1024 * 1024
MAX_FILES = 5000
FOLDERS = {
    NoteKind.GENERAL: "Notes",
    NoteKind.JOURNAL: "Journal",
    NoteKind.MEETING: "Meetings",
    NoteKind.TECHNICAL: "Technical",
    NoteKind.PROJECT: "Projects",
    NoteKind.IDEA: "Ideas",
    NoteKind.LEARNING: "Learning",
    NoteKind.CAREER_EVIDENCE: "Career evidence",
    NoteKind.TEMPLATE: "Templates",
}
_KIND_BY_FOLDER = {v.casefold(): k for k, v in FOLDERS.items()}
_ESCAPED_LINK = re.compile(r"\\\[\\\[(.+?)\\\]\\\]")
_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]\x00-\x1f]')
_FRONT = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def file_name(title: str) -> str:
    """A title as a portable file name (Obsidian forbids some characters)."""
    name = " ".join(_UNSAFE.sub(" ", title).split()).strip(" .")[:120]
    return name or "Untitled"


def obsidian_body(body: str) -> str:
    """The editor may store ``\\[\\[link\\]\\]``; Obsidian wants ``[[link]]``."""
    return _ESCAPED_LINK.sub(lambda m: "[[" + m.group(1).replace("\\|", "|") + "]]", body)


def _yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_markdown(n: Note) -> str:
    lines = ["---", f"title: {_yaml_str(n.title)}", f"kind: {n.kind.value}"]
    if n.tags:
        lines.append("tags:")
        lines += [f"  - {t}" for t in n.tags]
    if n.note_date:
        lines.append(f"date: {n.note_date.isoformat()}")
    lines += [f"created: {n.created_at.isoformat()}", f"updated: {n.updated_at.isoformat()}"]
    lines += [f"ppos_id: {n.id}", "---", ""]
    return "\n".join(lines) + obsidian_body(n.body).rstrip() + "\n"


def parse_markdown(text: str) -> tuple[dict[str, object], str]:
    """Front matter (a small, safe YAML subset) and the body."""
    meta: dict[str, object] = {}
    m = _FRONT.match(text)
    if not m:
        return meta, text
    key: str | None = None
    for raw in m.group(1).splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s*(.*)$", raw)
        if item and key:
            existing = meta.get(key)
            values = existing if isinstance(existing, list) else []
            values.append(_unquote(item.group(1)))
            meta[key] = values
            continue
        kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if not kv:
            continue
        key, value = kv.group(1).lower(), kv.group(2).strip()
        if value.startswith("[") and value.endswith("]"):
            meta[key] = [_unquote(v) for v in value[1:-1].split(",") if v.strip()]
        else:
            meta[key] = _unquote(value) if value else []
    return meta, text[m.end() :]


def _unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return v


@dataclass
class ImportResult:
    created: list[str] = field(default_factory=list)  # titles
    skipped: list[str] = field(default_factory=list)  # identical note already here
    errors: list[str] = field(default_factory=list)


class VaultService:
    def __init__(self, notes: NoteService) -> None:
        self._notes = notes

    def export_zip(self) -> bytes:
        notes = self._notes.find(NoteQuery(limit=100_000))
        buf = io.BytesIO()
        used: set[str] = set()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for n in sorted(notes, key=lambda x: x.created_at):
                folder = FOLDERS.get(n.kind, "Notes")
                base = f"{folder}/{file_name(n.title)}"
                path, i = f"{base}.md", 2
                while path.casefold() in used:
                    path, i = f"{base} ({i}).md", i + 1
                used.add(path.casefold())
                z.writestr(path, to_markdown(n))
            z.writestr(
                "README.txt",
                "Personal OS notes\n\nExported as an Obsidian-compatible vault: one Markdown file"
                " per note, [[links]] by title, metadata in front matter.\n",
            )
        return buf.getvalue()

    def import_files(self, filename: str, data: bytes) -> ImportResult:
        if len(data) > MAX_ARCHIVE:
            raise ValidationError("files up to 50 MB can be imported")
        files: list[tuple[str, bytes]] = []
        if data.startswith(b"PK\x03\x04"):
            try:
                z = zipfile.ZipFile(io.BytesIO(data))
            except zipfile.BadZipFile as exc:
                raise ValidationError("the zip file is damaged") from exc
            members = [
                i
                for i in z.infolist()
                if i.filename.lower().endswith(".md")
                and not i.is_dir()
                and not any(p.startswith(".") for p in i.filename.split("/"))  # .obsidian, .trash
            ]
            if len(members) > MAX_FILES:
                raise ValidationError(f"at most {MAX_FILES} notes per import")
            if sum(i.file_size for i in members) > MAX_ARCHIVE * 4:
                raise ValidationError("the archive expands to too much data")
            for i in members:
                if i.file_size > MAX_FILE:
                    continue
                files.append((i.filename, z.read(i)))
        elif filename.lower().endswith(".md"):
            files.append((filename, data))
        else:
            raise ValidationError("import a vault .zip or a .md file")

        existing = {
            (n.title.casefold(), obsidian_body(n.body).strip())
            for n in self._notes.find(NoteQuery(limit=100_000))
        }
        result = ImportResult()
        for path, raw in files:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                result.errors.append(f"{path}: not UTF-8 text")
                continue
            meta, body = parse_markdown(text.replace("\r\n", "\n"))
            parts = path.split("/")
            title = str(meta.get("title") or parts[-1][:-3]).strip() or "Untitled"
            kind_raw = str(meta.get("kind") or "")
            kind = (
                NoteKind(kind_raw)
                if kind_raw in NoteKind._value2member_map_
                else _KIND_BY_FOLDER.get(parts[-2].casefold(), NoteKind.GENERAL)
                if len(parts) > 1
                else NoteKind.GENERAL
            )
            tags_raw = meta.get("tags") or []
            tags = [
                str(t).lstrip("#") for t in (tags_raw if isinstance(tags_raw, list) else [tags_raw])
            ]
            key = (title.casefold(), obsidian_body(body).strip())
            if key in existing:
                result.skipped.append(title)
                continue
            note_date = None
            if kind == NoteKind.JOURNAL and meta.get("date"):
                try:
                    note_date = date.fromisoformat(str(meta["date"]))
                except ValueError:
                    note_date = None
            try:
                fields: dict[str, object] = {"kind": kind, "tags": tags}
                if note_date and self._notes.journal_for(note_date) is None:
                    fields["note_date"] = note_date
                elif kind == NoteKind.JOURNAL:
                    fields["kind"] = NoteKind.GENERAL  # one journal per day: keep it as a note
                self._notes.create(title=title, body=body.lstrip("\n"), **fields)
                existing.add(key)
                result.created.append(title)
            except Exception as exc:  # one bad file must not stop the import
                result.errors.append(f"{path}: {exc}")
        return result
