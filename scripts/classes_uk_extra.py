"""Зібрати тексти опційних умінь класів, яких немає в перекладі глави.

Глава класу в PHB не містить опційних умінь TCoE («Instinctive Pounce»,
«Magical Guidance»…), а механіки класу їх знають. Тому для них потрібен
окремий маленький набір перекладів.

    python scripts/classes_uk_extra.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("DNDSHEET_CONTENT_DIR", str(ROOT / "content"))

from dndsheet.characters.api import classes_uk  # noqa: E402
from dndsheet.characters.api.features import class_texts_all  # noqa: E402
from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

OUT = ROOT / "var" / "uk" / "classes" / "extra"


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def main() -> int:
    service = build_service()
    rows: dict[str, dict] = {}
    for definition in service.class_definitions():
        texts = class_texts_all(service, definition.key)
        # Лише вміння з індексу механік: у главі TCoE є ще й цілі підкласи, і
        # їхній переклад уже живе в шарі підкласів — тут він зайвий.
        for feature in definition.features:
            text = texts.get(feature.name_en)
            if not text or not text.strip() or classes_uk.text_uk(text):
                continue
            rows.setdefault(
                ident(text),
                {
                    "id": ident(text),
                    "class_key": definition.key,
                    "name_en": feature.name_en,
                    "text_en": text,
                },
            )
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    (OUT / "texts-01.json").write_text(
        json.dumps(list(rows.values()), ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"текстів: {len(rows)}")
    print("слів:", sum(len(row["text_en"].split()) for row in rows.values()))
    print(f"вхід: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
