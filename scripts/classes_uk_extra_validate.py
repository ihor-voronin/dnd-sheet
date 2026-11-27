"""Перевірити переклад опційних умінь класів (24 тексти поза главою PHB).

python scripts/classes_uk_extra_validate.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "var" / "uk" / "classes" / "extra" / "texts-01.json"
OUTPUT = ROOT / "content" / "translations" / "classes" / "texts-extra-01.json"

DICE = re.compile(r"\b\d*d\d+\b")
CYRILLIC = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")


def tokens(text: str) -> tuple[list[str], list[str]]:
    return sorted(DICE.findall(text)), sorted(re.findall(r"\d+", text))


def paragraphs(text: str) -> int:
    return len([part for part in re.split(r"\n\s*\n", text) if part.strip()])


def main() -> int:
    source = {row["id"]: row for row in json.loads(INPUT.read_text(encoding="utf-8"))}
    try:
        rows = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"немає або невалідний вихід: {exc}")
        return 1
    translated = {row["id"]: str(row.get("text_uk") or "") for row in rows}
    problems: list[str] = []
    for key, row in source.items():
        text_uk = translated.get(key, "")
        if not text_uk.strip():
            problems.append(f"{row['name_en']}: немає перекладу")
            continue
        if not CYRILLIC.search(text_uk):
            problems.append(f"{row['name_en']}: без кирилиці")
            continue
        dice_src, numbers_src = tokens(row["text_en"])
        dice_uk, numbers_uk = tokens(text_uk)
        if dice_src != dice_uk:
            problems.append(f"{row['name_en']}: кубики {dice_src} → {dice_uk}")
        if numbers_src != numbers_uk:
            problems.append(f"{row['name_en']}: числа {numbers_src} → {numbers_uk}")
        if paragraphs(row["text_en"]) != paragraphs(text_uk):
            problems.append(f"{row['name_en']}: абзаців {paragraphs(row['text_en'])} → {paragraphs(text_uk)}")
    for problem in problems[:20]:
        print("  !", problem)
    print(f"перевірено: {len(source)}; проблем: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
