"""Validate the EEPC records.

This book has a real text layer, so the risk is not OCR but parsing: a spell body
running into the next entry, the back cover, or a half-read stat block. The checks
below are structural, plus a comparison with the same rules text already in the
corpus (Xanathar's Guide / Princes of the Apocalypse reprints), where differences
are expected from errata rather than from extraction.

    python scripts/pdf/validate_eepc.py
"""
from __future__ import annotations

import difflib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
COMPENDIUM = ROOT / "content" / "compendium"
WORD = re.compile(r"[a-z0-9']+")

# What the book says, checked independently of the parser.
EXPECTED_SPECIES = {
    "aarakocra": ({"dexterity": 2, "wisdom": 1}, "medium", 25, None),
    "deepgnome": ({"intelligence": 2, "dexterity": 1}, "small", 25, "gnome"),
    "genasi": ({"constitution": 2}, "medium", 30, None),
    "airgenasi": ({"dexterity": 1}, None, None, "genasi"),
    "earthgenasi": ({"strength": 1}, None, None, "genasi"),
    "firegenasi": ({"intelligence": 1}, None, None, "genasi"),
    "watergenasi": ({"wisdom": 1}, None, None, "genasi"),
    "goliath": ({"strength": 2, "constitution": 1}, "medium", 30, None),
}

FOREIGN = re.compile(
    r"(?i)(what happens next|MMORPG|Gale Force Nine|WizKids|Adventurers League"
    r"|Chapter \d \| |Spell Descriptions|Table of Contents|Fabricate)"
)


def squashed(text: str) -> str:
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=[a-z])[-–]\s*(?=[a-z])", "", text)
    return "".join(WORD.findall(text.lower()))


def key_of(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load(book: str, category: str) -> list[dict]:
    path = COMPENDIUM / book / f"{category}.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    report = ROOT / "logs" / "eepc_validation.txt"
    if "--report" in sys.argv:
        report = pathlib.Path(sys.argv[sys.argv.index("--report") + 1])

    spells = load("eepc", "spell")
    species = load("eepc", "species")
    lines: list[str] = [f"species: {len(species)}   spells: {len(spells)}"]

    problems: list[str] = []
    for record in spells:
        data = record["data"]
        missing = [
            field for field in ("casting_time", "range", "components", "duration")
            if not data.get(field)
        ]
        if missing:
            problems.append(f"{record['name_en']}: stat block missing {missing}")
        if not record["text_en"].strip():
            problems.append(f"{record['name_en']}: empty body")
        hit = FOREIGN.search(record["text_en"])
        if hit:
            problems.append(f"{record['name_en']}: foreign text {hit.group(0)!r}")
        if not data.get("classes"):
            problems.append(f"{record['name_en']}: no class list")
        if data["level"] > 0 and data["level"] > len(record["text_en"]) / 40:
            problems.append(f"{record['name_en']}: body looks too short for its level")

    for record in species:
        expected = EXPECTED_SPECIES.get(key_of(record["name_en"]))
        if expected is None:
            problems.append(f"{record['name_en']}: unexpected species entry")
            continue
        increases, size, speed, parent = expected
        data = record["data"]
        if data["ability_increases"] != increases:
            problems.append(
                f"{record['name_en']}: ability increases {data['ability_increases']} != {increases}"
            )
        if data["size"] != size:
            problems.append(f"{record['name_en']}: size {data['size']} != {size}")
        if data["speed"] != speed:
            problems.append(f"{record['name_en']}: speed {data['speed']} != {speed}")
        if (data["subrace_of"] or None) != parent:
            problems.append(f"{record['name_en']}: subrace_of {data['subrace_of']} != {parent}")

    missed = set(EXPECTED_SPECIES) - {key_of(record["name_en"]) for record in species}
    for name in sorted(missed):
        problems.append(f"missing species: {name}")

    lines.append(f"structural problems: {len(problems)}")
    lines.extend(f"  {problem}" for problem in problems)

    # Errata-aware comparison with the corpus copies of the same spells.
    xgte = {key_of(record["name_en"]): record for record in load("xgte", "spell")}
    pota = {key_of(record["name_en"]): record for record in load("pota", "spell")}
    lines.append("")
    lines.append("comparison with the same spells as reprinted in XGtE / PotA")
    lines.append("(differences here are errata, not extraction faults):")
    outliers = 0
    for record in spells:
        reference = xgte.get(key_of(record["name_en"])) or pota.get(key_of(record["name_en"]))
        if reference is None:
            lines.append(f"  {record['name_en']:32} no counterpart")
            continue
        ratio = difflib.SequenceMatcher(
            a=squashed(record["text_en"]), b=squashed(reference["text_en"]), autojunk=False
        ).ratio()
        scale = len(record["text_en"]) / max(1, len(reference["text_en"]))
        flag = ""
        if scale > 1.6 or scale < 0.6:
            flag = "  <-- length differs sharply"
            outliers += 1
        lines.append(f"  {record['name_en']:32} text {ratio:.3f}  length x{scale:.2f}{flag}")
    lines.append(f"length outliers: {outliers}")

    report.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:4]))
    print(f"report: {report}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
