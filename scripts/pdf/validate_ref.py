"""Validate the gotg records against an independent OCR of the same book.

`logs/gotg_ref_text.pdf` is an Internet Archive scan of the same 200 pages with
its own auto-OCR. Two independently OCR'd copies separate real text from
recognition noise: where both agree the reading is almost certainly right, and
each disagreement is a place worth checking against the page image.

Spacing and punctuation are normalised away before comparing, because that is
exactly the axis on which two OCRs differ without either being wrong
("max imum" vs "maximum", "armor s" vs "armor's").

    python scripts/pdf/validate_ref.py [--report logs/gotg_validation.txt]
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "logs" / "gotg_ref_text.pdf"
COMPENDIUM = ROOT / "content" / "compendium" / "gotg"
KEEP = re.compile(r"[a-z0-9]")

# Records whose remaining differences were read one by one and traced to the
# reference OCR, not to us ("furdined", "s eet storm", "feet of 4 creature",
# "40 feet" for a range the page image clearly prints as 60). Listed so a later
# run does not have to re-litigate them.
REVIEWED_OURS_PREFERRED = {
    "gotg/background/rune-carver": "reference misreads lone/rol/metal/figurnes/nutes",
    "gotg/subclass/path-of-the-giant": "reference prints 40 ft; the page image says 60 ft",
    "gotg/item/lucent-destroyer": "reference shows running head inside the sentence",
    "gotg/item/mistral-mantle": "reference: atunement, furdined, 'feet of 4 creature', 's eet storm'",
}


def squash_with_map(text: str) -> tuple[str, list[int]]:
    """Lowercase alphanumerics only, plus the raw index of every kept char."""
    kept: list[str] = []
    index: list[int] = []
    for position, char in enumerate(text):
        low = char.lower()
        if KEEP.match(low):
            kept.append(low)
            index.append(position)
    return "".join(kept), index


@dataclass
class Page:
    raw: str
    squashed: str
    index: list[int]


def load_pages() -> list[Page]:
    doc = pymupdf.open(REF)
    pages = []
    for page in doc:
        raw = page.get_text("text")
        squashed, index = squash_with_map(raw)
        pages.append(Page(raw, squashed, index))
    return pages


STAT_END = re.compile(
    r"(?:Wondrous Item|Weapon \([^)]*\)|Armor \([^)]*\)|Ring|Rod|Staff|Wand|Shield)"
    r"\s*,?\s*(?:Common|Uncommon|Rare|Very Rare|Legendary|Artifact|Varies)"
    r"(?:\s*\(Requires Attunement[^)]*\))?",
    re.IGNORECASE,
)


def locate(pages: list[Page], text: str, hint: int | None) -> tuple[int, int, float] | None:
    """Find where `text` begins in the reference, preferring the best-matching hit.

    Item records open with the same stat line ("Wondrous Item, Very Rare
    (Requires Attunement)"), so keys are taken from distinctive parts of the
    body — right after the stat line first, then further in — and every
    candidate hit is scored by how well the surrounding text matches.
    """
    squashed_ours, _ = squash_with_map(text)
    stat = STAT_END.search(text)
    offsets = []
    if stat:
        offsets.append(len(squash_with_map(text[:stat.end()])[0]) + 10)
    offsets.extend((180, 320, 90))
    offsets = [offset for offset in offsets if 0 < offset < len(squashed_ours) - 45]

    order = list(range(len(pages)))
    if hint is not None:
        guess = max(0, min(len(pages) - 1, hint + 4 - 1))
        order = [guess] + [index for index in order if index != guess]

    best: tuple[int, int, float] | None = None
    for offset in offsets:
        needle = squashed_ours[offset:offset + 45]
        for page_index in order:
            page = pages[page_index]
            for position in _all_positions(page.squashed, needle):
                back = position - offset
                if back < 0:
                    continue
                start = page.index[back]
                ref_raw = reference_window(pages, (page_index, start), len(text))
                ref_s, _ = squash_with_map(ref_raw)
                ratio = difflib.SequenceMatcher(
                    a=squashed_ours, b=ref_s[: len(squashed_ours) + 40], autojunk=False
                ).ratio()
                if best is None or ratio > best[2]:
                    best = (page_index, start, ratio)
                if ratio > 0.97:
                    return best
    return best


def _all_positions(haystack: str, needle: str) -> list[int]:
    found = []
    start = 0
    while True:
        position = haystack.find(needle, start)
        if position < 0:
            return found
        found.append(position)
        start = position + 1


def reference_window(pages: list[Page], start: tuple[int, int], length: int) -> str:
    page_index, offset = start
    text = pages[page_index].raw[offset:]
    for follow in range(page_index + 1, len(pages)):
        if len(text) > length * 2:
            break
        text += "\n" + pages[follow].raw
    return text[: int(length * 2.0)]


@dataclass
class Result:
    record: str
    page: int | None
    located: bool
    coverage: float
    truncated: bool
    diffs: list[str]


def compare(record: dict, pages: list[Page]) -> Result:
    """How much of our text the reference explains, and whether it is cut short.

    The reference window runs past the end of the entry into the next one, so the
    question is one-directional: is every word we wrote present, in order, in the
    book? Low coverage means we wrote something the book does not say; text the
    reference holds beyond our last word is the next entry and is ignored.
    """
    ours = record["text_en"]
    start = locate(pages, ours, record.get("page"))
    if start is None:
        return Result(record["id"], record.get("page"), False, 0.0, False, [])
    page_index, offset, _score = start
    ref_raw = reference_window(pages, (page_index, offset), len(ours))
    ours_s, _ = squash_with_map(ours)
    ref_s, _ = squash_with_map(ref_raw)

    matcher = difflib.SequenceMatcher(a=ours_s, b=ref_s, autojunk=False)
    matched = sum(i2 - i1 for tag, i1, i2, _j1, _j2 in matcher.get_opcodes() if tag == "equal")
    coverage = matched / len(ours_s) if ours_s else 0.0

    diffs: list[str] = []
    last_ref = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        last_ref = max(last_ref, j2)
        if tag == "equal":
            continue
        if tag == "replace" and max(i2 - i1, j2 - j1) < 4:
            continue  # single-letter OCR noise
        diffs.append(
            f"[{tag}] ours …{ours_s[max(0, i1 - 20):i2 + 20]}… | ref …{ref_s[max(0, j1 - 20):j2 + 20]}…"
        )

    # If the book keeps going mid-sentence after our last word, we cut it short.
    tail = ref_raw[:0]
    del tail
    following = ref_s[last_ref:last_ref + 60]
    truncated = len(following) > 20 and not re.search(r"[.!?]", following[:20])
    return Result(record["id"], record.get("page"), True, coverage, truncated, diffs)


def load_records() -> list[dict]:
    records: list[dict] = []
    for path in sorted(COMPENDIUM.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    return records


def main() -> None:
    out = ROOT / "logs" / "gotg_validation.txt"
    if "--report" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--report") + 1])

    pages = load_pages()
    records = load_records()
    results = [compare(record, pages) for record in records]

    lines = [f"records: {len(results)}   reference pages: {len(pages)}"]
    missing = [r for r in results if not r.located]
    lines.append(f"not located in the reference: {len(missing)}")
    lines.extend(f"  {result.record}" for result in missing)

    located = [r for r in results if r.located]
    clean = [r for r in located if r.coverage >= 0.995 and not r.truncated]
    reviewed = [r for r in located if r.record in REVIEWED_OURS_PREFERRED]
    lines.append(f"located: {len(located)}; fully explained by the book: {len(clean)}")
    lines.append(f"reviewed and kept as ours (reference OCR is worse): {len(reviewed)}")
    for result in reviewed:
        lines.append(f"  {result.record} - {REVIEWED_OURS_PREFERRED[result.record]}")

    for result in sorted(located, key=lambda r: (r.coverage, r.truncated)):
        if result.coverage >= 0.995 and not result.truncated:
            continue
        flags = []
        if result.coverage < 0.995:
            flags.append(f"coverage {result.coverage:.4f}")
        if result.truncated:
            flags.append("possibly cut short")
        lines.append("")
        lines.append(f"## {result.record}  (page {result.page}, {', '.join(flags)})")
        for diff in result.diffs[:10]:
            lines.append(f"   {diff}")

    out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:6]))
    print(f"report: {out}")


if __name__ == "__main__":
    main()
