"""Назви класів, видів, підкласів і передісторій для експорту (бекенд).

Джерело — словники `TERMS` і `SPECIES_UK` у `frontend/src/features/character/uk.ts`
(там їх бачить екран). Бекенд не читає TypeScript, тож скрипт переносить їх у
шар `content/translations/terms/names.json`: id — хеш англійської назви в
нижньому регістрі (`uk_text.ident`).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "src" / "features" / "character" / "uk.ts"
TARGET = ROOT / "content" / "translations" / "terms" / "names.json"
PAIR = re.compile(r'^\s*"?([^":]+?)"?\s*:\s*"([^"]+)",', re.M)


def block(text: str, name: str) -> str:
    start = text.index(f"const {name}")
    return text[start : text.index("\n};", start)]


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    pairs: dict[str, str] = {}
    for name in ("TERMS", "SPECIES_UK"):
        for en, uk in PAIR.findall(block(text, name)):
            pairs.setdefault(en.strip().casefold(), uk)
    rows = [
        {"id": hashlib.sha1(en.encode()).hexdigest()[:10], "en": en, "name_uk": uk}
        for en, uk in sorted(pairs.items())
    ]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(rows))


if __name__ == "__main__":
    main()
