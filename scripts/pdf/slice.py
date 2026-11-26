"""Slice the assembled text by known entry names.

Display headings in this book are italic item/feat names, and OCR often glues
them to the stat line that follows ("Adze of Annam Weapon (Greataxe), Arti...").
Instead of trusting heading detection, this walks a canonical list of names and
cuts the text between consecutive ones, matching spaces loosely so OCR spacing
glitches do not hide a name.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import despace  # noqa: E402
import polish  # noqa: E402

NOISE = re.compile(
    r"^\s*(chapter\s*\d+\s*[|lI1]\s*.{0,40}|appendix\s*[ab]\s*[|lI1]?\s*.{0,40}"
    r"|kaicarpenter|isabel\w*|[0-9]{1,3})\s*$",
    re.IGNORECASE,
)


STAT_LINE = re.compile(
    r"(?:Wondrous Item|Weapon \(|Armor \(|Ring,|Rod,|Staff,|Wand,|Shield,)"
    r"\s*(?:Common|Uncommon|Rare|Very Rare|Legendary|Artifact|Var\w+)",
    re.IGNORECASE,
)


def squash(text: str) -> str:
    """Lowercase with every non-letter removed, for loose matching."""
    return re.sub(r"[^a-z]", "", text.lower())


def load_text(base: Path, pages: list[int]) -> str:
    chunks: list[str] = []
    for pno in pages:
        path = base / "pages" / f"{pno:03d}.md"
        if not path.exists():
            continue
        keep = [line for line in path.read_text(encoding="utf-8").splitlines() if not NOISE.match(line)]
        chunks.append("\n".join(keep))
    text = "\n".join(chunks)
    return re.sub(r"\n{3,}", "\n\n", text)


def slice_entries(text: str, names: list[str]) -> list[dict]:
    """Cut `text` into entries, one per name, in the given order."""
    flat = squash(text)
    # Cheap index: squash(text) positions do not map linearly to raw offsets, so
    # find each name on the raw text with a whitespace-tolerant regex instead.
    positions: list[tuple[int, str]] = []
    for name in names:
        # Split on apostrophes too: OCR renders "Wayfarer's" as "Wayfarer's",
        # "Wayfarer s" or "Wayfarer'S", and the separator below absorbs that.
        words = [w for w in re.split(r"[\s']+", name) if w]
        pattern = r"[^A-Za-z]{0,8}".join(re.escape(w) for w in words)
        hits = [match.start() for match in re.finditer(pattern, text, re.IGNORECASE)]
        if not hits:
            positions.append((-1, name))
            continue
        # An entry heading is followed by its stat line ("Wondrous Item, Rare"),
        # so prefer the first hit that looks like a heading rather than prose.
        def looks_like_heading(start: int) -> bool:
            tail = text[start:start + 140]
            return bool(STAT_LINE.search(tail))

        chosen = next((hit for hit in hits if looks_like_heading(hit)), hits[0])
        positions.append((chosen, name))

    found = [(pos, name) for pos, name in positions if pos >= 0]
    found.sort()
    entries: list[dict] = []
    for idx, (start, name) in enumerate(found):
        end = found[idx + 1][0] if idx + 1 < len(found) else len(text)
        body = text[start:end]
        # Drop the heading itself from the body.
        body = body[len(name):] if body.lower().startswith(name.lower()) else body
        entries.append({"name": name, "text": polish.polish(despace.fix(clean_body(body)))})
    missing = [name for pos, name in positions if pos < 0]
    return entries, missing


def clean_body(body: str) -> str:
    body = re.sub(r"\s+", " ", body).strip()
    # Repair the sentence breaks the page join introduced.
    body = re.sub(r"\s+([,.;:])", r"\1", body)
    return body


def main() -> None:
    base = Path(sys.argv[1])
    names_file = Path(sys.argv[2])
    out = Path(sys.argv[3])
    pages = []
    for arg in sys.argv[4:]:
        if "-" in arg:
            lo, hi = arg.split("-", 1)
            pages.extend(range(int(lo), int(hi) + 1))
        else:
            pages.append(int(arg))
    names = [line.strip() for line in names_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    text = load_text(base, pages)
    entries, missing = slice_entries(text, names)
    out.write_text(json.dumps({"entries": entries, "missing": missing}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(entries)} found, {len(missing)} missing -> {out}")
    if missing:
        print("missing:", ", ".join(missing))


if __name__ == "__main__":
    main()
