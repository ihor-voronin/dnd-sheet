"""Підготувати тексти класів до перекладу: назви вмінь, тексти, описи.

Корпус тримає особливості класу всередині `text_en`: класові вміння — це
заголовки `###` (Rage, Unarmored Defense), а опис класу — проза на початку
глави. Тому переклад живе не в записах довідника, а поруч — у
`content/translations/classes/`, і ключ — `sha1(оригінал)[:10]`: «Ability
Score Improvement» у дванадцяти класів — той самий текст, і платити за нього
двічі не потрібно.

Скрипт нічого не перекладає: він лише готує вхідні файли для агентів і
друкує, скільки всього треба перекласти.

    python scripts/classes_uk_prepare.py [--missing]

Пише:

* `var/uk/classes/input/names.json` — унікальні назви вмінь (`{id, name_en}`);
* `var/uk/classes/input/texts-01.json` … — тексти вмінь (`{id, name_en, class, text_en}`);
* `var/uk/classes/input/descriptions.json` — описи класів (`{id, class, text_en}`).
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

from dndsheet.characters.api.features import class_details  # noqa: E402
from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

OUT = ROOT / "var" / "uk" / "classes"
#: Скільки англійських слів в одній черзі: більше — агент втрачає увагу, менше
#: — багато разів повторює глосарій.
WORDS_PER_CHUNK = 4000


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def collect() -> tuple[dict[str, str], dict[str, dict], dict[str, dict]]:
    service = build_service()
    names: dict[str, str] = {}
    texts: dict[str, dict] = {}
    descriptions: dict[str, dict] = {}

    for definition in service.class_definitions():
        details = class_details(service, definition.key)
        description = details.get("description") or ""
        if description.strip():
            descriptions.setdefault(
                ident(description),
                {"class": definition.name_en, "class_key": definition.key, "text_en": description},
            )
        for feature in details["features"]:
            name_en = feature["name_en"]
            names.setdefault(name_en, ident(name_en))
            text = feature.get("text") or ""
            if text.strip():
                key = ident(text)
                texts.setdefault(
                    key,
                    {
                        "id": key,
                        "name_en": name_en,
                        "class_key": definition.key,
                        "text_en": text,
                    },
                )
    return names, texts, descriptions


def write_chunks(folder: Path, prefix: str, items: list[dict]) -> int:
    """Розкласти тексти на черги за кількістю слів, не розриваючи запис."""
    folder.mkdir(parents=True, exist_ok=True)
    chunks: list[list[dict]] = []
    current: list[dict] = []
    words = 0
    for item in items:
        size = len(str(item.get("text_en") or "").split())
        if current and words + size > WORDS_PER_CHUNK:
            chunks.append(current)
            current, words = [], 0
        current.append(item)
        words += size
    if current:
        chunks.append(current)
    for number, chunk in enumerate(chunks, start=1):
        path = folder / f"{prefix}-{number:02d}.json"
        path.write_text(json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(chunks)


def existing_ids(field: str) -> set[str]:
    """Які id уже перекладені — щоб не платити за них удруге."""
    done: set[str] = set()
    folder = ROOT / "content" / "translations" / "classes"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict) and row.get(field):
                done.add(str(row.get("id")))
    return done


def main() -> int:
    names, texts, descriptions = collect()
    input_dir = OUT / "input"
    OUT.mkdir(parents=True, exist_ok=True)
    if "--missing" in sys.argv:
        done_names, done_texts = existing_ids("name_uk"), existing_ids("text_uk")
        names = {key: value for key, value in names.items() if value not in done_names}
        texts = {key: row for key, row in texts.items() if key not in done_texts}
        descriptions = {key: row for key, row in descriptions.items() if key not in done_texts}
        for old in input_dir.glob("*.json") if input_dir.is_dir() else []:
            old.unlink()

    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "names.json").write_text(
        json.dumps(
            [{"id": value, "name_en": key} for key, value in sorted(names.items())],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    (input_dir / "descriptions.json").write_text(
        json.dumps(
            [{"id": key, **row} for key, row in sorted(descriptions.items())],
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    chunks = write_chunks(input_dir, "texts", list(texts.values()))

    print(f"назв: {len(names)}")
    print(f"текстів: {len(texts)} (черг: {chunks})")
    print(f"описів: {len(descriptions)}")
    print(
        "слів:",
        sum(len(row["text_en"].split()) for row in texts.values())
        + sum(len(row["text_en"].split()) for row in descriptions.values()),
    )
    print(f"вхід: {input_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
