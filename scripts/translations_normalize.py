"""Звести варіанти термінів у перекладах корпусу до одного (за глосарієм).

Тексти перекладали кілька агентів паралельно, і частина термінів, яких не було в
глосарії, вийшла різною: «рейтинг / рівень / показник небезпеки», «темнозір» і
«темний зір», «МДР» і «МУД». Скрипт правит лише `text_uk` і лише ці відомі
пари; нові терміни після цього — у `content/glossary.uk.yml`.

    python scripts/translations_normalize.py          # показати, скільки замін
    python scripts/translations_normalize.py --write  # записати
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: (шаблон, заміна) — від довших до коротших, з урахуванням відмінка.
RULES: tuple[tuple[str, str], ...] = (
    # Challenge rating — «показник небезпеки».
    (r"\b([Рр])ейтингом небезпеки", lambda m: ("П" if m.group(1) == "Р" else "п") + "оказником небезпеки"),
    (r"\b([Рр])івнем небезпеки", lambda m: ("П" if m.group(1) == "Р" else "п") + "оказником небезпеки"),
    (r"\b([Рр])ейтингу небезпеки", lambda m: ("П" if m.group(1) == "Р" else "п") + "оказника небезпеки"),
    (r"\b([Рр])івня небезпеки", lambda m: ("П" if m.group(1) == "Р" else "п") + "оказника небезпеки"),
    (r"\b([Рр])ейтинг небезпеки", lambda m: ("П" if m.group(1) == "Р" else "п") + "оказник небезпеки"),
    (r"\b([Рр])івень небезпеки", lambda m: ("П" if m.group(1) == "Р" else "п") + "оказник небезпеки"),
    (r"\(РН\)", "(ПН)"),
    # Darkvision — «темний зір».
    (r"\b([Тт])емнозором\b", lambda m: m.group(1) + "емним зором"),
    (r"\b([Тт])емнозору\b", lambda m: m.group(1) + "емного зору"),
    (r"\b([Тт])емнозір\b", lambda m: m.group(1) + "емний зір"),
    # Навичка Investigation — «Розслідування», як на листі.
    (r"\bАналіз\b", "Розслідування"),
    # Скорочення Мудрості — як у labels.ts.
    (r"\bМДР\b", "МУД"),
    # Acquisitions Incorporated — назва книги, транслітом.
    (r"корпораці[яї] [«„]Здобутки[»“]", "«Аквізишнз Інкорпорейтед»"),
)


def normalize(text: str) -> tuple[str, int]:
    total = 0
    for pattern, replacement in RULES:
        text, count = re.subn(pattern, replacement, text)
        total += count
    return text, total


def main(write: bool) -> None:
    grand = 0
    for path in sorted((ROOT / "content" / "translations").glob("*/*.json")):
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        rows = data if isinstance(data, list) else next((v for v in data.values() if isinstance(v, list)), [])
        changed = 0
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("text_uk"), str):
                row["text_uk"], count = normalize(row["text_uk"])
                changed += count
        if changed:
            grand += changed
            print(f"{path.relative_to(ROOT)}: {changed}")
            if write:
                indent = 1 if raw.startswith("[\n {") else 2
                path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + ("\n" if raw.endswith("\n") else ""), encoding="utf-8")
    print(f"Разом замін: {grand}" + ("" if write else " (без --write нічого не записано)"))


if __name__ == "__main__":
    main("--write" in sys.argv)
