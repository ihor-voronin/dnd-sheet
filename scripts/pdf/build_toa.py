"""Tomb of Annihilation → записи довідника.

Книга — пригода, і для листка в ній є рівно те, чого бракувало корпусу:
дві передісторії в додатку A (Anthropologist, Archaeologist). Додаток C дає
магічні предмети, додаток D — монстрів; їхній розбір окремий, тут його немає.

Текстовий шар справжній (не скан), тому OCR не потрібен: заголовки набрані
Times-Roman у великих літерах, тіло — Times-Roman 9.6.

    python scripts/pdf/build_toa.py --pages   # розкласти сторінки в markdown
    python scripts/pdf/build_toa.py           # зібрати записи
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.normalize import canonical as compendium_format  # noqa: E402
from scripts.pdf import build_sotdq as base  # noqa: E402

PDF = ROOT / "content" / "raw" / "toa" / "source.pdf"
PAGES_DIR = ROOT / "content" / "raw" / "toa" / "pages"
SOURCE = "toa"
LICENSE = "proprietary"
URL = None
FETCHED = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

BACKGROUNDS = [
    ("ANTHROPOLOGIST", "Anthropologist"),
    ("ARCHAEOLOGIST", "Archaeologist"),
]

HEADING_MIN = 10.4


def read_lines(doc: pymupdf.Document) -> list[base.Line]:
    return base.read_lines(doc)


def despace(text: str) -> str:
    """Склеює заголовки, розірвані кернінгом: «A RC HA EO L OG I ST».

    У цьому PDF частина заголовків набрана з міжлітерними пробілами, і без
    склейки вони не розпізнаються як заголовки («A RC HA EO L OG I ST» замість
    «ARCHAEOLOGIST»). Склеюємо лише тоді, коли всі слова короткі (1–2 літери)
    і рядок у великих літерах — інакше зламали б «APPENDIX A: CHARACTER …».
    """
    words = [word for word in text.split(" ") if word]
    if len(words) >= 3 and text.isupper() and all(1 <= len(word) <= 2 for word in words):
        return "".join(words)
    return text


def is_heading(line: base.Line) -> bool:
    text = despace(line.text.strip())
    return line.size >= HEADING_MIN and text.isupper() and 2 < len(text) < 80


def heading_level(line: base.Line) -> int:
    if line.size >= 16:
        return 1
    if line.size >= 12.2:
        return 2
    return 3


def build_nodes(lines: list[base.Line]) -> list[base.Node]:
    nodes: list[base.Node] = []
    paragraph: base.Node | None = None

    def flush() -> None:
        nonlocal paragraph
        if paragraph is not None and paragraph.text.strip():
            nodes.append(paragraph)
        paragraph = None

    for line in lines:
        if is_heading(line):
            flush()
            nodes.append(
                base.Node(
                    "heading",
                    base.clean(despace(line.text)),
                    heading_level(line),
                    line.page,
                    [line],
                )
            )
        elif line.font.startswith("Times-Italic"):
            flush()
            nodes.append(base.Node("italic", base.clean(line.text), 0, line.page, [line]))
        elif paragraph is None or line.bold_lead or line.size != paragraph.lines[-1].size:
            flush()
            paragraph = base.Node("para", base.clean(line.text), 0, line.page, [line])
        else:
            paragraph.text = base.join_pair(paragraph.text, line.text)
            paragraph.lines.append(line)
    flush()
    return nodes


def section(nodes: list[base.Node], title: str) -> tuple[list[base.Node], base.Node]:
    index = next(
        i
        for i, node in enumerate(nodes)
        if node.kind == "heading" and node.text.strip().upper() == title.upper()
    )
    heading = nodes[index]
    body: list[base.Node] = []
    for node in nodes[index + 1 :]:
        if node.kind == "heading" and node.level <= heading.level:
            break
        body.append(node)
    return body, heading


def entity_text(nodes: list[base.Node]) -> str:
    return base.clean("\n\n".join(node.text for node in nodes if node.text.strip()))


def feature_name(text: str) -> str | None:
    match = re.search(r"^Feature:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def make_record(category: str, name_en: str, slug: str, text: str, data: dict, page: int) -> dict:
    return {
        "id": f"{SOURCE}/{category}/{slug}",
        "schema": "compendium-entry/1",
        "source_id": SOURCE,
        "category": category,
        "name_en": name_en,
        "name_uk": None,
        "edition": "2014",
        "license": LICENSE,
        "url": URL,
        "page": page,
        "text_en": text,
        "text_uk": None,
        "data": data,
        "status": "raw",
        "fetched_at": FETCHED,
        "notes": [],
    }


def build_records(nodes: list[base.Node]) -> list[dict]:
    records: list[dict] = []
    for title, english in BACKGROUNDS:
        body, heading = section(nodes, title)
        text = entity_text(body)
        records.append(
            make_record(
                "background",
                english,
                re.sub(r"[^a-z0-9]+", "-", english.lower()).strip("-"),
                text,
                {"feature": feature_name(text)},
                heading.page,
            )
        )
    return records


def write_records(records: list[dict]) -> dict[str, int]:
    spec = compendium_format.load_spec()
    by_category: dict[str, list[dict]] = {}
    for record in records:
        canonical, _ = compendium_format.canonicalize(record, spec)
        by_category.setdefault(canonical["category"], []).append(canonical)
    for category, rows in by_category.items():
        directory = spec.category_dir(category, SOURCE)
        directory.mkdir(parents=True, exist_ok=True)
        compendium_format.write_jsonl(directory / f"{category}.jsonl", rows)
    _, _, problems = compendium_format.normalize_source(SOURCE, spec, write=True)
    for problem in problems:
        print("ПРОБЛЕМА:", problem, file=sys.stderr)
    return {category: len(rows) for category, rows in by_category.items()}


def main(argv: list[str] | None = None) -> int:
    args = set(argv or sys.argv[1:])
    doc = pymupdf.open(PDF)
    lines = read_lines(doc)
    if "--pages" in args:
        PAGES_DIR.mkdir(parents=True, exist_ok=True)
        by_page: dict[int, list[base.Line]] = {}
        for line in lines:
            by_page.setdefault(line.page, []).append(line)
        for page in range(1, doc.page_count + 1):
            nodes = build_nodes(by_page.get(page, []))
            (PAGES_DIR / f"{page:03d}.md").write_text(
                "\n\n".join(
                    ("#" * node.level + " " + node.text) if node.kind == "heading" else node.text
                    for node in nodes
                )
                + "\n",
                encoding="utf-8",
            )
        print(f"сторінок: {doc.page_count} → {PAGES_DIR}")
        return 0
    records = build_records(build_nodes(lines))
    counters = write_records(records)
    print("записи:", ", ".join(f"{k}={v}" for k, v in sorted(counters.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
