"""Build small .docx files for tests (no Word needed)."""

from __future__ import annotations

import io
import zipfile
from xml.sax.saxutils import escape

_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def para(text: str, style: str | None = None, numbered: bool = False) -> str:
    ppr = ""
    if style or numbered:
        inner = f'<w:pStyle w:val="{style}"/>' if style else ""
        inner += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>' if numbered else ""
        ppr = f"<w:pPr>{inner}</w:pPr>"
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


PAGE_BREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def table(rows: list[list[str]]) -> str:
    trs = "".join(
        "<w:tr>" + "".join(f"<w:tc>{para(c)}</w:tc>" for c in r) + "</w:tr>" for r in rows
    )
    return f"<w:tbl>{trs}</w:tbl>"


def docx(body: str, title: str | None = None, document_xml: str | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(
            "word/document.xml",
            document_xml
            or f'<?xml version="1.0"?><w:document {_NS}><w:body>{body}</w:body></w:document>',
        )
        if title:
            z.writestr(
                "docProps/core.xml",
                '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/'
                'metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
                f"<dc:title>{escape(title)}</dc:title></cp:coreProperties>",
            )
    return buf.getvalue()
