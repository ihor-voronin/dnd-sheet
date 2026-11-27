"""Підготувати описи підкласів (вступ до глави) до перекладу.

Особливості вже перекладені; лишався вступ — проза на початку глави
підкласу («An Alchemist is an expert at combining reagents…»). Він потрібен
на кроці «Клас»: коли гравець обирає підклас, екран має сказати, що це таке.

Файли лягають у той самий `var/uk/subclasses/input/`, що й тексти, тому
`subclasses_uk_check.py` і `subclasses_uk_validate.py` перевіряють їх без змін.

    python scripts/subclasses_uk_intro.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("DNDSHEET_CONTENT_DIR", str(ROOT / "content"))

from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

INPUT = ROOT / "var" / "uk" / "subclasses" / "input"
WORDS_PER_CHUNK = 4000


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def intro(text: str) -> str:
    """Проза до першого `##` (без заголовка `# Alchemist`)."""
    head = re.split(r"(?m)^##\s+", text or "", maxsplit=1)[0]
    head = re.sub(r"(?m)^#\s+.*\n", "", head, count=1)
    return head.strip()


def collect() -> list[dict]:
    service = build_service()
    rows: dict[str, dict] = {}
    for definition in service.class_definitions():
        for entry in service.subclasses(definition.name_en):
            body = intro(entry.text_en or "")
            if not body:
                continue
            rows.setdefault(
                ident(body),
                {
                    "id": ident(body),
                    "subclass": entry.name_en,
                    "class_key": definition.key,
                    "text_en": body,
                },
            )
    return [row for _, row in sorted(rows.items(), key=lambda pair: pair[0])]


def main() -> int:
    rows = collect()
    INPUT.mkdir(parents=True, exist_ok=True)
    for old in INPUT.glob("intro-*.json"):
        old.unlink()
    chunks: list[list[dict]] = []
    current: list[dict] = []
    words = 0
    for row in rows:
        size = len(row["text_en"].split())
        if current and words + size > WORDS_PER_CHUNK:
            chunks.append(current)
            current, words = [], 0
        current.append(row)
        words += size
    if current:
        chunks.append(current)
    for number, chunk in enumerate(chunks, start=1):
        (INPUT / f"intro-{number:02d}.json").write_text(
            json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    print(f"описів: {len(rows)} (черг: {len(chunks)})")
    print("слів:", sum(len(row["text_en"].split()) for row in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
