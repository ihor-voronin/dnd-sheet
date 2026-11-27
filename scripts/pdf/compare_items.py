"""Compare each gotg item record with the reference OCR slice, item by item.

Both sides are item-scoped here (the reference is cut by stat lines), so a word
diff is meaningful: it shows which sentences disagree rather than where the next
entry begins. Records are paired to reference slices by text similarity, because
the two OCRs do not agree on the display headings.

    python scripts/pdf/compare_items.py [--report logs/gotg_items_diff.txt]
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF_ITEMS = ROOT / "logs" / "gotg_ref_items.json"
OURS = ROOT / "content" / "compendium" / "gotg" / "item.jsonl"
WORD = re.compile(r"[a-z0-9']+")


def normalise(text: str) -> list[str]:
    """Lowercase words, with line-break hyphens rejoined ("pig- ments")."""
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=[a-z])[-–]\s*(?=[a-z])", "", text)
    return WORD.findall(text.lower())


def squashed(text: str) -> str:
    return "".join(normalise(text))


def similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(a=left, b=right, autojunk=False).ratio()


def main() -> None:
    report = ROOT / "logs" / "gotg_items_diff.txt"
    if "--report" in sys.argv:
        report = Path(sys.argv[sys.argv.index("--report") + 1])

    ours = [json.loads(line) for line in OURS.read_text(encoding="utf-8").splitlines() if line.strip()]
    refs = [
        {"text": entry["text"], "squashed": squashed(entry["text"])}
        for entry in json.loads(REF_ITEMS.read_text(encoding="utf-8"))
    ]
    for ref in refs:
        ref["words"] = normalise(ref["text"])

    lines: list[str] = []
    summary: list[tuple[float, str]] = []
    used: set[int] = set()
    pairs: list[tuple[dict, dict, float]] = []
    for record in ours:
        key = squashed(record["text_en"])
        scored = sorted(
            ((similarity(key, ref["squashed"]), index) for index, ref in enumerate(refs)),
            reverse=True,
        )
        best, index = scored[0]
        pairs.append((record, refs[index], best))
        used.add(index)
        summary.append((best, record["name_en"]))

    for record, ref, ratio in sorted(pairs, key=lambda item: item[2]):
        if ratio >= 0.985:
            continue
        ours_words = normalise(record["text_en"])
        ref_words = ref["words"]
        matcher = difflib.SequenceMatcher(a=ours_words, b=ref_words, autojunk=False)
        lines.append("")
        lines.append(
            f"## {record['name_en']}  (similarity {ratio:.4f}, ours {len(ours_words)}w, ref {len(ref_words)}w)"
        )
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            ours_frag = " ".join(ours_words[max(0, i1 - 4) : i2 + 4])
            ref_frag = " ".join(ref_words[max(0, j1 - 4) : j2 + 4])
            lines.append(f"   [{tag}] OURS: …{ours_frag}…")
            lines.append(f"          REF : …{ref_frag}…")

    lines.append("")
    lines.append(f"reference slices not matched to a record: {len(refs) - len(used)}")
    head = [f"{name}: {ratio:.4f}" for ratio, name in sorted(summary)]
    report.write_text("\n".join(head + [""] + lines), encoding="utf-8")
    print("\n".join(head))
    print(f"report: {report}")


if __name__ == "__main__":
    main()
