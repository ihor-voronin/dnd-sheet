"""Підготувати особливості підкласів до перекладу.

Підкласи — це `##`-заголовки в тексті підкласу, рівень у них записаний
курсивом (`*10th-level Cleric feature*`). Текст живе в записі довідника, тому
переклад лежить поруч — у `content/translations/subclasses/`, ключ — `sha1`
оригіналу, як у видів, класів і передісторій.

    python scripts/subclasses_uk_prepare.py [--missing]

Пише:

* `var/uk/subclasses/input/names.json` — назви особливостей;
* `var/uk/subclasses/input/texts-NN.json` — тексти особливостей.
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

from dndsheet.characters.api.features import subclass_features  # noqa: E402
from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

OUT = ROOT / "var" / "uk" / "subclasses"
WORDS_PER_CHUNK = 4000


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def collect() -> tuple[dict[str, dict], dict[str, dict]]:
    service = build_service()
    names: dict[str, dict] = {}
    texts: dict[str, dict] = {}
    for definition in service.class_definitions():
        for entry in service.subclasses(definition.name_en):
            for item in subclass_features(service, entry.id):
                name = item["name_en"]
                names.setdefault(
                    name,
                    {
                        "id": ident(name),
                        "name_en": name,
                        "subclass": item["subclass_name"],
                    },
                )
                body = item["description"]
                if body.strip():
                    key = ident(body)
                    texts.setdefault(
                        key,
                        {
                            "id": key,
                            "subclass": item["subclass_name"],
                            "class_key": definition.key,
                            "name_en": name,
                            "level": item["level"],
                            "text_en": body,
                        },
                    )
    return names, texts


def write_chunks(folder: Path, prefix: str, items: list[dict]) -> int:
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
    done: set[str] = set()
    folder = ROOT / "content" / "translations" / "subclasses"
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
    names, texts = collect()
    input_dir = OUT / "input"
    OUT.mkdir(parents=True, exist_ok=True)
    if "--missing" in sys.argv:
        done_names, done_texts = existing_ids("name_uk"), existing_ids("text_uk")
        names = {key: row for key, row in names.items() if row["id"] not in done_names}
        texts = {key: row for key, row in texts.items() if key not in done_texts}
        for old in input_dir.glob("*.json") if input_dir.is_dir() else []:
            old.unlink()

    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "names.json").write_text(
        json.dumps(
            [row for _, row in sorted(names.items())], ensure_ascii=False, indent=1
        ),
        encoding="utf-8",
    )
    chunks = write_chunks(input_dir, "texts", list(texts.values()))
    print(f"назв: {len(names)}")
    print(f"текстів: {len(texts)} (черг: {chunks})")
    print("слів:", sum(len(row["text_en"].split()) for row in texts.values()))
    print(f"вхід: {input_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
