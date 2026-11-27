"""Підготувати передісторії до перекладу: описи, риси, спорядження.

Текст передісторії живе в записі довідника (`text_en`): опис — це проза до
першого підзаголовка, риса — розділ `#### Feature: Military Rank`, а
спорядження — рядок `Equipment:` (його розбирає `background_info`). Переклад
тому лежить поруч — у `content/translations/backgrounds/`, ключ — `sha1`
оригіналу, як у видів і класів.

Скрипт нічого не перекладає: він готує вхідні файли й друкує обсяг.

    python scripts/backgrounds_uk_prepare.py [--missing]

Пише:

* `var/uk/backgrounds/input/names.json` — назви передісторій і рис;
* `var/uk/backgrounds/input/descriptions-NN.json` — описи;
* `var/uk/backgrounds/input/features-NN.json` — тексти рис;
* `var/uk/backgrounds/input/equipment.json` — фрази спорядження.
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

from dndsheet.characters.api.background_info import background_details  # noqa: E402
from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

OUT = ROOT / "var" / "uk" / "backgrounds"
WORDS_PER_CHUNK = 4200


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def collect() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict], dict[str, str]]:
    service = build_service()
    names: dict[str, dict] = {}
    descriptions: dict[str, dict] = {}
    features: dict[str, dict] = {}
    equipment: dict[str, str] = {}

    for item in service.backgrounds():
        names.setdefault(
            item.name_en,
            {"id": ident(item.name_en), "name_en": item.name_en, "kind": "background"},
        )
        if item.feature_en:
            names.setdefault(
                item.feature_en,
                {
                    "id": ident(item.feature_en),
                    "name_en": item.feature_en,
                    "kind": "feature",
                },
            )
        details = background_details(service, item.name_en, item.feature_en)
        description = details["description"]
        if description.strip():
            descriptions.setdefault(
                ident(description),
                {
                    "id": ident(description),
                    "background": item.name_en,
                    "text_en": description,
                },
            )
        feature_text = details["feature_text"]
        if feature_text.strip():
            features.setdefault(
                ident(feature_text),
                {
                    "id": ident(feature_text),
                    "background": item.name_en,
                    "feature_en": item.feature_en,
                    "text_en": feature_text,
                },
            )
        for row in details["equipment"]:
            for phrase in [row["text"], *row["choices"]]:
                if phrase.strip():
                    equipment.setdefault(ident(phrase), phrase)
    return names, descriptions, features, equipment


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


def write_json(path: Path, rows: list[dict]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def existing_ids(field: str) -> set[str]:
    done: set[str] = set()
    folder = ROOT / "content" / "translations" / "backgrounds"
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
    names, descriptions, features, equipment = collect()
    input_dir = OUT / "input"
    OUT.mkdir(parents=True, exist_ok=True)
    if "--missing" in sys.argv:
        done_names, done_texts = existing_ids("name_uk"), existing_ids("text_uk")
        names = {key: row for key, row in names.items() if row["id"] not in done_names}
        descriptions = {key: row for key, row in descriptions.items() if key not in done_texts}
        features = {key: row for key, row in features.items() if key not in done_texts}
        equipment = {key: value for key, value in equipment.items() if key not in done_texts}
        for old in input_dir.glob("*.json") if input_dir.is_dir() else []:
            old.unlink()

    input_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        input_dir / "names.json",
        [row for _, row in sorted(names.items())],
    )
    write_json(
        input_dir / "equipment.json",
        [{"id": key, "phrase_en": value} for key, value in sorted(equipment.items(), key=lambda row: row[1])],
    )
    desc_chunks = write_chunks(input_dir, "descriptions", list(descriptions.values()))
    feat_chunks = write_chunks(input_dir, "features", list(features.values()))

    print(f"назв: {len(names)} (з них рис: {sum(1 for r in names.values() if r['kind'] == 'feature')})")
    print(f"описів: {len(descriptions)} (черг: {desc_chunks})")
    print(f"рис: {len(features)} (черг: {feat_chunks})")
    print(f"фраз спорядження: {len(equipment)}")
    print(
        "слів:",
        sum(len(row["text_en"].split()) for row in descriptions.values())
        + sum(len(row["text_en"].split()) for row in features.values()),
    )
    print(f"вхід: {input_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
