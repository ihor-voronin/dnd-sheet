"""Перевірити якість перекладу класів: числа, кубики, абзаци, мова.

Повнота — це `classes_uk_check.py`. Цей скрипт дивиться на інше: чи переклад
не «загубив» числа й кубики (1d6 зник — це вже інше правило), чи збережено
структуру (пункти списку, заголовки всередині тексту) і чи справді текст
український, а не англійська копія.

    python scripts/classes_uk_validate.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "var" / "uk" / "subclasses" / "input"
OUTPUT = ROOT / "content" / "translations" / "subclasses"

DICE = re.compile(r"\b\d*d\d+\b")
#: «20,000» і «20 000» — те саме число: роздільник тисяч прибираємо.
THOUSANDS = re.compile(r"(?<=\d)[,\u00a0\u202f ](?=\d{3}(?!\d))")
CYRILLIC = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")
LATIN = re.compile(r"[A-Za-z]")
BULLET = re.compile(r"^\s*[-*]\s", re.MULTILINE)
SUBHEADING = re.compile(r"^#{3,6}\s", re.MULTILINE)


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

    for path in sorted(INPUT.glob("*.json")):
        field = "name_uk" if path.name in ("names.json", "entries.json") else "text_uk"
        source = {str(row["id"]): row for row in load(path)}
        translated = {
            str(row["id"]): str(row.get(field) or "")
            for row in load(OUTPUT / path.name)
        }
        for key, row in source.items():
            text_uk = translated.get(key, "")
            if not text_uk:
                continue
            checked += 1
            original = str(row.get("text_en") or row.get("name_en") or "")
            if not CYRILLIC.search(text_uk):
                problems.append(f"{path.name}:{key}: без кирилиці — {text_uk[:40]!r}")
                continue
            if field == "name_uk":
                # Назва — коротка: латиниця тут означає неперекладене. Кубики
                # в дужках («(d10)») — не англійська, їх прибираємо перед
                # перевіркою.
                if LATIN.search(re.sub(r"d\d+", "", text_uk)):
                    problems.append(f"{path.name}:{key}: латиниця в назві — {text_uk!r}")
                continue
            dice_src, number_src = tokens(original)
            dice_uk, number_uk = tokens(text_uk)
            if dice_src != dice_uk:
                problems.append(f"{path.name}:{key}: кубики {dice_src} → {dice_uk}")
            if number_src != number_uk:
                problems.append(f"{path.name}:{key}: числа {number_src} → {number_uk}")
            if paragraphs(original) != paragraphs(text_uk):
                problems.append(
                    f"{path.name}:{key}: абзаців {paragraphs(original)} → "
                    f"{paragraphs(text_uk)}"
                )
            bullets_src = len(BULLET.findall(original))
            bullets_uk = len(BULLET.findall(text_uk))
            if bullets_src != bullets_uk:
                problems.append(
                    f"{path.name}:{key}: пунктів {bullets_src} → {bullets_uk}"
                )
            headings_src = len(SUBHEADING.findall(original))
            headings_uk = len(SUBHEADING.findall(text_uk))
            if headings_src != headings_uk:
                problems.append(
                    f"{path.name}:{key}: підзаголовків {headings_src} → {headings_uk}"
                )
            # англійський залишок: багато латиниці на кожну кирилицю
            latin, cyrillic = len(LATIN.findall(text_uk)), len(CYRILLIC.findall(text_uk))
            if latin > 3 and cyrillic and latin / cyrillic > 0.25:
                problems.append(
                    f"{path.name}:{key}: схоже на неперекладене ({latin} лат. / {cyrillic} кир.)"
                )

    for problem in problems[:40]:
        print("  !", problem)
    print(f"\nперевірено: {checked}; проблем: {len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

