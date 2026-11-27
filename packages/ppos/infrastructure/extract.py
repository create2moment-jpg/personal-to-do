"""Type sniffing and text extraction (PDF via pypdf, Word, plain text / Markdown)."""

from __future__ import annotations

import io
import logging

from ppos.domain.documents import ExtractedPage, first_heading
from ppos.infrastructure.docx import DOCX_MIME, docx_pages, docx_title, is_docx
from ppos.shared.errors import ValidationError

EXTRACTOR_VERSION = "extract:v2(pypdf5,docx1,text)+chunk:v2"
log = logging.getLogger("ppos.extract")

TEXT_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown"}


def sniff(filename: str, data: bytes) -> str:
    """Decide the type from content (magic bytes), not just the name."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if is_docx(data):
        return DOCX_MIME
    if b"\x00" not in data[:4096]:
        try:
            data[:65536].decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            return TEXT_EXTENSIONS.get(ext, "text/plain")
    if ext == ".doc":
        raise ValidationError("old .doc files are not supported — save as .docx or PDF")
    raise ValidationError("unsupported file type — PDF, Word (.docx), .txt and .md are supported")


def extract_pages(mime: str, data: bytes) -> list[ExtractedPage]:
    if mime == DOCX_MIME:
        return docx_pages(data)
    if mime == "application/pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise ValidationError("the PDF is password-protected")
            pages = [
                ExtractedPage(i + 1, (p.extract_text() or "").replace("\r", ""))
                for i, p in enumerate(reader.pages)
            ]
        except ValidationError:
            raise
        except Exception as exc:  # pypdf raises many types on damaged files
            raise ValidationError(f"could not read the PDF: {exc}") from exc
        return pages
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n")
    parts = text.split("\f") if "\f" in text else [text]
    return [ExtractedPage(i + 1, p) for i, p in enumerate(parts)]


def document_title(mime: str, data: bytes) -> str | None:
    """Title from the file's own metadata, when it has one."""
    if mime == "application/pdf":
        return pdf_title(data)
    if mime == DOCX_MIME:
        title = docx_title(data)
        if title:
            return title
        try:  # no title in the file's properties: its first heading
            pages = docx_pages(data)
        except ValidationError:
            return None
        return first_heading(pages[0].text) if pages else None
    return None


def pdf_title(data: bytes) -> str | None:
    try:
        from pypdf import PdfReader

        meta = PdfReader(io.BytesIO(data)).metadata
        title = (meta.title if meta else None) or None
        return str(title).strip() or None if title else None
    except Exception:  # metadata is optional
        return None
