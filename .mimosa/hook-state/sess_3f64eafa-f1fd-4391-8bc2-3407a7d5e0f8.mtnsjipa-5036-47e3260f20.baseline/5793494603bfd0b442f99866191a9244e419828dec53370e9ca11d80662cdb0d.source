"""GenBI codebase → single PDF with TOC, bookmarks, and per-file sections.

Run:  uv run --with reportlab python gen_codebook.py
Out:  GBI-codebase.pdf (repo root)
"""

import datetime
import subprocess
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

REPO = Path(__file__).resolve().parent
OUT = REPO / "GBI-codebase.pdf"

# --- fonts -------------------------------------------------------------------
MONO = "Consolas"
try:
    pdfmetrics.registerFont(TTFont(MONO, r"C:\Windows\Fonts\consola.ttf"))
    pdfmetrics.registerFont(TTFont(MONO + "-Bold", r"C:\Windows\Fonts\consolab.ttf"))
    addMapping(MONO, 0, 0, MONO)
    addMapping(MONO, 1, 0, MONO + "-Bold")
except Exception:
    MONO = "Courier"  # fallback: built-in, no Unicode but never missing
SANS = "Helvetica"

# --- file collection ---------------------------------------------------------
EXCLUDE_DIRS = (".mimosa", ".zcode", ".cubestore", "node_modules", ".next", ".git", ".venv")
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".ttf",
              ".eot", ".pdf", ".zip", ".gz", ".exe", ".dll", ".bin", ".pyc", ".lock~"}


def collect_files():
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    files = []
    for rel in out:
        p = Path(rel)
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in BINARY_EXT:
            continue
        full = REPO / p
        if not full.is_file():
            continue
        try:
            text = full.read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        except OSError:
            continue
        files.append((rel.replace("\\", "/"), text))
    # group by top-level path for a readable order
    files.sort(key=lambda t: t[0].lower())
    return files


# --- styles ------------------------------------------------------------------
styles = getSampleStyleSheet()
h1 = ParagraphStyle("H1", parent=styles["Title"], fontName=SANS, fontSize=22, spaceAfter=6)
sub = ParagraphStyle("Sub", parent=styles["Normal"], fontName=SANS, fontSize=10,
                     textColor="#555555", leading=14)
fileh = ParagraphStyle("FileH", fontName=SANS, fontSize=11, spaceBefore=10,
                       spaceAfter=4, leading=14, textColor="#1a1a2e")
meta = ParagraphStyle("Meta", fontName=SANS, fontSize=7.5, textColor="#888888",
                      spaceAfter=6)
code = ParagraphStyle(
    "Code", fontName=MONO, fontSize=5.6, leading=7.0,
)
toc_h = ParagraphStyle("TocH", parent=styles["Heading1"], fontName=SANS, fontSize=16)

SESSION_TAG = f"GenBI session {datetime.datetime.now():%Y-%m-%d %H:%M}"


def after_flowable(self, flowable):
    """Notify TOC + add PDF bookmark/outline for each file heading."""
    if isinstance(flowable, Paragraph) and flowable.style.name == "FileH":
        text = flowable.getPlainText()
        key = f"h-{abs(hash(text)) & 0xFFFFFF:x}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=0, closed=False)
        self.notify("TOCEntry", (0, text, self.page, key))


class CodebookDoc(BaseDocTemplate):
    afterFlowable = after_flowable


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(SANS, 7)
    canvas.setFillColorRGB(0.45, 0.45, 0.45)
    canvas.drawString(18 * mm, 289 * mm, SESSION_TAG)
    canvas.drawRightString(192 * mm, 289 * mm, "GenBI codebase export")
    canvas.setFont(SANS, 8)
    canvas.drawCentredString(105 * mm, 10 * mm, f"— {doc.page} —")
    canvas.restoreState()


def code_block(text, rel):
    """Preformatted with a light filename gutter via line numbers."""
    lines = text.splitlines() or [""]
    numbered = []
    for i, ln in enumerate(lines, 1):
        # hard-wrap very long lines at 150 chars (lockfiles, minified blobs)
        while len(ln) > 150:
            numbered.append(f"{i:>5}│ {ln[:150]}")
            ln = ln[150:]
        numbered.append(f"{i:>5}│ {ln}")
    body = "\n".join(numbered)
    if MONO == "Courier":
        # Courier lacks unicode: replace common non-ascii glyphs
        body = (body.replace("─", "-").replace("│", "|").replace("→", "->")
                    .replace("·", ".").replace("✅", "[OK]").replace("❌", "[X]")
                    .replace("⚠", "[!]").replace("…", "...").replace("—", "-")
                    .replace("'", "'").replace('"', '"').replace("", "'"))
        body = body.encode("ascii", errors="replace").decode()
    return Preformatted(body, code, maxLineLength=None)


def main():
    files = collect_files()
    total_lines = sum(len(t.splitlines()) for _, t in files)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                            capture_output=True, text=True).stdout.strip()

    doc = CodebookDoc(
        str(OUT), pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="GenBI — Codebase Export",
        author=SESSION_TAG,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=header_footer)])

    story = []
    # --- cover / session header ---
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("GenBI — Generative BI Platform", h1))
    story.append(Paragraph("Complete codebase export", sub))
    story.append(Spacer(1, 18 * mm))
    story.append(Paragraph(f"Session: {SESSION_TAG}", sub))
    story.append(Paragraph(f"Git commit: {commit}", sub))
    story.append(Paragraph(f"Files: {len(files)}&nbsp;&nbsp;·&nbsp;&nbsp;Lines: {total_lines:,}", sub))
    story.append(Paragraph("Index: every filename below is a link; PDF outline mirrors the TOC.", sub))
    story.append(PageBreak())

    # --- TOC ---
    story.append(Paragraph("Table of Contents", toc_h))
    story.append(Spacer(1, 4 * mm))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle(
        "TOC0", fontName=MONO if MONO != "Courier" else SANS, fontSize=7.5,
        leading=10.5, leftIndent=4,
    )]
    story.append(toc)
    story.append(PageBreak())

    # --- files ---
    for rel, text in files:
        n = len(text.splitlines())
        story.append(Paragraph(rel, fileh))
        story.append(Paragraph(f"{n} lines · {len(text.encode('utf-8'))/1024:.1f} KB", meta))
        story.append(code_block(text, rel))
        story.append(PageBreak())

    doc.multiBuild(story)
    print(f"wrote {OUT} ({OUT.stat().st_size/1024/1024:.1f} MB, {len(files)} files, {total_lines:,} lines)")


if __name__ == "__main__":
    sys.exit(main())
