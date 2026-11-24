"""Type sniffing and text extraction (PDF via pypdf, plain text / Markdown)."""

from __future__ import annotations

import io
import logging

from ppos.domain.documents import ExtractedPage
from ppos.shared.errors import ValidationError

EXTRACTOR_VERSION = "extract:v1(pypdf5,text)+chunk:v1"
log = logging.getLogger("ppos.extract")

TEXT_EXTENSIONS = {".txt": "text/plain", ".md": "text/markdown", ".markdown": "text/markdown"}


def sniff(filename: str, data: bytes) -> str:
    """Decide the type from content (magic bytes), not just the name."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if b"\x00" not in data[:4096]:
        try:
            data[:65536].decode("utf-8")
        except UnicodeDecodeError:
            pass
        else:
            return TEXT_EXTENSIONS.get(ext, "text/plain")
    if data.startswith(b"PK\x03\x04") and ext == ".docx":
        raise ValidationError(
            "Word files are not supported yet — export as PDF for now (backlog B-006)"
        )
    raise ValidationError("unsupported file type — PDF, .txt and .md are supported")


def extract_pages(mime: str, data: bytes) -> list[ExtractedPage]:
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


def pdf_title(data: bytes) -> str | None:
    try:
        from pypdf import PdfReader

        meta = PdfReader(io.BytesIO(data)).metadata
        title = (meta.title if meta else None) or None
        return str(title).strip() or None if title else None
    except Exception:  # metadata is optional
        return None
