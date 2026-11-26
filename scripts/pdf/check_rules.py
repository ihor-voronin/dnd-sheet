"""Check the two authored rule records against the reference scan.

`rule/bonus-feats` is short prose and `rule/rune-spells` is a table, so neither
locates the way a long body entry does. Here the table's rune -> spell pairs are
read straight out of the reference page and compared pair by pair.

    python scripts/pdf/check_rules.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "logs" / "gotg_ref_text.pdf"
COMPENDIUM = ROOT / "content" / "compendium" / "gotg" / "rule.jsonl"

SPELLS = (
    "fog cloud|inflict wounds|chromatic orb|disguise self|burning hands|speak with animals"
    "|armor of agathys|goodberry|longstrider|command|entangle|sanctuary|thunderwave"
)


def ref_text() -> str:
    doc = pymupdf.open(REF)
    # Chapter 1 runs across PDF pages 15-23 (printed 11-19).
    return "\n".join(doc[index].get_text("text") for index in range(14, 23))


def pairs(text: str) -> dict[str, str]:
    """Rune -> spell pairs, read as `Rune ... Spell` runs from the table."""
    flat = re.sub(r"\s+", " ", text)
    found: dict[str, str] = {}
    for match in re.finditer(r"\b([A-Z][a-z]{3,9})\s+((?:" + SPELLS + r"))\b", flat, re.IGNORECASE):
        found[match.group(1).title()] = match.group(2).title()
    return found


def main() -> None:
    records = [json.loads(line) for line in COMPENDIUM.read_text(encoding="utf-8").splitlines() if line.strip()]

    ours: dict[str, str] = {}
    for record in records:
        if record["id"].endswith("/rune-spells"):
            for line in record["text_en"].splitlines():
                cells = [cell.strip(" *") for cell in line.strip().strip("|").split("|")]
                if len(cells) == 2 and cells[0] not in ("Rune", "---"):
                    ours[cells[0]] = cells[1]

    reference = pairs(ref_text())
    print(f"ours: {len(ours)} pairs, reference: {len(reference)}")
    missing = {rune: spell for rune, spell in ours.items() if reference.get(rune, "").lower() != spell.lower()}
    extra = {rune: spell for rune, spell in reference.items() if rune not in ours}
    print("mismatched or unconfirmed in reference:", missing or "none")
    print("pairs the reference has that we lack:", extra or "none")

    bonus = next(record for record in records if record["id"].endswith("/bonus-feats"))
    flat_ref = re.sub(r"\s+", " ", ref_text())
    flat_ours = re.sub(r"\s+", " ", bonus["text_en"])
    key = "If the DM decides to allow the giant foundling and rune carver backgrounds"
    print("bonus-feats text present in reference:", key.lower() in flat_ref.lower())
    print("bonus-feats has the Skilled/Tough list:", "Skilled" in flat_ref and "Tough" in flat_ref)
    del flat_ours


if __name__ == "__main__":
    main()
