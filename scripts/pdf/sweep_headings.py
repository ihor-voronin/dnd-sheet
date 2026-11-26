"""Completeness sweep: list every entry heading in the reference, compare to ours."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "logs" / "gotg_ref_text.pdf"
COMPENDIUM = ROOT / "content" / "compendium" / "gotg"


def page_text(first: int, last: int) -> str:
    doc = pymupdf.open(REF)
    return "\n".join(doc[index].get_text("text") for index in range(first - 1, last))


def headings(text: str) -> list[str]:
    """Display headings: short lines in caps or Title Case, not sentence text."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not 3 < len(line) < 60:
            continue
        if line.endswith((".", ",", ";", ":")) or re.search(r"\d{2,}", line):
            continue
        letters = [c for c in line if c.isalpha()]
        if not letters:
            continue
        if sum(1 for c in letters if c.isupper()) / len(letters) > 0.6:
            out.append(line)
    return out


def main() -> None:
    records = []
    for path in sorted(COMPENDIUM.glob("*.jsonl")):
        records.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    known = {re.sub(r"[^a-z0-9]", "", record["name_en"].lower()) for record in records}

    for label, first, last in (("chapter 1", 15, 24), ("magic items", 114, 122)):
        print(f"===== {label}: reference headings =====")
        seen: list[str] = []
        for heading in headings(page_text(first, last)):
            key = re.sub(r"[^a-z0-9]", "", heading.lower())
            if key in seen:
                continue
            seen.append(key)
            covered = any(key == name or key in name or name in key for name in known)
            if not covered:
                print(f"  not in records: {heading}")
        print(f"  ({len(seen)} distinct headings)")


if __name__ == "__main__":
    main()
