"""Index a scanned book: printed page number, chapter running head, headings.

Works straight from the OCR cache, so it can run while OCR is still going.
Outputs JSON per page so later stages can map book page -> PDF page and find
where each chapter starts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).parent))
from pdf2md import Box, assemble, load_boxes  # noqa: E402

FOOTER_RE = re.compile(r"^\s*(CHAPTER|APPENDIX)\s*(?P<num>[0-9A-Z]+)\s*\|?\s*(?P<title>.*)$", re.I)
PNUM_RE = re.compile(r"^\s*(?P<num>\d{1,3})\s*$")

# Running heads at the bottom of each page: "CHAPTER 1 | CHARACTER CREATION".
CHAPTER_TITLES = {
    "1": "Character Creation",
    "2": "Giants in Play",
    "3": "Giant Adventures",
    "4": "Giant Enclaves",
    "5": "Giant Treasures",
    "6": "Bestiary",
}


def page_record(pno: int, img_dir: Path, ocr_dir: Path) -> dict:
    img = img_dir / f"{pno:03d}.jpg"
    ocr = ocr_dir / f"{pno:03d}.json"
    if not ocr.exists():
        return {"pdf_page": pno, "status": "no-ocr"}
    pix = pymupdf.Pixmap(str(img))
    w, h = float(pix.width), float(pix.height)
    boxes = load_boxes(ocr)
    text = assemble(boxes, w, h)

    bottom = [b for b in boxes if b.y0 > h * 0.93]
    footer = " ".join(b.text for b in sorted(bottom, key=lambda b: b.x0)).strip()
    printed = None
    for b in bottom:
        m = PNUM_RE.match(b.text)
        if m:
            printed = int(m.group("num"))
    chapter = None
    m = FOOTER_RE.search(footer)
    if m:
        chapter = m.group("num").upper()
        if not re.fullmatch(r"\d+", chapter) or chapter not in CHAPTER_TITLES:
            pass

    headings = [b.text for b in boxes if b.text.isupper() and len(b.text) > 3][:12]
    return {
        "pdf_page": pno,
        "printed_page": printed,
        "footer": footer[:120],
        "chapter": chapter,
        "headings": headings,
        "chars": len(text),
    }


def main() -> None:
    base = Path(sys.argv[1])
    out = Path(sys.argv[2])
    img_dir, ocr_dir, md_dir = base / "images", base / "ocr", base / "pages"
    total = len(list(img_dir.glob("*.jpg")))
    rows = [page_record(p, img_dir, ocr_dir) for p in range(1, total + 1)]
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    # Offset check: printed page vs pdf page is constant once body pages start.
    offsets: dict[int, int] = {}
    for row in rows:
        if row.get("printed_page"):
            delta = row["pdf_page"] - row["printed_page"]
            offsets[delta] = offsets.get(delta, 0) + 1
    print("pages", total, "with printed number", sum(1 for r in rows if r.get("printed_page")))
    print("offset histogram", dict(sorted(offsets.items(), key=lambda kv: -kv[1])[:5]))
    chapters = [(r["pdf_page"], r["chapter"]) for r in rows if r.get("chapter")]
    first: dict[str, int] = {}
    for pdf_page, chap in chapters:
        first.setdefault(str(chap), pdf_page)
    print("first pdf page per chapter", first)


if __name__ == "__main__":
    main()
