from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container, build_container
from ppos.domain.documents import ExtractedPage, chunk_pages, detect_heading
from ppos.infrastructure.config import Settings
from ppos.infrastructure.document_store import DocumentStore
from ppos.infrastructure.jobs import InlineJobRunner
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError
from ppos_api.main import create_app
from tests.conftest import POSIX_MODES
from tests.pdfgen import make_pdf

REVIEW = [
    ["MID-YEAR PERFORMANCE REVIEW", "", "Summary", "Strong ownership of the retrieval platform."],
    [
        "2. Achievements",
        "Led the hybrid retrieval benchmark adopted by two teams.",
        "Improved recall at 10 by 11 percent.",
    ],
    ["3. Development areas", "Delegate more and grow junior engineers."],
]


@pytest.fixture
def docs(settings: Settings, clock: FixedClock) -> Container:
    return build_container(settings, clock, jobs=InlineJobRunner())


def test_headings_and_chunking_keep_provenance() -> None:
    assert detect_heading("2.1 Impact on the team")
    assert detect_heading("DEVELOPMENT AREAS")
    assert not detect_heading("This is an ordinary sentence that ends with a period.")
    pages = [
        ExtractedPage(1, "INTRODUCTION\n\n" + "Alpha sentence. " * 40),
        ExtractedPage(2, "2. Results\n\n" + "Beta sentence. " * 120),
    ]
    chunks = chunk_pages(pages, target=500, overlap=0)
    assert chunks[0].page_start == 1 and chunks[0].section == "INTRODUCTION"
    assert all(c.page_start == c.page_end for c in chunks)  # never spans pages
    assert any(c.page_start == 2 and c.section == "2. Results" for c in chunks)
    assert all(len(c.text) <= 600 for c in chunks)
    assert [c.seq for c in chunks] == list(range(len(chunks)))


def test_pdf_ingest_extracts_pages_and_dedupes(docs: Container, settings: Settings) -> None:
    pdf = make_pdf(REVIEW, title="Mid-year review 2026")
    r = docs.documents.ingest("review.pdf", pdf, kind="performance_report")
    assert not r.duplicate and r.document.title == "Mid-year review 2026"
    doc, chunks = docs.documents.get(r.document.id)
    assert doc.status.value == "ready" and doc.pages == 3 and doc.extractor_version
    assert any("benchmark" in str(c["text"]) and c["page_start"] == 2 for c in chunks)
    stored = settings.local_data_dir / doc.storage_path
    assert stored.read_bytes() == pdf
    assert not POSIX_MODES or oct(stored.stat().st_mode & 0o777) == "0o600"
    again = docs.documents.ingest("copy-of-review.pdf", pdf)
    assert again.duplicate and again.document.id == doc.id


def test_search_cites_document_and_page(docs: Container) -> None:
    docs.documents.ingest("review.pdf", make_pdf(REVIEW))
    hits = docs.documents.search("delegate junior")
    assert hits and hits[0].page_start == 3 and hits[0].document_title == "review"


def test_scanned_pdf_needs_ocr_and_corrupt_pdf_fails(docs: Container) -> None:
    scanned = docs.documents.ingest("scan.pdf", make_pdf([[], []])).document
    assert docs.documents.get(scanned.id)[0].status.value == "needs_ocr"
    broken = docs.documents.ingest("broken.pdf", b"%PDF-1.4\nthis is not really a pdf").document
    d = docs.documents.get(broken.id)[0]
    assert d.status.value == "failed" and d.error


def test_text_and_markdown_and_type_checks(docs: Container) -> None:
    md = (
        b"# Engineering levels\n\n## L4\n\nOwns features end to end.\n\n"
        b"## L5\n\nLeads cross-team projects.\n"
    )
    d = docs.documents.ingest("levels.md", md, kind="framework").document
    doc, chunks = docs.documents.get(d.id)
    assert doc.mime == "text/markdown" and doc.status.value == "ready" and chunks
    assert doc.title == "Engineering levels"  # first Markdown heading
    assert chunks[0]["section"] in ("Engineering levels", "L4")
    big = (
        b"# Levels\n\n## L4\n\n"
        + b"Owns features end to end. " * 6
        + b"\n\n## L5\n\n"
        + b"Leads projects. " * 6
    )
    d2 = docs.documents.ingest("levels2.md", big).document
    sections = [c["section"] for c in docs.documents.get(d2.id)[1]]
    assert "L4" in sections and "L5" in sections  # each heading starts its own citable chunk
    with pytest.raises(ValidationError):
        docs.documents.ingest("evil.exe", b"MZ\x90\x00\x03\x00\x00\x00binary")
    with pytest.raises(ValidationError):
        docs.documents.ingest("empty.txt", b"")
    with pytest.raises(ValidationError):
        docs.documents.ingest("x.txt", b"hello", kind="nonsense")


def test_reindex_delete_and_resume(docs: Container, settings: Settings) -> None:
    d = docs.documents.ingest("notes.txt", b"First page\fSecond page about evals").document
    assert docs.documents.get(d.id)[0].pages == 2
    assert docs.documents.reindex(d.id) == 1
    assert docs.documents.reindex(None, only_outdated=True) == 0  # already current
    path = settings.local_data_dir / docs.documents.get(d.id)[0].storage_path
    docs.documents.delete(d.id)
    assert not path.exists()
    assert docs.documents.search("evals") == []
    # a document left "queued" (e.g. crash) is picked up on restart
    with docs.uow() as uow:
        uow.conn.execute(
            "INSERT INTO documents (id, title, filename, mime, sha256, size_bytes, storage_path,"
            " status, created_at, updated_at) VALUES ('q', 'q', 'q.txt', 'text/plain', 'abc', 1,"
            " 'documents/ab/missing.txt', 'queued', '2026-01-01', '2026-01-01')"
        )
        uow.commit()
    assert docs.documents.resume_pending() == 1
    assert (
        docs.documents.get("q")[0].status.value == "failed"
    )  # file missing → recorded, not crashed


def test_store_blocks_path_escape(tmp_path: Path) -> None:
    store = DocumentStore(tmp_path)
    with pytest.raises(PermissionError):
        store.read("../secrets.txt")


def test_api_upload_detail_file_and_search(settings: Settings, clock: FixedClock) -> None:
    app = create_app(settings, clock)
    with TestClient(
        app,
        base_url="http://127.0.0.1",
        headers={"Authorization": f"Bearer {app.state.api_token}"},
    ) as client:
        pdf = make_pdf(REVIEW)
        r = client.post("/api/documents?filename=review.pdf&kind=performance_report", content=pdf)
        assert r.status_code == 202
        doc_id = r.json()["document"]["id"]
        client.app.state.container.documents.jobs.wait_idle()  # type: ignore[attr-defined]
        detail = client.get(f"/api/documents/{doc_id}").json()
        assert detail["status"] == "ready" and len(detail["chunks"]) >= 1
        f = client.get(f"/api/documents/{doc_id}/file")
        assert f.content == pdf and f.headers["content-type"] == "application/pdf"
        assert "sandbox" in f.headers["content-security-policy"]
        hits = client.get("/api/documents/search", params={"q": "recall"}).json()
        assert hits[0]["page_start"] == 2
        assert (
            client.post("/api/documents?filename=x.bin", content=b"\x00\x01\x02").status_code == 422
        )
