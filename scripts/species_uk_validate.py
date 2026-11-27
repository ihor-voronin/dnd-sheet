"""Перевірити якість перекладу видів: числа, кубики, абзаци, мова.

Повнота — це `species_uk_check.py`. Цей скрипт дивиться на інше: чи переклад
не «загубив» числа й кубики (1d6 зник — це вже інше правило) і чи справді
український текст, а не англійська копія.

    python scripts/species_uk_validate.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "var" / "uk" / "input"
OUTPUT = ROOT / "content" / "translations" / "species"

DICE = re.compile(r"\b\d*d\d+\b")
#: «20,000» і «20 000» — те саме число: роздільник тисяч прибираємо.
THOUSANDS = re.compile(r"(?<=\d)[,\u00a0\u202f ](?=\d{3}(?!\d))")
CYRILLIC = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")
LATIN = re.compile(r"[A-Za-z]")


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def tokens(text: str) -> tuple[list[str], list[str]]:
    """Кубики й числа: «11th» і «11-го» — те саме одинадцять."""
    joined = THOUSANDS.sub("", text)
    return sorted(DICE.findall(joined)), sorted(re.findall(r"\d+", joined))


def paragraphs(text: str) -> int:
    return len([part for part in re.split(r"\n\s*\n", text) if part.strip()])


def main() -> int:
    problems: list[str] = []
    checked = 0

    files = [("names.json", "name_uk")] + [
        (path.name, "text_uk") for path in sorted(INPUT.glob("*.json")) if path.name != "names.json"
    ]
    for name, field in files:
        source = {str(row["id"]): row for row in load(INPUT / name)}
        translated = {str(row["id"]): str(row.get(field) or "") for row in load(OUTPUT / name)}
        for key, row in source.items():
            text_uk = translated.get(key, "")
            if not text_uk:
                continue
            checked += 1
            original = str(row.get("text_en") or row.get("name_en") or "")
            if not CYRILLIC.search(text_uk):
                problems.append(f"{name}:{key}: без кирилиці — {text_uk[:40]!r}")
                continue
            if name != "names.json":
                dice_src, number_src = tokens(original)
                dice_uk, number_uk = tokens(text_uk)
                if dice_src != dice_uk:
                    problems.append(f"{name}:{key}: кубики {dice_src} → {dice_uk}")
                if number_src != number_uk:
                    problems.append(f"{name}:{key}: числа {number_src} → {number_uk}")
                if paragraphs(original) != paragraphs(text_uk):
                    problems.append(f"{name}:{key}: абзаців {paragraphs(original)} → {paragraphs(text_uk)}")
            # англійський залишок: багато латиниці на кожну кирилицю
            latin, cyrillic = len(LATIN.findall(text_uk)), len(CYRILLIC.findall(text_uk))
            if latin > 3 and cyrillic and latin / cyrillic > 1.2:
                problems.append(f"{name}:{key}: схоже на неперекладене ({latin} лат. / {cyrillic} кир.)")

    for problem in problems[:40]:
        print("  !", problem)
    print(f"\nперевірено: {checked}; проблем: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
