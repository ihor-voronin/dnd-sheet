"""Звірка наших назв із довідником D&D World.

Порівнюємо назви предметів і заклять: англійська в нас і в довіднику та
українська в нас і в довіднику. Виводить список розбіжностей, за яким далі
правимо словник. Нічого не змінює — тільки звіт.

Джерело правди для «наших» назв — те, що реально в застосунку: назви
предметів беруться з черг перекладу, закляття — з `uk.ts` (там же вони й
живуть, окремого файлу немає).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "var" / "reference"
WORK = ROOT / "var" / "translations" / "items"
SPACES = re.compile(r"\s+")


def norm(value: str) -> str:
    return SPACES.sub(" ", value.strip().lower()).replace("’", "'").replace("ʼ", "'")


def items_ours() -> dict[str, str]:
    """Пари з черг: id → name_en у `in/`, переклад у `content/translations`."""
    translated: dict[str, str] = {}
    for path in sorted((ROOT / "content" / "translations" / "items").glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8"))["items"]:
            translated[row["id"]] = row.get("name_uk") or ""
    ours: dict[str, str] = {}
    for path in sorted((WORK / "in").glob("*.json")):
        for row in json.loads(path.read_text(encoding="utf-8"))["items"]:
            name = translated.get(row["id"], "").strip()
            if name:
                ours.setdefault(norm(row["name_en"]), name)
    return ours


def spells_ours() -> dict[str, str]:
    """Закляття з `uk.ts`: ключ — англійська назва, значення — українська."""
    source = (ROOT / "frontend" / "src" / "features" / "character" / "uk.ts").read_text(encoding="utf-8")
    block = source.split("const SPELLS", 1)[1].split("};", 1)[0]
    pairs = re.findall(r'^\s{2}"?([^":\s][^":]*?)"?: \{\s*\n?\s*name: "([^"]+)"', block, re.M)
    return {norm(english): ukrainian for english, ukrainian in pairs}


def report(ours: dict[str, str], theirs: dict[str, str], title: str) -> None:
    have = 0
    same = 0
    diff: list[tuple[str, str, str]] = []
    for english, ukrainian in ours.items():
        reference = theirs.get(english)
        if reference is None:
            continue
        have += 1
        if norm(reference) == norm(ukrainian):
            same += 1
        else:
            diff.append((english, ukrainian, reference))
    print(f"=== {title}: у довіднику {have} з {len(ours)}, збігів {same}, розбіжностей {len(diff)}")
    for english, mine, reference in sorted(diff):
        print(f"  {english}\n    наше:  {mine}\n    дод.:  {reference}")


def main() -> None:
    report(items_ours(), _load(REFERENCE / "dndworld-items.json"), "предмети")
    print()
    report(spells_ours(), _load(REFERENCE / "dndworld-spells.json"), "закляття")


def _load(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
