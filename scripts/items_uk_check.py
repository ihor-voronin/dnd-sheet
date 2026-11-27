"""Швидка перевірка якості перекладів предметів: довжина й кістки.

Не замінює читання очима, але ловить обрізаний текст («переклали перший
абзац і кинули») і загублені кістки — те, що на екрані видно як помилку
правила.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "var" / "translations" / "items"
DICE = re.compile(r"\d+d\d+(?:\s*[+-]\s*\d+)?")


def main() -> None:
    suspicious: list[tuple[str, str]] = []
    total = 0
    for source in sorted((WORK / "in").glob("*.json")):
        also = ROOT / "content" / "translations" / "items" / source.name
        incoming = json.loads(source.read_text(encoding="utf-8"))["items"]
        if not also.exists():
            suspicious.append((source.name, "немає перекладу"))
            continue
        rows = {row["id"]: row for row in json.loads(also.read_text(encoding="utf-8"))["items"]}
        for item in incoming:
            if not item.get("text_en"):
                continue
            total += 1
            row = rows.get(item["id"])
            if row is None:
                suspicious.append((item["name_en"], "запису немає"))
                continue
            english = item["text_en"]
            ukrainian = row.get("text_uk") or ""
            ratio = len(ukrainian) / len(english) if english else 0
            if ratio < 0.55:
                suspicious.append((item["name_en"], f"коротко {ratio:.2f}"))
            elif ratio > 1.9:
                suspicious.append((item["name_en"], f"довго {ratio:.2f}"))
            if sorted(DICE.findall(english.replace(" ", ""))) != sorted(DICE.findall(ukrainian.replace(" ", ""))):
                suspicious.append((item["name_en"], "кістки не збігаються"))
    print(f"описів перевірено: {total}")
    print(f"підозрілих: {len(suspicious)}")
    for name, why in suspicious[:30]:
        print(f"  {name}: {why}")


if __name__ == "__main__":
    main()
