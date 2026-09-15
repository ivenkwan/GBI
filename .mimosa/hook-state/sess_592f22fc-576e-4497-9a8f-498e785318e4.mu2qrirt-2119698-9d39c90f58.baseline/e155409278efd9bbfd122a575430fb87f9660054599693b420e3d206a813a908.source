"""Report PDF export — dependency-free writer (Phase 19).

Renders a report dict (as returned by reports.get_report) into a valid PDF
using only the standard library: Helvetica text on A4 pages, wrapped
paragraphs, per-section headings/tables, and — when ``cairosvg`` is
importable — section charts rasterized to PNG and embedded as images
(PDF XObject with an alpha SMask; the PNG decoder is stdlib zlib plus
scanline unfiltering). Without cairosvg the chart slot renders a note; the
PDF itself always succeeds.

Text is encoded as WinAnsi (PDF's built-in Helvetica encoding); characters
outside it are replaced so the byte stream is always encodable.
"""

import zlib

_PAGE_W, _PAGE_H = 595.0, 842.0  # A4, points
_MARGIN = 50.0
_LINE_GAP = 4.0

# Approximate Helvetica advance widths (fraction of font size) for wrapping.
_CHAR_W_AVG = 0.5
_CHAR_W_NARROW = 0.28
_NARROW = set("iljtfI|.,;:'!()[]{}/\\ ")


def _to_winansi(text: str) -> str:
    """Replace characters PDF Helvetica cannot encode."""
    return text.encode("cp1252", errors="replace").decode("cp1252")


def _escape_pdf_string(text: str) -> str:
    return _to_winansi(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(text: str, size: float, max_width: float) -> list[str]:
    """Greedy word wrap using approximate Helvetica widths."""
    lines: list[str] = []
    for raw_line in text.split("\n"):
        words = raw_line.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            width = sum(_CHAR_W_NARROW if ch in _NARROW else _CHAR_W_AVG for ch in candidate) * size
            if current and width > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# PNG decoding (stdlib): 8-bit RGB/RGBA/gray, non-interlaced
# ---------------------------------------------------------------------------


class PNGError(ValueError):
    pass


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png(data: bytes) -> tuple[int, int, int, bytes]:
    """Decode a non-interlaced 8-bit PNG → (width, height, channels, raw).

    channels is 1 (gray/gray+alpha→gray), 3 (RGB), or 4 (RGBA). Raises
    PNGError for anything else (palette, 16-bit, interlaced).
    """
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise PNGError("not a PNG")

    pos = 8
    width = height = 0
    bit_depth = color_type = interlace = 0
    idat = bytearray()
    while pos < len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        chunk_type = data[pos + 4 : pos + 8]
        chunk = data[pos + 8 : pos + 8 + length]
        pos += 12 + length  # + CRC
        if chunk_type == b"IHDR":
            width = int.from_bytes(chunk[0:4], "big")
            height = int.from_bytes(chunk[4:8], "big")
            bit_depth = chunk[8]
            color_type = chunk[9]
            interlace = chunk[12]
        elif chunk_type == b"IDAT":
            idat.extend(chunk)
        elif chunk_type == b"IEND":
            break

    if bit_depth != 8 or interlace != 0:
        raise PNGError("only 8-bit non-interlaced PNG supported")
    if color_type == 0:
        channels = 1
    elif color_type == 2:
        channels = 3
    elif color_type == 4:
        channels = 2
    elif color_type == 6:
        channels = 4
    else:
        raise PNGError("palette PNG not supported")

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(stride * height)
    prev_row = bytearray(stride)
    p = 0
    for y in range(height):
        ftype = raw[p]
        p += 1
        row = bytearray(raw[p : p + stride])
        p += stride
        if ftype == 1:  # Sub
            for i in range(channels, stride):
                row[i] = (row[i] + row[i - channels]) & 255
        elif ftype == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 255
        elif ftype == 3:  # Average
            for i in range(stride):
                left = row[i - channels] if i >= channels else 0
                row[i] = (row[i] + ((left + prev_row[i]) >> 1)) & 255
        elif ftype == 4:  # Paeth
            for i in range(stride):
                left = row[i - channels] if i >= channels else 0
                upleft = prev_row[i - channels] if i >= channels else 0
                row[i] = (row[i] + _paeth(left, prev_row[i], upleft)) & 255
        out[y * stride : (y + 1) * stride] = row
        prev_row = row

    if channels == 2:
        # gray + alpha → keep gray (drop alpha)
        flat = bytes(out)
        return width, height, 1, bytes(flat[i] for i in range(0, len(flat), 2))
    return width, height, channels, bytes(out)


def _png_to_pdf_image(png_bytes: bytes) -> dict | None:
    """PNG bytes → PDF image object spec {w, h, rgb, alpha} (FlateDecode).

    None when the PNG can't be decoded (unsupported variant) — the caller
    falls back to a text note.
    """
    try:
        w, h, channels, raw = decode_png(png_bytes)
    except (PNGError, zlib.error, ValueError, IndexError):
        return None

    if channels == 4:
        rgb = bytearray(w * h * 3)
        alpha = bytearray(w * h)
        src = 0
        dst = 0
        for _ in range(w * h):
            rgb[dst : dst + 3] = raw[src : src + 3]
            alpha[_] = raw[src + 3]
            src += 4
            dst += 3
        return {"w": w, "h": h, "rgb": bytes(rgb), "alpha": bytes(alpha)}
    if channels == 3:
        return {"w": w, "h": h, "rgb": raw, "alpha": None}
    if channels == 1:
        return {"w": w, "h": h, "rgb": raw, "alpha": None}  # DeviceGray
    return None


def _svg_to_png(svg: str) -> bytes | None:
    """Rasterize SVG via cairosvg when available; None otherwise."""
    try:
        import cairosvg  # type: ignore[import-not-found]

        return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=900)
    except ImportError:
        return None
    except Exception:  # noqa: BLE001 — any rasterizer failure falls back to a note
        return None


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------


class _PdfBuilder:
    """Minimal PDF writer: pages of text + images, Helvetica fonts."""

    def __init__(self) -> None:
        self.objects: list[bytes] = []  # 1-indexed object bodies
        self.pages: list[list[bytes]] = []  # content streams
        self.images: list[dict] = []  # image specs, one per draw call

    def _add_object(self, body: bytes) -> int:
        self.objects.append(body)
        return len(self.objects)

    def new_page(self) -> None:
        self.pages.append([])

    def text(
        self, x: float, y: float, size: float, text: str, bold: bool = False, gray: float = 0.0
    ) -> None:
        font = "/F2" if bold else "/F1"
        self.pages[-1].append(
            f"BT {gray} {gray} {gray} rg {font} {size} Tf {x:.1f} {y:.1f} Td ({_escape_pdf_string(text)}) Tj ET".encode(
                "cp1252", errors="replace"
            )
        )

    def image(self, png: bytes, x: float, y: float, w: float, h: float) -> bool:
        """Draw a PNG at (x, y) sized w×h. False when not renderable."""
        spec = _png_to_pdf_image(png)
        if spec is None:
            return False
        idx = len(self.images)
        self.images.append(spec)
        self.pages[-1].append(f"q {w:.1f} 0 0 {h:.1f} {x:.1f} {y:.1f} cm /Im{idx} Do Q".encode())
        return True

    def line(self, x1: float, y1: float, x2: float, y2: float, gray: float = 0.8) -> None:
        self.pages[-1].append(
            f"{gray} {gray} {gray} RG 0.7 w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S".encode()
        )

    def build(self) -> bytes:
        font1 = self._add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        font2 = self._add_object(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")

        image_obj_ids: list[int] = []
        for spec in self.images:
            channels = 1 if len(spec["rgb"]) == spec["w"] * spec["h"] else 3
            colorspace = b"/DeviceGray" if channels == 1 else b"/DeviceRGB"

            alpha_id = None
            if spec["alpha"] is not None:
                alpha_id = self._add_object(
                    b"<< /Type /XObject /Subtype /Image /Width %d /Height %d "
                    b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode "
                    b"/Length %d >>\nstream\n"
                    % (spec["w"], spec["h"], len(spec["alpha"]))
                    + zlib.compress(spec["alpha"])
                    + b"\nendstream"
                )

            smask = b" /SMask %d 0 R" % alpha_id if alpha_id else b""
            rgb_id = self._add_object(
                b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace %s "
                b"/BitsPerComponent 8 /Filter /FlateDecode"
                % (spec["w"], spec["h"], colorspace)
                + smask
                + b" /Length %d >>\nstream\n" % len(spec["rgb"])
                + zlib.compress(spec["rgb"])
                + b"\nendstream"
            )
            image_obj_ids.append(rgb_id)

        page_ids = []
        for content_parts in self.pages:
            content = b"\n".join(content_parts)
            content_id = self._add_object(
                b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
            )
            xobjects = b"".join(
                b"/Im%d %d 0 R " % (idx, rgb_id) for idx, rgb_id in enumerate(image_obj_ids)
            )
            resources = (
                b"<< /Font << /F1 %d 0 R /F2 %d 0 R >>" % (font1, font2)
                + (b" /XObject << %s >>" % xobjects if xobjects else b"")
                + b" >>"
            )
            page_id = self._add_object(
                b"<< /Type /Page /Parent PARENT 0 R /MediaBox [0 0 %.1f %.1f] "
                b"/Resources %s /Contents %d 0 R >>" % (_PAGE_W, _PAGE_H, resources, content_id)
            )
            page_ids.append(page_id)

        pages_id = self._add_object(
            b"<< /Type /Pages /Kids [%s] /Count %d >>"
            % (b" ".join(b"%d 0 R" % p for p in page_ids), len(page_ids))
        )
        catalog_id = self._add_object(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)

        # Patch the PARENT placeholder now that pages_id is known.
        for i, body in enumerate(self.objects, start=1):
            if b"/Parent PARENT 0 R" in body:
                self.objects[i - 1] = body.replace(
                    b"/Parent PARENT 0 R", b"/Parent %d 0 R" % pages_id
                )

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, body in enumerate(self.objects, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
        xref_pos = len(out)
        out += b"xref\n0 %d\n" % (len(self.objects) + 1)
        out += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            out += b"%010d 00000 n \n" % off
        out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            len(self.objects) + 1,
            catalog_id,
            xref_pos,
        )
        return bytes(out)


def render_report_pdf(report: dict) -> bytes:
    """Render a report dict to PDF bytes. Never raises on content — only on
    programming errors."""
    b = _PdfBuilder()
    b.new_page()
    y = _PAGE_H - _MARGIN

    def ensure(space: float) -> None:
        nonlocal y
        if y - space < _MARGIN:
            b.new_page()
            y = _PAGE_H - _MARGIN

    def para(text: str, size: float = 10, bold: bool = False, gray: float = 0.1, gap: float = 6.0):
        nonlocal y
        for line in _wrap(text or "", size, _PAGE_W - 2 * _MARGIN):
            ensure(size + _LINE_GAP)
            y -= size + _LINE_GAP
            b.text(_MARGIN, y, size, line, bold=bold, gray=gray)
        y -= gap

    # Title block
    para(report.get("title", "Report"), size=20, bold=True, gray=0.0, gap=2)
    para(
        f"Generated {report.get('created_at', '')} · {len(report.get('sections', []))} sections",
        size=9,
        gray=0.45,
        gap=10,
    )
    b.line(_MARGIN, y, _PAGE_W - _MARGIN, y)
    y -= 14

    if report.get("summary"):
        para(report["summary"], size=10, gray=0.25, gap=10)

    for section in report.get("sections", []):
        ensure(90)
        para(
            section.get("section_title", section.get("metric_name", "Section")),
            size=13,
            bold=True,
            gap=2,
        )
        total = section.get("data_total")
        meta = f"{section.get('metric_name', '')}"
        if total is not None:
            meta += f" · total {total:,.0f}"
        meta += f" · {section.get('row_count', 0)} rows"
        para(meta, size=9, gray=0.45, gap=6)

        svg = section.get("chart_svg")
        drawn = False
        if svg:
            png = _svg_to_png(svg)
            if png is not None:
                ensure(240)
                y -= 230
                drawn = b.image(png, _MARGIN, y, _PAGE_W - 2 * _MARGIN, 225)
                if not drawn:
                    y += 230
        if not drawn:
            para("[chart image unavailable in this export]", size=9, gray=0.6, gap=6)

        if section.get("narrative"):
            para(section["narrative"], size=10, gray=0.2, gap=12)
        else:
            y -= 8

    for warning in report.get("warnings", []):
        para(f"⚠ {warning}", size=8, gray=0.5, gap=2)

    return b.build()
