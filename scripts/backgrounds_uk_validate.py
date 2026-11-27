"""Перевірити якість перекладу передісторій: числа, кубики, абзаци, мова.

    python scripts/backgrounds_uk_validate.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "var" / "uk" / "backgrounds" / "input"
OUTPUT = ROOT / "content" / "translations" / "backgrounds"

DICE = re.compile(r"\b\d*d\d+\b")
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
    joined = THOUSANDS.sub("", text)
    return sorted(DICE.findall(joined)), sorted(re.findall(r"\d+", joined))


def paragraphs(text: str) -> int:
    return len([part for part in re.split(r"\n\s*\n", text) if part.strip()])


def main() -> int:
    problems: list[str] = []
    checked = 0

    for path in sorted(INPUT.glob("*.json")):
        field = "name_uk" if path.name == "names.json" else "text_uk"
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
            original = str(
                row.get("text_en") or row.get("name_en") or row.get("phrase_en") or ""
            )
            if not CYRILLIC.search(text_uk):
                problems.append(f"{path.name}:{key}: без кирилиці — {text_uk[:40]!r}")
                continue
            if field == "name_uk":
                if LATIN.search(text_uk):
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
            if len(SUBHEADING.findall(original)) != len(SUBHEADING.findall(text_uk)):
                problems.append(f"{path.name}:{key}: підзаголовки не збігаються")
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
