"""Word (.docx) text extraction with the standard library only.

A .docx is a zip of XML parts. We read ``word/document.xml`` (paragraphs,
headings, lists, tables, page breaks) and ``docProps/core.xml`` (title). The
input is untrusted: archive members are size-capped before decompressing and
any XML with a DOCTYPE is refused, so entity-expansion tricks cannot run.
"""

from __future__ import annotations

import io
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator

from ppos.domain.documents import ExtractedPage
from ppos.shared.errors import ValidationError

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_PART_BYTES = 64 * 1024 * 1024  # uncompressed size of one XML part

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING = re.compile(r"^(?:heading|berschrift|titre|título|titolo)\s*([1-6])$", re.IGNORECASE)


def is_docx(data: bytes) -> bool:
    if not data.startswith(b"PK\x03\x04"):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            return "word/document.xml" in z.namelist()
    except zipfile.BadZipFile:
        return False


def _part(z: zipfile.ZipFile, name: str) -> ET.Element | None:
    try:
        info = z.getinfo(name)
    except KeyError:
        return None
    if info.file_size > MAX_PART_BYTES:
        raise ValidationError("the Word file is too large to read safely")
    with z.open(info) as f:
        raw = f.read(MAX_PART_BYTES + 1)
    if len(raw) > MAX_PART_BYTES:
        raise ValidationError("the Word file is too large to read safely")
    if b"<!DOCTYPE" in raw[:4096].upper() or b"<!ENTITY" in raw.upper():
        raise ValidationError("the Word file contains a DOCTYPE — refused for safety")
    try:
        return ET.fromstring(raw)  # noqa: S314 - no DOCTYPE, so no entities
    except ET.ParseError as exc:
        raise ValidationError(f"could not read the Word file: {exc}") from exc


def _open(data: bytes) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValidationError("the Word file is damaged (not a valid zip archive)") from exc


def _style(p: ET.Element) -> str:
    el = p.find(f"{W}pPr/{W}pStyle")
    return (el.get(f"{W}val") or "") if el is not None else ""


def _runs(p: ET.Element) -> Iterator[str]:
    """Text of a paragraph in order; ``\\f`` marks a page break."""
    for el in p.iter():
        tag = el.tag
        if tag == f"{W}t" and el.text:
            yield el.text
        elif tag == f"{W}tab":
            yield "\t"
        elif tag == f"{W}br":
            yield "\f" if el.get(f"{W}type") == "page" else "\n"
        elif tag == f"{W}lastRenderedPageBreak":
            yield "\f"


def _paragraph(p: ET.Element) -> str:
    text = "".join(_runs(p))
    if not text.strip("\f"):
        return text if "\f" in text else ""
    style = _style(p)
    m = _HEADING.match(style.replace("-", " ").strip()) or re.match(r"^Heading([1-6])$", style)
    if style.lower() == "title":
        return "# " + text.strip()
    if m:
        return "#" * int(m.group(1)) + " " + text.strip()
    if p.find(f"{W}pPr/{W}numPr") is not None or style.lower().startswith("list"):
        return "- " + text.strip()
    return text


def _table(tbl: ET.Element) -> str:
    rows = []
    for tr in tbl.iter(f"{W}tr"):
        cells = []
        for tc in tr.findall(f"{W}tc"):
            cell = " ".join(
                t for t in (_paragraph(p).strip() for p in tc.iter(f"{W}p")) if t.strip("\f")
            )
            cells.append(cell.replace("\f", " "))
        if any(cells):
            rows.append(" | ".join(cells))
    return "\n".join(rows)


def docx_pages(data: bytes) -> list[ExtractedPage]:
    with _open(data) as z:
        root = _part(z, "word/document.xml")
    if root is None:
        raise ValidationError("this is not a Word document (word/document.xml missing)")
    body = root.find(f"{W}body")
    blocks: list[str] = []
    for el in list(body) if body is not None else []:
        if el.tag == f"{W}p":
            blocks.append(_paragraph(el))
        elif el.tag == f"{W}tbl":
            blocks.append(_table(el))
    text = "\n\n".join(b for b in blocks if b)
    text = re.sub(r"\n*\f\n*", "\f", text)  # a page break separates pages, not paragraphs
    parts = [p.strip("\n") for p in text.split("\f")]
    while len(parts) > 1 and not parts[-1].strip():
        parts.pop()
    pages = [p for p in parts if p.strip()] or [""]
    return [ExtractedPage(i + 1, p) for i, p in enumerate(pages)]


def docx_title(data: bytes) -> str | None:
    try:
        with _open(data) as z:
            core = _part(z, "docProps/core.xml")
    except ValidationError:
        return None
    if core is None:
        return None
    el = core.find("{http://purl.org/dc/elements/1.1/}title")
    title = (el.text or "").strip() if el is not None else ""
    return title[:200] or None
