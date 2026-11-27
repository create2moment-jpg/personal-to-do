import dataclasses

import pytest

from ppos.bootstrap import Container, build_container
from ppos.domain.documents import DocStatus, ExtractedPage
from ppos.infrastructure.config import Settings
from ppos.infrastructure.jobs import InlineJobRunner
from ppos.infrastructure.ocr import ocr_pdf, ocr_tools
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError
from tests.pdfgen import make_pdf


@pytest.fixture
def docs(settings: Settings, clock: FixedClock) -> Container:
    return build_container(settings, clock, jobs=InlineJobRunner())


def _with_ocr(c: Container, engine: str, pages: list[str]) -> list[bytes]:
    calls: list[bytes] = []

    def fake(data: bytes) -> list[ExtractedPage]:
        calls.append(data)
        return [ExtractedPage(i + 1, t) for i, t in enumerate(pages)]

    svc = c.documents
    svc._x = dataclasses.replace(svc._x, ocr=fake, ocr_version=lambda: engine)  # type: ignore[attr-defined]
    return calls


def test_scanned_pdf_without_ocr_explains_how_to_enable_it(docs: Container) -> None:
    _with_ocr(docs, "", [])  # OCR not installed
    d = docs.documents.ingest("scan.pdf", make_pdf([[], []])).document
    d, _ = docs.documents.get(d.id)
    assert d.status == DocStatus.NEEDS_OCR and "install Tesseract" in (d.error or "")


def test_scanned_pdf_is_read_with_ocr_and_marked(docs: Container) -> None:
    calls = _with_ocr(
        docs,
        "tesseract-5.3",
        ["Mid-year review. Led the retrieval benchmark.", "Delegate more to junior engineers."],
    )
    d = docs.documents.ingest("scan.pdf", make_pdf([[], []])).document
    d, chunks = docs.documents.get(d.id)
    assert len(calls) == 1 and d.status == DocStatus.READY and d.error is None
    assert d.extractor_version and d.extractor_version.endswith("+ocr(tesseract-5.3)")
    assert chunks and chunks[0]["extractor_version"] == d.extractor_version
    [hit] = docs.documents.search("delegate junior")
    assert hit.page_start == 2
    # an "update outdated" pass does not OCR the same file again
    assert docs.documents.reindex(None, only_outdated=True) == 0
    assert len(calls) == 1


def test_ocr_that_finds_nothing_keeps_needs_ocr(docs: Container) -> None:
    _with_ocr(docs, "tesseract-5.3", ["", ""])
    d = docs.documents.ingest("blank.pdf", make_pdf([[], []])).document
    d, _ = docs.documents.get(d.id)
    assert d.status == DocStatus.NEEDS_OCR and "OCR found no readable text" in (d.error or "")
    # installing / fixing OCR later: outdated pass retries documents that still need it
    _with_ocr(docs, "tesseract-5.3", ["Now readable text on page one of the scan."])
    assert docs.documents.reindex(None, only_outdated=True) == 1


def test_ocr_language_is_validated() -> None:
    if ocr_tools() is None:
        pytest.skip("Tesseract / Poppler not installed")
    with pytest.raises(ValidationError, match="language"):
        ocr_pdf(b"%PDF-1.4", lang="eng; rm -rf /")


@pytest.mark.skipif(ocr_tools() is None, reason="Tesseract / Poppler not installed")
def test_real_tesseract_reads_an_image_only_pdf(docs: Container) -> None:
    from tests.pdfgen import make_scanned_pdf

    scan = make_scanned_pdf(["QUARTERLY REVIEW", "Improved recall by eleven percent."], dpi=200)
    d = docs.documents.ingest("scan.pdf", scan).document
    d, chunks = docs.documents.get(d.id)
    assert d.status == DocStatus.READY, d.error
    assert "+ocr(tesseract" in (d.extractor_version or "")
    text = " ".join(str(c["text"]) for c in chunks).lower()
    assert "quarterly review" in text and "recall" in text
