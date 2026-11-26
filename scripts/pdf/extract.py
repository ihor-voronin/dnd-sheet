"""Pull entities out of the assembled page text.

The book marks every entry with a display heading, which the XY-cut assembler
turns into a `### ` line. Concatenating a chapter's pages and splitting on those
headings yields (name, body) candidates; this script prints them as JSON so the
records can be reviewed before they are written into the compendium.

    python scripts/pdf/extract.py content/raw/gotg-pdf 15 29
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import despace  # noqa: E402

FOOTER_RE = re.compile(r"^(chapter\s*\d+|appendix\s*[ab])\s*[|l]?\s*.{0,40}$", re.I)
PAGE_NOISE = re.compile(r"^\s*(kaicarpenter|olivierbernard|[0-9]{1,3})\s*$", re.I)


def load_pages(base: Path, pages: list[int]) -> str:
    chunks = []
    for pno in pages:
        path = base / "pages" / f"{pno:03d}.md"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if PAGE_NOISE.match(line) or FOOTER_RE.match(line.strip()):
                continue
            chunks.append(line)
    return "\n".join(chunks)


def split_entries(text: str) -> list[dict]:
    entries: list[dict] = []
    current = {"name": None, "body": []}
    for line in text.splitlines():
        if line.startswith("### "):
            if current["name"] or " ".join(current["body"]).strip():
                entries.append(current)
            current = {"name": line[4:].strip(), "body": []}
        else:
            current["body"].append(line)
    if current["name"] or " ".join(current["body"]).strip():
        entries.append(current)
    return [
        {"name": entry["name"], "text": despace.fix(" ".join(entry["body"]).strip())}
        for entry in entries
    ]


def main() -> None:
    base = Path(sys.argv[1])
    args = [a for a in sys.argv[2:] if not a.startswith("-o=")]
    out = next((a[3:] for a in sys.argv[2:] if a.startswith("-o=")), None)
    pages = []
    for arg in args:
        if "-" in arg:
            lo, hi = arg.split("-", 1)
            pages.extend(range(int(lo), int(hi) + 1))
        else:
            pages.append(int(arg))
    text = load_pages(base, pages)
    entries = split_entries(text)
    payload = json.dumps(entries, ensure_ascii=False, indent=1)
    if out:
        Path(out).write_text(payload, encoding="utf-8")
        print(f"{len(entries)} entries -> {out}")
    else:
        print(payload)


if __name__ == "__main__":
    main()
