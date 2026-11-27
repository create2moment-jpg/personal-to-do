import importlib.util
import struct
import threading
import zlib
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import ppos.bootstrap
from ppos.ai.runtime import LLMConfig
from ppos.bootstrap import Container, build_container
from ppos.domain.documents import DocStatus
from ppos.infrastructure.config import Settings
from ppos.infrastructure.jobs import InlineJobRunner
from ppos.infrastructure.pdf_images import page_images, png
from ppos.infrastructure.vision_ocr import clean_transcript
from ppos.shared.clock import FixedClock
from ppos.shared.errors import ValidationError
from tests.pdfgen import make_image_pdf

_spec = importlib.util.spec_from_file_location(
    "fake_llm", Path(__file__).parents[2] / "scripts" / "fake_llm.py"
)
assert _spec and _spec.loader
fake_llm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_llm)

W, H = 40, 20
GRAY = bytes((x * 6) % 256 for x in range(W * H))
# smallest useful JPEG header bytes: the model receives the file untouched
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


class Quiet(fake_llm.Handler):  # type: ignore[name-defined, misc]
    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def server() -> Iterator[str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


@pytest.fixture
def docs(settings: Settings, clock: FixedClock, monkeypatch: pytest.MonkeyPatch) -> Container:
    monkeypatch.setattr(ppos.bootstrap, "ocr_tools", lambda: None)  # a laptop without Tesseract
    return build_container(settings, clock, jobs=InlineJobRunner())


def test_png_encoder_round_trips() -> None:
    data = png(W, H, GRAY, 1)
    assert data.startswith(b"\x89PNG") and struct.unpack(">II", data[16:24]) == (W, H)
    idat = data[data.index(b"IDAT") + 4 : data.index(b"IEND") - 8]
    rows = zlib.decompress(idat)
    assert rows[0] == 0 and rows[1 : W + 1] == GRAY[:W]
    with pytest.raises(ValidationError):
        png(W, H, GRAY[:10], 1)


def test_page_images_from_flate_jpeg_and_unsupported() -> None:
    [img] = page_images(make_image_pdf(zlib.compress(GRAY), W, H))
    assert img.page == 1 and img.mime == "image/png"
    rgb = bytes(range(256)) * ((W * H * 3) // 256 + 1)
    [c] = page_images(
        make_image_pdf(zlib.compress(rgb[: W * H * 3]), W, H, colorspace="/DeviceRGB")
    )
    assert c.mime == "image/png" and c.data[25] == 2  # PNG colour type RGB
    [j] = page_images(make_image_pdf(JPEG, W, H, filter_="/DCTDecode", pages=1))
    assert j.mime == "image/jpeg" and j.data == JPEG
    with pytest.raises(ValidationError, match="CCITTFaxDecode"):
        page_images(make_image_pdf(b"\x00" * 10, W, H, filter_="/CCITTFaxDecode", bpc=1))


def test_clean_transcript() -> None:
    assert clean_transcript("```\nA\nB\n```") == "A\nB"
    assert clean_transcript("<think>hm</think>\nText") == "Text"


def test_scan_without_ai_or_tesseract_explains_both_options(docs: Container) -> None:
    d = docs.documents.ingest("scan.pdf", make_image_pdf(zlib.compress(GRAY), W, H)).document
    d, _ = docs.documents.get(d.id)
    assert d.status == DocStatus.NEEDS_OCR
    assert "understands images" in (d.error or "") and "Tesseract" in (d.error or "")


def test_local_vision_model_reads_the_scan(docs: Container, server: str) -> None:
    docs.ai.apply(LLMConfig(enabled=True, base_url=server))
    scan = make_image_pdf(zlib.compress(GRAY), W, H, pages=2)
    d = docs.documents.ingest("scan.pdf", scan).document
    d, chunks = docs.documents.get(d.id)
    assert d.status == DocStatus.READY, d.error
    assert d.extractor_version and d.extractor_version.endswith("+ocr(vision-fake-llm)")
    text = " ".join(str(c["text"]) for c in chunks)
    assert f"QUARTERLY REVIEW (PNG {W}x{H})" in text and "```" not in text
    [hit] = docs.documents.search("delegate junior")
    assert hit.page_start in (1, 2)


def test_jpeg_scan_is_sent_untouched(docs: Container, server: str) -> None:
    docs.ai.apply(LLMConfig(enabled=True, base_url=server))
    d = docs.documents.ingest("j.pdf", make_image_pdf(JPEG, W, H, filter_="/DCTDecode")).document
    _, chunks = docs.documents.get(d.id)
    assert "QUARTERLY REVIEW (JPEG)" in str(chunks[0]["text"])


def test_model_server_down_fails_with_reason(docs: Container) -> None:
    docs.ai.apply(LLMConfig(enabled=True, base_url="http://127.0.0.1:9/v1", model="m"))
    d = docs.documents.ingest("scan.pdf", make_image_pdf(zlib.compress(GRAY), W, H)).document
    d, _ = docs.documents.get(d.id)
    assert d.status == DocStatus.FAILED and "cannot reach" in (d.error or "")
