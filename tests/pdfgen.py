"""Build small but valid PDFs for tests (text layer via Helvetica)."""

from __future__ import annotations


def make_pdf(pages: list[list[str]], title: str | None = None) -> bytes:
    objs: list[bytes] = []
    n_pages = len(pages)
    font_id = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    for i, lines in enumerate(pages):
        content_id = 4 + 2 * i
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_id} 0 R"
            f" /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        ops = ["BT", "/F1 11 Tf", "14 TL", "72 720 Td"]
        for line in lines:
            esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            ops.append(f"({esc}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode() if lines else b""
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    info_id = None
    if title:
        objs.append(f"<< /Title ({title}) >>".encode())
        info_id = len(objs)
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    trailer = (
        f"<< /Size {len(objs) + 1} /Root 1 0 R"
        + (f" /Info {info_id} 0 R" if info_id else "")
        + " >>"
    )
    out += f"trailer\n{trailer}\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def make_scanned_pdf(lines: list[str], dpi: int = 150) -> bytes:
    """An image-only PDF (no text layer), like a scan: renders ``make_pdf`` with
    pdftoppm and embeds the bitmap. Requires Poppler's pdftoppm."""
    import subprocess
    import tempfile
    import zlib
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "t.pdf"
        src.write_bytes(make_pdf([lines]))
        subprocess.run(
            ["pdftoppm", "-r", str(dpi), "-gray", "-singlefile", str(src), str(Path(tmp) / "img")],
            check=True,
        )
        raw = (Path(tmp) / "img.pgm").read_bytes()
    header = raw.split(maxsplit=4)  # P5 width height maxval data
    width, height, pixels = int(header[1]), int(header[2]), header[4]
    img = zlib.compress(pixels[: width * height])
    w_pt, h_pt = width * 72 / dpi, height * 72 / dpi
    content = f"q {w_pt:.2f} 0 0 {h_pt:.2f} 0 0 cm /Im0 Do Q".encode()
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w_pt:.2f} {h_pt:.2f}] /Contents 4 0 R"
        " /Resources << /XObject << /Im0 5 0 R >> >> >>".encode(),
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace"
        f" /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode /Length {len(img)} >>\nstream\n"
        .encode() + img + b"\nendstream",
    ]  # fmt: skip
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def make_image_pdf(
    stream: bytes,
    width: int,
    height: int,
    filter_: str | None = "/FlateDecode",
    colorspace: str = "/DeviceGray",
    bpc: int = 8,
    pages: int = 1,
) -> bytes:
    """A PDF whose pages each show one image XObject (a synthetic "scan")."""
    objs: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 3 * i} 0 R" for i in range(pages))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    filt = f" /Filter {filter_}" if filter_ else ""
    for i in range(pages):
        content, image = 4 + 3 * i, 5 + 3 * i
        objs.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] /Contents"
            f" {content} 0 R /Resources << /XObject << /Im0 {image} 0 R >> >> >>".encode()
        )
        body = f"q {width} 0 0 {height} 0 0 cm /Im0 Do Q".encode()
        objs.append(b"<< /Length %d >>\nstream\n" % len(body) + body + b"\nendstream")
        objs.append(
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace"
            f" {colorspace} /BitsPerComponent {bpc}{filt} /Length {len(stream)} >>\nstream\n"
            .encode() + stream + b"\nendstream"
        )  # fmt: skip
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
