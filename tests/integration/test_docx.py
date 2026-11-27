import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from ppos.bootstrap import Container, build_container
from ppos.domain.documents import DocStatus
from ppos.infrastructure.config import Settings
from ppos.infrastructure.docx import DOCX_MIME, docx_pages, docx_title
from ppos.infrastructure.extract import sniff
from ppos.infrastructure.jobs import InlineJobRunner
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError
from tests.docxgen import PAGE_BREAK, docx, para, table

REVIEW = (
    para("Mid-year review", "Title")
    + para("Achievements", "Heading1")
    + para("Led the hybrid retrieval benchmark adopted by two teams.")
    + para("Mentored Ana", numbered=True)
    + PAGE_BREAK
    + para("Development areas", "Heading2")
    + para("Delegate more & grow junior engineers.")
    + table([["Goal", "Status"], ["Cut build time", "Done"]])
)


@pytest.fixture
def docs(settings: Settings, clock: FixedClock) -> Container:
    return build_container(settings, clock, jobs=InlineJobRunner())


def test_docx_text_keeps_structure_and_pages() -> None:
    data = docx(REVIEW, title="H1 review 2026")
    assert sniff("review.docx", data) == DOCX_MIME
    assert sniff("renamed.bin", data) == DOCX_MIME  # by content, not by name
    p1, p2 = docx_pages(data)
    assert p1.number == 1 and p1.text.startswith("# Mid-year review\n\n# Achievements")
    assert "- Mentored Ana" in p1.text and "Development" not in p1.text
    assert p2.text.startswith("## Development areas")
    assert "Delegate more & grow junior engineers." in p2.text
    assert "Goal | Status\nCut build time | Done" in p2.text
    assert docx_title(data) == "H1 review 2026"


def test_docx_unsafe_or_wrong_input_is_refused() -> None:
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>&a;</w:t></w:r></w:p></w:body></w:document>"
    )
    with pytest.raises(ValidationError, match="DOCTYPE"):
        docx_pages(docx("", document_xml=bomb))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "not word")
    with pytest.raises(ValidationError, match="unsupported"):
        sniff("x.docx", buf.getvalue())
    with pytest.raises(ValidationError, match=r"\.doc files"):
        sniff("old.doc", b"\xd0\xcf\x11\xe0\x00\x00binary")


def test_docx_ingest_is_searchable_with_provenance(docs: Container) -> None:
    r = docs.documents.ingest(
        "h1.docx", docx(REVIEW, title="H1 review 2026"), kind="performance_report"
    )
    doc, chunks = docs.documents.get(r.document.id)
    assert doc.mime == DOCX_MIME and doc.title == "H1 review 2026"
    assert doc.status == DocStatus.READY and doc.pages == 2
    assert doc.storage_path.endswith(".docx")
    assert any(ch["page_start"] == 2 and ch["section"] == "Development areas" for ch in chunks)
    [hit] = docs.documents.search("delegate junior")
    assert hit.page_start == 2 and hit.document_title == "H1 review 2026"


def test_docx_upload_api(client: TestClient) -> None:
    data = docx(para("Quarterly plan", "Heading1") + para("Ship the eval harness."))
    r = client.post("/api/documents?filename=plan.docx", content=data)
    assert r.status_code == 202, r.text
    doc = r.json()["document"]
    assert doc["mime"] == DOCX_MIME and doc["title"] == "Quarterly plan"
    client.app.state.container.documents.jobs.wait_idle()  # type: ignore[attr-defined]
    assert client.get(f"/api/documents/{doc['id']}").json()["status"] == "ready"
    f = client.get(f"/api/documents/{doc['id']}/file")
    assert f.headers["content-type"].startswith(DOCX_MIME)
