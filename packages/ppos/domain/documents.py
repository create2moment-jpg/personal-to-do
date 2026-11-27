"""Knowledge inbox: documents, extracted pages and provenance-carrying chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ppos.shared.errors import ValidationError

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
CHUNK_TARGET = 1200  # characters
CHUNK_OVERLAP = 150


class DocStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    NEEDS_OCR = "needs_ocr"  # scanned PDF without a text layer
    FAILED = "failed"


DOC_KINDS = (
    "performance_report",
    "experience_letter",
    "framework",
    "feedback",
    "technical",
    "other",
    "own_note",  # evidence you wrote yourself (created by the app, shown as "My evidence note")
)


@dataclass
class Document:
    id: str
    title: str
    filename: str
    mime: str
    sha256: str
    size_bytes: int
    storage_path: str
    created_at: datetime
    updated_at: datetime
    kind: str = "other"
    status: DocStatus = DocStatus.QUEUED
    error: str | None = None
    pages: int | None = None
    chars: int | None = None
    extractor_version: str | None = None
    supersedes_id: str | None = None
    processed_at: datetime | None = None

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split()) or self.filename
        if self.kind not in DOC_KINDS:
            raise ValidationError(f"kind must be one of {', '.join(DOC_KINDS)}")


@dataclass(frozen=True)
class ExtractedPage:
    number: int  # 1-based
    text: str


@dataclass(frozen=True)
class Chunk:
    seq: int
    page_start: int | None
    page_end: int | None
    section: str | None
    text: str
    char_start: int
    char_end: int


_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?\s+\S.{0,80}|[A-Z][A-Z0-9 &/,:()'-]{3,80})$")


_MD_HEADING = re.compile(r"^#{1,6}\s+(\S.{0,120})$")


def heading_text(line: str) -> str | None:
    """The heading's text if ``line`` is a heading (Markdown, numbered or ALL CAPS)."""
    s = line.strip()
    m = _MD_HEADING.match(s)
    if m:
        return m.group(1).strip()
    return " ".join(s.split()) if detect_heading(s) else None


def first_heading(text: str) -> str | None:
    """Title candidate: a Markdown heading near the top, else the first line if it is a heading."""
    lines = [ln for ln in text.splitlines()[:40] if ln.strip()]
    for line in lines:
        m = _MD_HEADING.match(line.strip())
        if m:
            return m.group(1).strip()[:200]
    if lines and detect_heading(lines[0]):
        return " ".join(lines[0].split())[:200]
    return None


def detect_heading(line: str) -> bool:
    """Short numbered lines ("2.1 Impact") or ALL-CAPS lines count as headings."""
    s = line.strip()
    if _MD_HEADING.match(s):
        return True
    if not s or len(s) > 90 or (s.endswith((".", ",", ";")) and not re.match(r"^\d", s)):
        return False
    return bool(_HEADING.match(s)) and len(s.split()) <= 12


def chunk_pages(
    pages: list[ExtractedPage], target: int = CHUNK_TARGET, overlap: int = CHUNK_OVERLAP
) -> list[Chunk]:
    """Paragraph-aware chunking that records page, section and character offsets.

    Chunks never cross a page boundary, so every citation points to one page.

    Offsets refer to the document text formed by joining pages with "\\n\\n".
    """
    paras: list[tuple[int, int, str, str | None]] = []  # (page, offset, text, section)
    starts_section: set[int] = set()  # indexes of paragraphs that open a new section
    offset = 0
    section: str | None = None
    for page in pages:
        for block in re.split(r"\n\s*\n", page.text):
            text = " ".join(block.split())
            if text:
                first_line = block.strip().splitlines()[0]
                h = heading_text(first_line)
                if h:
                    section = h
                    starts_section.add(len(paras))
                idx = page.text.find(block.strip()[:30])
                paras.append((page.number, offset + max(idx, 0), text, section))
        offset += len(page.text) + 2

    chunks: list[Chunk] = []
    buf: list[tuple[int, int, str, str | None]] = []
    size = 0

    def flush() -> None:
        nonlocal buf, size
        if not buf:
            return
        text = "\n\n".join(p[2] for p in buf)
        chunks.append(
            Chunk(
                seq=len(chunks),
                page_start=buf[0][0],
                page_end=buf[-1][0],
                section=buf[-1][3],  # the section the chunk's content belongs to
                text=text,
                char_start=buf[0][1],
                char_end=buf[-1][1] + len(buf[-1][2]),
            )
        )
        tail = buf[-1]
        buf, size = ([tail], len(tail[2])) if overlap and len(tail[2]) <= overlap else ([], 0)

    buf_has_body = False
    for idx, para in enumerate(paras):
        text = para[2]
        if idx in starts_section and buf_has_body:
            # a new heading starts a new chunk, so sections can be cited separately
            flush()
            buf, size = [], 0
            buf_has_body = False
        if len(text) > target:  # split very long paragraphs on sentence boundaries
            flush()
            sentences = re.split(r"(?<=[.!?])\s+", text)
            piece = ""
            for s in sentences:
                if piece and len(piece) + len(s) + 1 > target:
                    buf, size = [(para[0], para[1], piece, para[3])], len(piece)
                    flush()
                    piece = s
                else:
                    piece = f"{piece} {s}".strip()
            if piece:
                buf, size = [(para[0], para[1], piece, para[3])], len(piece)
                flush()
            continue
        if buf and para[0] != buf[-1][0]:
            # never let a chunk span pages: citations must point to one page
            flush()
            buf, size = [], 0  # no overlap carried across a page boundary
        elif buf and size + len(text) > target:
            flush()
        buf.append(para)
        size += len(text) + 2
        buf_has_body = buf_has_body or idx not in starts_section
    # Emit the remainder unless it is only the overlap tail of the previous chunk.
    only_tail = len(buf) == 1 and bool(chunks) and buf[0][2] in chunks[-1].text
    if buf and not only_tail:
        flush()
    return chunks
