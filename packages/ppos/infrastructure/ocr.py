"""OCR for scanned PDFs with Tesseract, when it is installed on this machine.

Optional: nothing is bundled and nothing leaves the machine. Pages are
rendered with ``pdftoppm`` (Poppler) and read with ``tesseract``; both are
called with argument lists (no shell), in a private temporary folder, with a
time limit per page.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ppos.domain.documents import ExtractedPage
from ppos.shared.errors import ValidationError

DPI = 300
PAGE_TIMEOUT_S = 120
MAX_OCR_PAGES = 300
_LANG = re.compile(r"^[a-z_]{3,8}(\+[a-z_]{3,8})*$")


def ocr_tools() -> tuple[str, str] | None:
    """Paths to (pdftoppm, tesseract), or None when either is missing."""
    pdftoppm, tesseract = shutil.which("pdftoppm"), shutil.which("tesseract")
    return (pdftoppm, tesseract) if pdftoppm and tesseract else None


def ocr_version() -> str:
    tools = ocr_tools()
    if tools is None:
        return ""
    try:
        out = subprocess.run(  # noqa: S603 - fixed argument list
            [tools[1], "--version"], capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return "tesseract"
    first = (out.stdout or out.stderr).splitlines()[:1]
    return first[0].strip().replace(" ", "-") if first else "tesseract"


def ocr_pdf(data: bytes, lang: str = "eng") -> list[ExtractedPage]:
    """Text of every page of a scanned PDF, page numbers kept."""
    tools = ocr_tools()
    if tools is None:
        raise ValidationError("OCR needs Tesseract and Poppler (pdftoppm) on this machine")
    if not _LANG.match(lang):
        raise ValidationError(f"invalid OCR language {lang!r} (e.g. eng or eng+deu)")
    pdftoppm, tesseract = tools
    with tempfile.TemporaryDirectory(prefix="ppos-ocr-") as tmp:
        Path(tmp).chmod(0o700)
        src = Path(tmp) / "in.pdf"
        src.write_bytes(data)
        _run(
            [pdftoppm, "-r", str(DPI), "-gray", "-png", "-l", str(MAX_OCR_PAGES), str(src),
             str(Path(tmp) / "p")],
            PAGE_TIMEOUT_S * 4,
        )  # fmt: skip
        images = sorted(Path(tmp).glob("p-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
        if not images:
            raise ValidationError("could not render the PDF pages for OCR")
        pages = []
        for i, img in enumerate(images, start=1):
            text = _run([tesseract, str(img), "stdout", "-l", lang, "--psm", "3"], PAGE_TIMEOUT_S)
            pages.append(ExtractedPage(i, text.replace("\r", "").replace("\f", "").strip()))
        return pages


def _run(args: list[str], timeout: int) -> str:
    try:
        out = subprocess.run(  # noqa: S603 - fixed argument list, no shell
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise ValidationError("OCR took too long and was stopped") from exc
    except OSError as exc:
        raise ValidationError(f"could not run {Path(args[0]).name}: {exc}") from exc
    if out.returncode != 0:
        detail = (out.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        raise ValidationError(f"{Path(args[0]).name} failed: {detail[0][:200]}")
    return out.stdout
