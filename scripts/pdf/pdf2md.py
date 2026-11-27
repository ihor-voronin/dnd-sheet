"""PDF (scanned book) -> per-page Markdown via OCR.

Stages, each cached on disk so the run is resumable:

  1. images/<page>.jpg  - the embedded page image, copied losslessly
  2. ocr/<page>.json    - OCR boxes [x0, y0, x1, y1, text, score]
  3. pages/<page>.md    - column-aware reading order with paragraph joining

The book has no text layer at all (each page is one 300 dpi scan), so the text
has to come from OCR. Run:

    python scripts/pdf/pdf2md.py "<book.pdf>" content/raw/<source>-pdf
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import xycut


@dataclass
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    score: float

    @property
    def h(self) -> float:
        return self.y1 - self.y0


def digest(engine, img: Path, dest: Path) -> int:
    """OCR one page image and cache the raw boxes as JSON."""
    result, _ = engine(str(img))
    boxes = []
    for item in result or []:
        pts, text, score = item[0], item[1], item[2]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        boxes.append([min(xs), min(ys), max(xs), max(ys), text, float(score)])
    dest.write_text(json.dumps(boxes, ensure_ascii=False), encoding="utf-8")
    return len(boxes)


def load_boxes(path: Path) -> list[Box]:
    return [Box(*b) for b in json.loads(path.read_text(encoding="utf-8"))]


def assemble(boxes: list[Box], width: float, height: float) -> str:
    """Reading order via recursive XY-cut, then paragraph joining."""
    if not boxes:
        return ""
    lines = [xycut.Line(b.x0, b.y0, b.x1, b.y1, b.text, b.score) for b in boxes]
    del height
    return "\n\n".join(xycut.blocks_to_markdown(lines, width))


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    dpi = int(sys.argv[3]) if len(sys.argv) > 3 else 300

    img_dir = out / "images"
    ocr_dir = out / "ocr"
    md_dir = out / "pages"
    for directory in (img_dir, ocr_dir, md_dir):
        directory.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(src)
    total = doc.page_count
    print(f"{total} pages", flush=True)

    made = 0
    for i in range(total):
        dest = img_dir / f"{i + 1:03d}.jpg"
        if dest.exists():
            continue
        page = doc[i]
        imgs = page.get_images(full=True)
        if imgs:
            # The scan already is one full-page image: copy its bytes instead of
            # re-rendering the page (same pixels, far faster and smaller).
            dest.write_bytes(doc.extract_image(imgs[0][0])["image"])
        else:
            page.get_pixmap(dpi=dpi).save(dest)
        made += 1
    print(f"images +{made}", flush=True)

    sizes = {}
    for i in range(total):
        pix = pymupdf.Pixmap(str(img_dir / f"{i + 1:03d}.jpg"))
        sizes[i + 1] = (float(pix.width), float(pix.height))

    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    for i in range(total):
        pno = i + 1
        dest = ocr_dir / f"{pno:03d}.json"
        if dest.exists():
            continue
        digest(engine, img_dir / f"{pno:03d}.jpg", dest)
        if pno % 10 == 0:
            print(f"  ocr {pno}/{total}", flush=True)
    print("ocr done", flush=True)

    for i in range(total):
        pno = i + 1
        boxes = load_boxes(ocr_dir / f"{pno:03d}.json")
        w, h = sizes[pno]
        (md_dir / f"{pno:03d}.md").write_text(assemble(boxes, w, h) + "\n", encoding="utf-8")
    print("assemble done", flush=True)


if __name__ == "__main__":
    main()
