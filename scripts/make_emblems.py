"""Emblems for the compendium and the wizard: a handful of game-icons.net icons (CC BY 3.0).

Takes the chosen icons from a checkout of https://github.com/game-icons/icons (the folder
name is the author) and writes only their path data, with author and source, to

    backend/src/dndsheet/visuals/application/emblems.json

The site draws them in its own colours (`currentColor`), so only the shape is kept. The
license is CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/): every icon used is
credited on /kb/credits and in docs/visuals.md, with its author.

    git clone --depth 1 https://github.com/game-icons/icons <dir>
    python scripts/make_emblems.py <dir>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "backend" / "src" / "dndsheet" / "visuals" / "application" / "emblems.json"

AUTHORS = {"lorc": "Lorc", "delapouite": "Delapouite", "skoll": "Skoll", "sbed": "Sbed"}

#: Our name → game-icons "<author>/<icon>".
CHOSEN = {
    # classes
    "class-artificer": "lorc/gear-hammer",
    "class-barbarian": "lorc/battle-axe",
    "class-bard": "lorc/lyre",
    "class-cleric": "lorc/holy-symbol",
    "class-druid": "delapouite/oak-leaf",
    "class-fighter": "lorc/crossed-swords",
    "class-monk": "lorc/meditation",
    "class-paladin": "delapouite/templar-shield",
    "class-ranger": "lorc/high-shot",
    "class-rogue": "lorc/cloak-dagger",
    "class-sorcerer": "lorc/magic-swirl",
    "class-warlock": "delapouite/warlock-eye",
    "class-wizard": "lorc/wizard-staff",
    # schools of magic
    "school-abjuration": "lorc/magic-shield",
    "school-conjuration": "lorc/magic-portal",
    "school-divination": "lorc/crystal-ball",
    "school-enchantment": "lorc/charm",
    "school-evocation": "lorc/fire-ray",
    "school-illusion": "lorc/domino-mask",
    "school-necromancy": "lorc/skull-crossed-bones",
    "school-transmutation": "delapouite/transform",
    # compendium sections
    "section-species": "lorc/hood",
    "section-classes": "lorc/broadsword",
    "section-backgrounds": "lorc/scroll-unfurled",
    "section-feats": "lorc/laurels",
    "section-spells": "delapouite/spell-book",
    "section-options": "lorc/rune-stone",
    "section-items": "lorc/knapsack",
    "section-glossary": "lorc/quill-ink",
    "section-guide": "lorc/open-book",
}

_PATH = re.compile(r'<path[^>]*\bd="([^"]+)"')
_NUMBER = re.compile(r"-?(?:\d+\.?\d*|\.\d+)")


def _short(token: str) -> str:
    value = f"{float(token):.1f}".rstrip("0").rstrip(".")
    if value in ("-0", ""):
        return "0"
    if value.startswith("0."):
        return value[1:]
    if value.startswith("-0."):
        return "-" + value[2:]
    return value


def _round(d: str) -> str:
    """One decimal is plenty in a 512 box shown at 18–56 px: about a third fewer bytes.

    Numbers in SVG paths may touch (`1.95.95` is two numbers); after rounding a
    separator is added where two numbers would otherwise merge into one.
    """
    out: list[str] = []
    position = 0
    for match in _NUMBER.finditer(d):
        out.append(d[position : match.start()])
        value = _short(match.group())
        previous = "".join(out)[-1:] if out else ""
        if previous and (previous.isdigit() or previous == ".") and not value.startswith("-"):
            out.append(" ")
        out.append(value)
        position = match.end()
    out.append(d[position:])
    return "".join(out)


def main(source: Path) -> int:
    emblems: dict[str, dict[str, str]] = {}
    for name, icon in CHOSEN.items():
        author, slug = icon.split("/")
        svg = (source / author / f"{slug}.svg").read_text(encoding="utf-8")
        paths = [d for d in _PATH.findall(svg) if d.strip() != "M0 0h512v512H0z"]
        if len(paths) != 1:
            raise SystemExit(f"{icon}: expected one shape path, got {len(paths)}")
        emblems[name] = {
            "d": _round(paths[0]),
            "author": AUTHORS.get(author, author.title()),
            "icon": slug,
            "url": f"https://game-icons.net/1x1/{author}/{slug}.html",
        }
    OUT.write_text(json.dumps(emblems, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    size = OUT.stat().st_size
    print(f"{OUT.relative_to(ROOT)}: {len(emblems)} emblems, {size / 1024:.1f} KB")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.exit(main(Path(sys.argv[1])))
