"""Slice items out of the reference OCR by their stat lines.

The reference scan is a second, independent OCR of the same pages. Its text is
linear (no column scrambling from our own layout analysis), so consecutive stat
lines delimit items cleanly — useful for checking the wording of entries whose
own OCR came out interleaved.

    python scripts/pdf/ref_items.py [--out logs/gotg_ref_items.json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "logs" / "gotg_ref_text.pdf"
STAT = re.compile(
    r"(?:Weapon|Armor)\s*\([^)]{0,40}\)\s*,\s*(?:Common|Uncommon|Rare|Very Rare|Legendary|Artifact|Var\w+)"
    r"|(?:Wondrous Item|Ring|Rod|Staff|Wand|Shield|Potion|Scroll|Tome)\s*,\s*"
    r"(?:Common|Uncommon|Rare|Very Rare|Legendary|Artifact|Var\w+)",
    re.IGNORECASE,
)
NAME_BACK = 90


def load_text(first: int, last: int) -> str:
    doc = pymupdf.open(REF)
    chunks = []
    for index in range(first - 1, min(last, doc.page_count)):
        chunks.append(doc[index].get_text("text"))
    return "\n".join(chunks)


def main() -> None:
    out = ROOT / "logs" / "gotg_ref_items.json"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    text = load_text(114, 122)
    flat = re.sub(r"\s+", " ", text)

    starts = [match.start() for match in STAT.finditer(flat)]
    entries = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(flat)
        head = flat[max(0, start - NAME_BACK):start].strip()
        name = re.split(r"(?<=[a-z])\.\s", head)[-1].strip()
        entries.append({"head": head[-70:], "name_guess": name, "text": flat[start:end].strip()})

    out.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(entries)} stat lines -> {out}")
    for entry in entries:
        print(f"[{entry['name_guess']}] {len(entry['text'])} · {entry['text'][:110]}")


if __name__ == "__main__":
    main()
