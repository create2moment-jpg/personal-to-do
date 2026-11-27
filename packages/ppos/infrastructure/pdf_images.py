"""The scanned image on each PDF page, as JPEG or PNG — no image libraries needed.

Scanners put one picture per page. JPEG pictures (DCTDecode, by far the most
common for grey and colour scans) are passed through untouched; uncompressed or
Flate-compressed grey/RGB pictures are wrapped as PNG with the standard library.
Fax-style black-and-white encodings (CCITT, JBIG2) and JPEG 2000 need an image
decoder and are reported as unsupported.
"""

from __future__ import annotations

import io
import struct
import zlib
from dataclasses import dataclass
from typing import Any

from ppos.shared.errors import ValidationError

MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_PAGES = 300
UNSUPPORTED = {"/CCITTFaxDecode", "/JBIG2Decode", "/JPXDecode"}


@dataclass(frozen=True)
class PageImage:
    page: int
    mime: str  # image/jpeg | image/png
    data: bytes


def png(width: int, height: int, pixels: bytes, channels: int, bits: int = 8) -> bytes:
    """Encode raw rows (no filter bytes) as a PNG: 1/3 channels, 1 or 8 bits."""
    color_type = {1: 0, 3: 2}[channels]
    row = (width * channels * bits + 7) // 8
    if len(pixels) < row * height:
        raise ValidationError("the scanned image is shorter than its declared size")
    raw = b"".join(b"\x00" + pixels[y * row : (y + 1) * row] for y in range(height))

    def chunk(tag: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body))

    header = struct.pack(">IIBBBBB", width, height, bits, color_type, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def _filters(obj: Any) -> list[str]:
    f = obj.get("/Filter")
    if f is None:
        return []
    return [str(x) for x in f] if isinstance(f, list) else [str(f)]


def _image(obj: Any) -> tuple[str, bytes]:
    filters = _filters(obj)
    if any(f in UNSUPPORTED for f in filters):
        name = next(f for f in filters if f in UNSUPPORTED).lstrip("/")
        raise ValidationError(f"scanned pages use {name} images, which need an image decoder")
    data = obj.get_data()
    if filters and filters[-1] == "/DCTDecode":
        return "image/jpeg", data
    width, height = int(obj["/Width"]), int(obj["/Height"])
    bits = int(obj.get("/BitsPerComponent", 8))
    space = obj.get("/ColorSpace")
    space = str(space) if not isinstance(space, list) else str(space[0])
    channels = {"/DeviceGray": 1, "/CalGray": 1, "/DeviceRGB": 3, "/CalRGB": 3}.get(space)
    if channels is None or bits not in (1, 8) or (bits == 1 and channels != 1):
        raise ValidationError(
            f"scanned pages use an unsupported image format ({space}, {bits} bit)"
        )
    return "image/png", png(width, height, data, channels, bits)


def page_images(data: bytes) -> list[PageImage]:
    """The largest picture on each page (pages without one are skipped)."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # pypdf raises many types on damaged files
        raise ValidationError(f"could not read the PDF: {exc}") from exc
    out: list[PageImage] = []
    problem: ValidationError | None = None
    for number, page in enumerate(reader.pages[:MAX_PAGES], start=1):
        res = page.get("/Resources")
        xobjects = res.get_object().get("/XObject") if res is not None else None
        if xobjects is None:
            continue
        candidates = []
        for ref in xobjects.get_object().values():
            obj = ref.get_object()
            if obj.get("/Subtype") == "/Image":
                candidates.append((int(obj.get("/Width", 0)) * int(obj.get("/Height", 0)), obj))
        if not candidates:
            continue
        obj = max(candidates, key=lambda c: c[0])[1]
        try:
            mime, img = _image(obj)
        except ValidationError as exc:
            problem = exc
            continue
        if len(img) > MAX_IMAGE_BYTES:
            problem = ValidationError("a scanned page is too large to send to the model")
            continue
        out.append(PageImage(number, mime, img))
    if not out and problem is not None:
        raise problem
    return out
